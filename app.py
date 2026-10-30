"""
CareMate: A Personalized Nurse Assistant
Run:  pip install -r requirements.txt
      python app.py
Open: http://127.0.0.1:5000

Three roles, switched with the "Signed in as" menu (demo only, no passwords):
  patient -> reports, appointments, prescriptions, nearest stores
  doctor  -> bookings, slots & fees, patients (reports, uploads, prescriptions)
  admin   -> insights (most booked doctors, most prescribed medicines), users
"""

import os
import re
import uuid
from datetime import date, timedelta
from functools import wraps

from flask import (Flask, abort, flash, jsonify, redirect, render_template, request,
                   send_from_directory, session, url_for)
from werkzeug.utils import secure_filename

from db import connect_from_config
from services import DAY_TIMES, FREQ_TIMES, PRIORITY_LABELS, REPORT_TYPES, load

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
ALLOWED = {"pdf", "png", "jpg", "jpeg"}
FREQUENCIES = list(FREQ_TIMES)
TIME_RE = re.compile(r"([01]\d|2[0-3]):[0-5]\d")   # HH:MM, 00:00-23:59

app = Flask(__name__)
app.secret_key = "fds-course-project-demo-key"
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024   # 10 MB uploads
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Queries always run on our own data structures; the database (if configured) just stores the rows.
na = load(connect_from_config())


# ------------------------------------------------------------------ helpers
def to_int(value, default):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def to_fee(value, default):
    try:
        fee = round(float(value), 2)
        return fee if 0 <= fee <= 100000 else default
    except (TypeError, ValueError):
        return default


def valid_date(value):
    try:
        date.fromisoformat(value)
        return True
    except (TypeError, ValueError):
        return False


def current_user():
    """(role, user). Falls back to the first active patient."""
    uid = session.get("user_id")
    u = na.user(uid)
    if not u or not u["active"]:
        u = na.all_patients(active_only=True)[0]
        session["user_id"] = u["id"]
    return na.role_of(u["id"]), u


def requires(role):
    def deco(view):
        @wraps(view)
        def wrapper(*args, **kwargs):
            if current_user()[0] != role:
                flash(f"That page is for {role}s. Switch user in the sidebar.", "info")
                return redirect(url_for("home"))
            return view(*args, **kwargs)
        return wrapper
    return deco


def save_upload(f):
    """Returns (filename_or_None, error_or_None)."""
    if not f or not f.filename:
        return None, None
    ext = f.filename.rsplit(".", 1)[-1].lower()
    if ext not in ALLOWED:
        return None, "Only PDF, PNG or JPG files are allowed."
    filename = f"{uuid.uuid4().hex[:8]}_{secure_filename(f.filename)}"
    f.save(os.path.join(UPLOAD_DIR, filename))
    return filename, None


def remove_upload(filename):
    if filename:
        try:
            os.remove(os.path.join(UPLOAD_DIR, filename))
        except FileNotFoundError:
            pass


@app.context_processor
def inject_globals():
    role, me = current_user()
    return dict(role=role, me=me,
                switch_patients=na.all_patients(active_only=True),
                switch_doctors=na.all_doctors(active_only=True),
                switch_admins=na.all_admins(active_only=True),
                doctor_name=lambda did: na.doctors.get(did)["name"] if na.doctors.contains(did) else "Doctor",
                patient_name=lambda pid: na.patients.get(pid)["name"],
                today=date.today().isoformat())


@app.post("/switch-user")
def switch_user():
    u = na.user(request.form.get("user_id"))
    if u and u["active"]:
        session["user_id"] = u["id"]
    return redirect(url_for("home"))


@app.get("/")
def home():
    role, me = current_user()
    if role == "doctor":
        return doctor_home(me)
    if role == "admin":
        return admin_home(me)
    upcoming = [a for a in na.patient_appointments(me["id"]) if a["status"] in ("Pending", "Confirmed")]
    return render_template("home.html",
                           reports=na.list_reports(me["id"])[:3],
                           report_count=len(na.reports.get(me["id"])),
                           upcoming=upcoming,
                           schedule=na.daily_schedule(me["id"]),
                           recent_rx=na.prescription_history(me["id"])[:3],
                           activity=na.activity_for("patient", me["id"]))


@app.get("/uploads/<path:filename>")
def uploaded_file(filename):
    # the patient who owns the report, or a doctor whose booking with them was accepted
    role, me = current_user()
    report = next((r for r in na.report_by_id.values() if r["filename"] == filename), None)
    if not na.can_view_report(role, me["id"], report):
        abort(404)
    return send_from_directory(UPLOAD_DIR, filename)


@app.get("/report/<rid>")
def view_report(rid):
    """One report on its own page, with the file in the browser's PDF / image viewer."""
    role, me = current_user()
    report = na.report_by_id.get(rid)
    if not na.can_view_report(role, me["id"], report):
        abort(404)
    ext = report["filename"].rsplit(".", 1)[-1].lower() if report["filename"] else None
    back = url_for("reports") if role == "patient" else url_for("doctor_patients", patient=report["patient_id"])
    return render_template("report.html", r=report, ext=ext, back=back,
                           patient=na.patients.get(report["patient_id"]),
                           can_change=na.can_change_file(role, me["id"], report))


@app.post("/report/<rid>/file")
def attach_report_file(rid):
    role, me = current_user()
    report = na.report_by_id.get(rid)
    if not na.can_view_report(role, me["id"], report):
        abort(404)
    if not na.can_change_file(role, me["id"], report):
        flash("Only whoever uploaded this report can replace its file.", "error")
        return redirect(url_for("view_report", rid=rid))
    filename, err = save_upload(request.files.get("file"))
    if err or not filename:
        flash(err or "Choose a PDF, PNG or JPG file first.", "error")
    else:
        old = report["filename"]
        na.attach_file(rid, filename)
        if old and old != filename:
            remove_upload(old)
        flash("File attached.", "ok")
    return redirect(url_for("view_report", rid=rid))


@app.get("/api/medicines")
def api_medicines():
    return jsonify(na.suggest_medicines(request.args.get("q", "")))


@app.get("/under-the-hood")
def under_the_hood():
    return render_template("dsa.html", stats=na.dsa_stats())


# ================================================================== PATIENT
@app.get("/reports")
@requires("patient")
def reports():
    me = current_user()[1]
    args = request.args
    on_date = args.get("on_date", "")
    if on_date:
        items = na.find_report_on_date(me["id"], on_date)          # binary search
        algo = f"Binary search on date-sorted reports for {on_date}"
    else:
        items = na.list_reports(me["id"], args.get("q", ""), args.get("type", ""),
                                args.get("sort", "date"), args.get("order", "desc"),
                                args.get("from", ""), args.get("to", ""))
        used = ["BST range query" if (args.get("from") or args.get("to")) else "linked-list traversal"]
        if args.get("q"):
            used.append("linear search")
        used.append(f"merge sort by {args.get('sort', 'date')}")
        algo = " → ".join(used)
    bst = na.report_index.get(me["id"])
    return render_template("reports.html", items=items, types=REPORT_TYPES, args=args, algo=algo,
                           total=len(na.reports.get(me["id"])), bst_height=bst.height())


@app.post("/reports/upload")
@requires("patient")
def upload_report():
    me = current_user()[1]
    title = request.form.get("title", "").strip()
    rdate = request.form.get("date") or date.today().isoformat()
    if not title or not valid_date(rdate):
        flash("Please give the report a title and a valid date.", "error")
        return redirect(url_for("reports"))
    filename, err = save_upload(request.files.get("file"))
    if err:
        flash(err, "error")
        return redirect(url_for("reports"))
    rtype = request.form.get("type")
    na.add_report(me["id"], title, rtype if rtype in REPORT_TYPES else "Other", rdate,
                  request.form.get("doctor", ""), request.form.get("notes", ""), filename)
    flash(f"'{title}' added to your library.", "ok")
    return redirect(url_for("reports"))


@app.post("/reports/<rid>/delete")
@requires("patient")
def delete_report(rid):
    me = current_user()[1]
    r = na.report_by_id.get(rid)
    if not r or r["patient_id"] != me["id"] or r["uploaded_by"]:
        flash("You can only delete reports you uploaded yourself.", "error")
        return redirect(url_for("reports"))
    na.delete_report(me["id"], rid)
    remove_upload(r["filename"])
    flash(f"Deleted '{r['title']}'.", "ok")
    return redirect(url_for("reports"))


@app.get("/appointments")
@requires("patient")
def appointments():
    me = current_user()[1]
    doctors = na.all_doctors(active_only=True)
    return render_template("appointments.html", doctors=doctors,
                           slots={d["id"]: na.bookable_slots(d["id"]) for d in doctors},
                           mine=na.patient_appointments(me["id"]),
                           waiting=[w for d in doctors for w in na.waitlist.get(d["id"]).to_list()
                                    if w["patient_id"] == me["id"]],
                           priorities=PRIORITY_LABELS, selected=request.args.get("doctor"))


@app.post("/appointments/book")
@requires("patient")
def book():
    me = current_user()[1]
    did = request.form.get("doctor_id")
    doctor = na.doctors.get(did)
    if not doctor or not doctor["active"]:
        flash("Please choose a doctor.", "error")
        return redirect(url_for("appointments"))
    slot = request.form.get("slot", "")
    if slot and slot not in [s for s, _ in na.bookable_slots(did)]:
        flash("That slot is no longer free. Please pick another.", "error")
        return redirect(url_for("appointments", doctor=did))
    priority = to_int(request.form.get("priority"), 3)
    if priority not in PRIORITY_LABELS:
        priority = 3
    status, appt = na.book_appointment(me["id"], did, slot, priority,
                                       request.form.get("reason", "").strip() or "General consultation")
    if status == "confirmed":
        flash(f"Confirmed with {doctor['name']} on {appt['slot']}. Fee ₹{appt['fee']:g}, pay at the clinic.", "ok")
    elif status == "pending":
        flash(f"Request sent to {doctor['name']} for {appt['slot']}. You'll see it here once they accept.", "info")
    else:
        flash("No free slot, so you've joined the waiting list. "
              "You'll get the first slot that frees up.", "info")
    return redirect(url_for("appointments", doctor=did))


@app.post("/appointments/<aid>/cancel")
@requires("patient")
def cancel(aid):
    appt = na.cancel_appointment(aid, current_user()[1]["id"])
    flash("Appointment cancelled." if appt else "Could not cancel.", "ok" if appt else "error")
    return redirect(url_for("appointments"))


@app.get("/prescriptions")
@requires("patient")
def prescriptions():
    me = current_user()[1]
    history = na.prescription_history(me["id"])
    chosen = na.rx_by_id.get(request.args.get("rx", ""))
    if not chosen or chosen["patient_id"] != me["id"]:
        chosen = history[0] if history else None
    return render_template("prescriptions.html", history=history, chosen=chosen,
                           schedule=na.daily_schedule(me["id"]), is_active=na.is_active,
                           rx_running=lambda rx: any(na.is_active(rx, it) for it in rx["items"]),
                           new_since=(date.today() - timedelta(days=3)).isoformat())


@app.get("/stores")
@requires("patient")
def stores():
    me = current_user()[1]
    origin = request.args.get("from") or me["location"]
    if origin not in na.city.adj:
        origin = me["location"]
    use_rx = request.args.get("rx", "1") == "1"
    needed = na.current_medicines(me["id"]) if use_rx else []
    results = na.nearest_stores(origin, needed)
    selected = request.args.get("store") or (results[0]["store"]["id"] if results else None)
    chosen = next((r for r in results if r["store"]["id"] == selected), None)
    return render_template("stores.html", results=results, origin=origin, places=na.places(),
                           needed=needed, use_rx=use_rx, chosen=chosen,
                           graph=dict(pos=na.city.pos, edges=na.city.edges()))


# ================================================================== DOCTOR
def doctor_home(me):
    did = me["id"]
    upcoming = [a for a in na.doctor_queue_view(did)]
    return render_template("doctor_home.html", pending=na.pending_requests(did),
                           queue=upcoming, waiting=na.waitlist.get(did).to_list(),
                           days=na.upcoming_days(did)[:5],
                           activity=na.activity_for("doctor", did))


@app.post("/doctor/auto-accept")
@requires("doctor")
def toggle_auto_accept():
    me = current_user()[1]
    on = request.form.get("on") == "1"
    na.set_auto_accept(me["id"], on)
    flash("Auto-accept is ON: new bookings are confirmed instantly." if on else
          "Auto-accept is OFF: you'll accept or reject each booking.", "ok")
    return redirect(url_for("home"))


@app.post("/doctor/requests/<aid>/<action>")
@requires("doctor")
def handle_request(aid, action):
    me = current_user()[1]
    if action == "accept":
        appt = na.accept_appointment(aid, me["id"])
        msg = "Accepted. You can now open this patient's reports."
    elif action == "reject":
        appt = na.reject_appointment(aid, me["id"])
        msg = "Request declined; the slot went to the waiting list or back to free."
    else:
        abort(404)
    flash(msg if appt else "That request was already handled.", "ok" if appt else "info")
    return redirect(url_for("home"))


@app.post("/doctor/next")
@requires("doctor")
def call_next():
    appt = na.call_next_patient(current_user()[1]["id"])
    if appt:
        flash(f"Now seeing {na.patients.get(appt['patient_id'])['name']} "
              f"({appt['priority_label']}): {appt['reason']}", "ok")
    else:
        flash("Queue is empty.", "info")
    return redirect(url_for("home"))


@app.route("/doctor/slots", methods=["GET", "POST"])
@requires("doctor")
def doctor_slots():
    me = current_user()[1]
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    day = request.values.get("day") or tomorrow
    if not valid_date(day) or day < date.today().isoformat():
        flash("Pick today or a future date.", "error")
        return redirect(url_for("doctor_slots"))
    if request.method == "POST":
        # any valid HH:MM, so doctors can add custom times outside the half-hour grid
        times = {t for t in request.form.getlist("times") if TIME_RE.fullmatch(t)}
        fee = to_fee(request.form.get("fee"), me["fee"])
        na.set_day_slots(me["id"], day, times, fee)
        flash(f"Saved {len(times)} slot(s) for {day} at ₹{fee:g}.", "ok")
        return redirect(url_for("doctor_slots", day=day))
    view = na.day_view(me["id"], day)
    day_fee = next((f for _, state, f in view if f is not None), me["fee"])
    return render_template("doctor_slots.html", day=day, view=view, fee=day_fee, grid=DAY_TIMES,
                           days=na.upcoming_days(me["id"]))


def doctor_patient_or_404(pid):
    me = current_user()[1]
    if not na.patients.contains(pid) or not na.has_access(me["id"], pid):
        abort(404)
    return me, na.patients.get(pid)


@app.get("/doctor/patients")
@requires("doctor")
def doctor_patients():
    me = current_user()[1]
    patients = na.doctor_patients(me["id"])
    pid = request.args.get("patient") or (patients[0]["id"] if patients else None)
    patient = na.patients.get(pid) if pid and na.has_access(me["id"], pid) else None
    return render_template("doctor_patients.html", patients=patients, patient=patient,
                           reports=na.list_reports(pid) if patient else [],
                           history=na.prescription_history(pid) if patient else [],
                           types=REPORT_TYPES, frequencies=FREQUENCIES)


@app.post("/doctor/patients/<pid>/report")
@requires("doctor")
def doctor_upload_report(pid):
    me, patient = doctor_patient_or_404(pid)
    title = request.form.get("title", "").strip()
    rdate = request.form.get("date") or date.today().isoformat()
    if not title or not valid_date(rdate):
        flash("Please give the report a title and a valid date.", "error")
        return redirect(url_for("doctor_patients", patient=pid))
    filename, err = save_upload(request.files.get("file"))
    if err:
        flash(err, "error")
        return redirect(url_for("doctor_patients", patient=pid))
    rtype = request.form.get("type")
    na.add_report(pid, title, rtype if rtype in REPORT_TYPES else "Other", rdate, me["name"],
                  request.form.get("notes", ""), filename, uploaded_by=me["id"])
    flash(f"'{title}' uploaded to {patient['name']}'s reports.", "ok")
    return redirect(url_for("doctor_patients", patient=pid))


@app.post("/doctor/patients/<pid>/prescribe")
@requires("doctor")
def prescribe(pid):
    me, patient = doctor_patient_or_404(pid)
    f = request.form
    items = []
    for med, dose, freq, days in zip(f.getlist("medicine"), f.getlist("dose"),
                                     f.getlist("frequency"), f.getlist("days")):
        if med.strip():
            items.append(dict(medicine=med.strip()[:100], dose=dose.strip()[:50] or "1 tablet",
                              frequency=freq if freq in FREQUENCIES else FREQUENCIES[0],
                              days=min(365, max(1, to_int(days, 1)))))
    if not items:
        flash("Add at least one medicine.", "error")
    else:
        na.add_prescription(pid, me["id"], items, f.get("notes", ""))
        flash(f"Prescription sent to {patient['name']}. It's on their Prescriptions page now.", "ok")
    return redirect(url_for("doctor_patients", patient=pid))


@app.post("/doctor/patients/<pid>/undo")
@requires("doctor")
def undo_prescription(pid):
    me, _ = doctor_patient_or_404(pid)
    rx = na.undo_last_prescription(pid, me["id"])
    flash(f"Withdrew the prescription from {rx['date']} (stack pop)." if rx else
          "Only the newest prescription can be withdrawn, and only by the doctor who wrote it.",
          "ok" if rx else "info")
    return redirect(url_for("doctor_patients", patient=pid))


# ================================================================== ADMIN
def admin_home(me):
    return render_template("admin_home.html", top_doctors=na.most_booked_doctors(5),
                           top_medicines=na.most_prescribed_medicines(5),
                           totals=na.platform_totals(), activity=na.activity_for("admin", me["id"], 10))


@app.get("/admin/users")
@requires("admin")
def admin_users():
    return render_template("admin_users.html", patients=na.all_patients(), doctors=na.all_doctors(),
                           admins=na.all_admins(), places=na.places())


def user_fields(role, form):
    """Read and clean the form fields for one kind of user."""
    name = form.get("name", "").strip()[:100]
    if not name:
        return None
    if role == "patient":
        loc = form.get("location")
        return dict(name=name, age=min(130, max(0, to_int(form.get("age"), 0))),
                    gender=form.get("gender", "")[:10], blood_group=form.get("blood_group", "")[:5],
                    location=loc if loc in na.places() else na.places()[0],
                    phone=form.get("phone", "")[:20])
    if role == "doctor":
        return dict(name=name, specialty=form.get("specialty", "")[:100],
                    clinic=form.get("clinic", "")[:150], fee=to_fee(form.get("fee"), 500),
                    phone=form.get("phone", "")[:20])
    return dict(name=name)


@app.post("/admin/users/add/<role>")
@requires("admin")
def admin_add_user(role):
    fields = user_fields(role, request.form)
    if role not in ("patient", "doctor", "admin") or not fields:
        flash("Please fill in at least the name.", "error")
        return redirect(url_for("admin_users"))
    add = dict(patient=na.add_patient, doctor=na.add_doctor, admin=na.add_admin)[role]
    add(**fields)
    flash(f"Added {role} {fields['name']}.", "ok")
    return redirect(url_for("admin_users"))


@app.post("/admin/users/<uid>/edit")
@requires("admin")
def admin_edit_user(uid):
    role = na.role_of(uid)
    fields = user_fields(role, request.form) if role else None
    if not fields:
        flash("Please fill in at least the name.", "error")
    else:
        na.update_user(uid, **fields)
        flash(f"Saved {fields['name']}.", "ok")
    return redirect(url_for("admin_users"))


@app.post("/admin/users/<uid>/toggle")
@requires("admin")
def admin_toggle_user(uid):
    u = na.user(uid)
    if not u:
        abort(404)
    if uid == current_user()[1]["id"]:
        flash("You can't deactivate yourself.", "error")
    elif na.role_of(uid) == "patient" and u["active"] and len(na.all_patients(active_only=True)) == 1:
        flash("Keep at least one active patient.", "error")
    else:
        na.update_user(uid, active=not u["active"])
        flash(f"{u['name']} is now {'active' if u['active'] else 'deactivated'}.", "ok")
    return redirect(url_for("admin_users"))


if __name__ == "__main__":
    app.run(debug=True)
