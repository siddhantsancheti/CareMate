"""
CareMate: A Personalized Nurse Assistant
Run:  pip install -r requirements.txt
      python app.py
Open: http://127.0.0.1:5000

This file only has the web pages. Each feature lives in its own file:
users.py, reports.py, appointments.py, prescriptions.py, stores.py, admin.py
"""

import os
import re
import uuid
from datetime import date, timedelta

from flask import Flask, abort, flash, jsonify, redirect, render_template, request, send_from_directory, session, url_for
from werkzeug.utils import secure_filename

import admin
import appointments
import data
import demo
import prescriptions
import reports
import stores
import users

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads")
EMAIL_RE = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")
FREQUENCIES = list(prescriptions.FREQ_TIMES)

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY") or os.urandom(32).hex()   # sign-ins reset when the app restarts
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024                     # 10 MB uploads
os.makedirs(UPLOAD_DIR, exist_ok=True)
demo.load()


# ------------------------------------------------------------------ helpers
def current_user():
    """(role, user) of whoever is signed in, or (None, None)."""
    return users.find_user(session.get("user_id"))


def number(value, default, low, high):
    """A number from a form, kept between low and high."""
    try:
        return min(high, max(low, int(float(value))))
    except (TypeError, ValueError):
        return default


def valid_date(text):
    try:
        date.fromisoformat(text)
        return True
    except (TypeError, ValueError):
        return False


def save_upload():
    """Saves the uploaded file. Returns (filename or None, error or None)."""
    f = request.files.get("file")
    if not f or not f.filename:
        return None, None
    if f.filename.rsplit(".", 1)[-1].lower() not in ("pdf", "png", "jpg", "jpeg"):
        return None, "Only PDF, PNG or JPG files are allowed."
    filename = uuid.uuid4().hex[:8] + "_" + secure_filename(f.filename)
    f.save(os.path.join(UPLOAD_DIR, filename))
    return filename, None


def report_from_form(patient_id, doctor="", uploaded_by=None):
    """Shared by patient and doctor uploads."""
    title, rdate = request.form.get("title", "").strip(), request.form.get("date") or date.today().isoformat()
    if not title or not valid_date(rdate):
        flash("Please give the report a title and a valid date.", "error")
        return False
    filename, error = save_upload()
    if error:
        flash(error, "error")
        return False
    rtype = request.form.get("type")
    reports.add_report(patient_id, title, rtype if rtype in reports.REPORT_TYPES else "Other", rdate,
                       request.form.get("doctor", doctor), request.form.get("notes", ""), filename, uploaded_by)
    flash(f"'{title}' added.", "ok")
    return True


@app.before_request
def require_login():
    role, user = current_user()
    if request.endpoint not in ("login", "signup", "static") and not user:
        return redirect(url_for("login"))
    if (request.endpoint or "").startswith("doctor_") and role != "doctor":      # doctor pages
        return redirect(url_for("home"))
    if request.endpoint in ("reports", "upload_report", "delete_report", "appointments", "book", "cancel",
                            "prescriptions", "stores") and role != "patient":                  # patient pages
        return redirect(url_for("home"))


@app.context_processor
def add_to_every_page():
    role, me = current_user()
    return dict(role=role, me=me, today=date.today().isoformat(),
                doctor_name=lambda did: data.doctors[did]["name"],
                patient_name=lambda pid: data.patients[pid]["name"])


# ------------------------------------------------------------------ sign up / log in
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user = users.login(request.form.get("email", ""), request.form.get("password", ""))
        if not user:
            flash("Wrong email or password.", "error")
            return render_template("login.html", email=request.form.get("email", "")), 401
        session["user_id"] = user["id"]
        return redirect(url_for("home"))
    return render_template("login.html", email="")


@app.route("/signup", methods=["GET", "POST"])
def signup():
    f = request.form
    if request.method == "GET":
        return render_template("signup.html", form={}, places=stores.places())
    role, name = f.get("role"), f.get("name", "").strip()[:100]
    email, password = f.get("email", "").strip().lower()[:120], f.get("password", "")
    error = ("Choose patient or doctor and give your name." if role not in ("patient", "doctor") or not name else
             "Enter a valid email address." if not EMAIL_RE.fullmatch(email) else
             "That email is already registered. Log in instead." if users.email_taken(email) else
             "Use a password of at least 6 characters." if len(password) < 6 else
             "The two passwords don't match." if password != f.get("confirm") else None)
    if error:
        flash(error, "error")
        return render_template("signup.html", form=f, places=stores.places()), 400
    if role == "patient":
        place = f.get("location") if f.get("location") in stores.places() else "VIIT College"
        user_id = users.add_patient(name, number(f.get("age"), 0, 0, 130), f.get("gender", "")[:10],
                                    f.get("blood_group", "")[:5], place, f.get("phone", "")[:20], email, password)
    else:
        user_id = users.add_doctor(name, f.get("specialty", "")[:100], f.get("clinic", "")[:150],
                                   number(f.get("fee"), 500, 0, 100000), f.get("phone", "")[:20], email, password)
    session["user_id"] = user_id
    flash(f"Welcome to CareMate, {name}!", "ok")
    return redirect(url_for("doctor_slots") if role == "doctor" else url_for("home"))


@app.post("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.get("/")
def home():
    role, me = current_user()
    if role == "doctor":
        return render_template("doctor_home.html", pending=data.requests[me["id"]].to_list(),
                               queue=data.queue[me["id"]].to_list(), waiting=data.waitlist[me["id"]].to_list(),
                               days=appointments.upcoming_days(me["id"])[:5],
                               activity=data.activity_for("doctor", me["id"]))
    if role == "admin":
        return render_template("admin_home.html", top_doctors=admin.most_booked_doctors(),
                               top_medicines=admin.most_prescribed_medicines(), totals=admin.totals(),
                               activity=data.activity_for("admin", me["id"], 10))
    upcoming = [a for a in appointments.patient_appointments(me["id"]) if a["status"] in ("Pending", "Confirmed")]
    return render_template("home.html", reports=reports.list_reports(me["id"])[:3],
                           report_count=len(data.reports[me["id"]]), upcoming=upcoming,
                           schedule=prescriptions.todays_reminders(me["id"]),
                           recent_rx=prescriptions.history(me["id"])[:3],
                           activity=data.activity_for("patient", me["id"]))


# ------------------------------------------------------------------ report files (patient and doctor)
@app.get("/uploads/<path:filename>")
def uploaded_file(filename):
    role, me = current_user()
    report = next((r for r in data.report_by_id.values() if r["filename"] == filename), None)
    if not reports.can_view(role, me["id"], report):
        abort(404)
    return send_from_directory(UPLOAD_DIR, filename)


@app.get("/report/<rid>")
def view_report(rid):
    role, me = current_user()
    report = data.report_by_id.get(rid)
    if not reports.can_view(role, me["id"], report):
        abort(404)
    ext = report["filename"].rsplit(".", 1)[-1].lower() if report["filename"] else None
    back = url_for("reports") if role == "patient" else url_for("doctor_patients", patient=report["patient_id"])
    return render_template("report.html", r=report, ext=ext, back=back, patient=data.patients[report["patient_id"]],
                           can_change=reports.can_change_file(role, me["id"], report))


@app.post("/report/<rid>/file")
def attach_report_file(rid):
    role, me = current_user()
    report = data.report_by_id.get(rid)
    if not reports.can_change_file(role, me["id"], report):
        abort(404)
    filename, error = save_upload()
    if error or not filename:
        flash(error or "Choose a PDF, PNG or JPG file first.", "error")
    else:
        report["filename"] = filename
        flash("File attached.", "ok")
    return redirect(url_for("view_report", rid=rid))


@app.get("/api/medicines")
def api_medicines():
    return jsonify(prescriptions.suggest(request.args.get("q", "")))


# ================================================================== PATIENT
@app.get("/reports", endpoint="reports")
def reports_page():
    me, a = current_user()[1], request.args
    if a.get("on_date"):
        items = reports.reports_on_date(me["id"], a["on_date"])
    else:
        items = reports.list_reports(me["id"], a.get("q", ""), a.get("type", ""), a.get("sort", "date"),
                                     a.get("order", "desc"), a.get("from", ""), a.get("to", ""))
    return render_template("reports.html", items=items, types=reports.REPORT_TYPES, args=a,
                           total=len(data.reports[me["id"]]))


@app.post("/reports/upload")
def upload_report():
    report_from_form(current_user()[1]["id"])
    return redirect(url_for("reports"))


@app.post("/reports/<rid>/delete")
def delete_report(rid):
    me, report = current_user()[1], data.report_by_id.get(rid)
    if not report or report["patient_id"] != me["id"] or report["uploaded_by"]:
        flash("You can only delete reports you uploaded yourself.", "error")
    else:
        reports.delete_report(report)
        flash(f"Deleted '{report['title']}'.", "ok")
    return redirect(url_for("reports"))


@app.get("/appointments", endpoint="appointments")
def appointments_page():
    me = current_user()[1]
    doctors = users.all_doctors()
    return render_template("appointments.html", doctors=doctors,
                           slots={d["id"]: appointments.bookable_slots(d["id"]) for d in doctors},
                           mine=appointments.patient_appointments(me["id"]),
                           waiting=[w for d in doctors for w in data.waitlist[d["id"]].to_list()
                                    if w["patient_id"] == me["id"]],
                           priorities=appointments.PRIORITY_LABELS, selected=request.args.get("doctor"))


@app.post("/appointments/book")
def book():
    me, did = current_user()[1], request.form.get("doctor_id")
    if did not in data.doctors:
        flash("Please choose a doctor.", "error")
        return redirect(url_for("appointments"))
    slot = request.form.get("slot", "")
    if slot and slot not in [s for s, fee in appointments.bookable_slots(did)]:
        flash("That slot is no longer free. Please pick another.", "error")
        return redirect(url_for("appointments", doctor=did))
    status, appt = appointments.book(me["id"], did, slot, number(request.form.get("priority"), 3, 1, 3),
                                     request.form.get("reason", "").strip() or "General consultation")
    doctor = data.doctors[did]["name"]
    flash({"confirmed": f"Confirmed with {doctor}. Pay the fee at the clinic.",
           "pending": f"Request sent to {doctor}. You'll see it here once they accept.",
           "waitlisted": "No free slot, so you've joined the waiting list. You'll get the first slot that frees up."}
          [status], "ok" if status == "confirmed" else "info")
    return redirect(url_for("appointments", doctor=did))


@app.post("/appointments/<aid>/cancel")
def cancel(aid):
    appt = appointments.cancel(aid, current_user()[1]["id"])
    flash("Appointment cancelled." if appt else "Could not cancel.", "ok" if appt else "error")
    return redirect(url_for("appointments"))


@app.get("/prescriptions", endpoint="prescriptions")
def prescriptions_page():
    me = current_user()[1]
    history = prescriptions.history(me["id"])
    chosen = data.rx_by_id.get(request.args.get("rx", ""))
    if not chosen or chosen["patient_id"] != me["id"]:
        chosen = history[0] if history else None
    return render_template("prescriptions.html", history=history, chosen=chosen,
                           schedule=prescriptions.todays_reminders(me["id"]), is_active=prescriptions.is_active,
                           rx_running=lambda rx: any(prescriptions.is_active(rx, it) for it in rx["items"]),
                           new_since=(date.today() - timedelta(days=3)).isoformat())


@app.get("/stores", endpoint="stores")
def stores_page():
    me = current_user()[1]
    origin = request.args.get("from") if request.args.get("from") in stores.places() else me["location"]
    use_rx = request.args.get("rx", "1") == "1"
    needed = prescriptions.current_medicines(me["id"]) if use_rx else []
    results = stores.nearest_stores(origin, needed)
    selected = request.args.get("store") or results[0]["store"]["id"]
    chosen = next((r for r in results if r["store"]["id"] == selected), None)
    return render_template("stores.html", results=results, origin=origin, places=stores.places(), needed=needed,
                           use_rx=use_rx, chosen=chosen, graph=dict(pos=stores.city.pos, edges=stores.city.all_roads()))


# ================================================================== DOCTOR
@app.post("/doctor/auto-accept")
def doctor_auto_accept():
    on = request.form.get("on") == "1"
    appointments.set_auto_accept(current_user()[1]["id"], on)
    flash("Auto-accept is ON: new bookings are confirmed instantly." if on else
          "Auto-accept is OFF: you'll accept or reject each booking.", "ok")
    return redirect(url_for("home"))


@app.post("/doctor/requests/<aid>/<action>")
def doctor_request(aid, action):
    did = current_user()[1]["id"]
    appt = appointments.accept(aid, did) if action == "accept" else appointments.reject(aid, did)
    flash(("Accepted. You can now open this patient's reports." if action == "accept" else
           "Request declined; the slot went to the waiting list or back to free.") if appt else
          "That request was already handled.", "ok" if appt else "info")
    return redirect(url_for("home"))


@app.post("/doctor/next")
def doctor_next():
    appt = appointments.call_next(current_user()[1]["id"])
    if appt:
        flash(f"Now seeing {data.patients[appt['patient_id']]['name']} ({appt['priority_label']}): "
              f"{appt['reason']}", "ok")
    else:
        flash("Queue is empty.", "info")
    return redirect(url_for("home"))


@app.route("/doctor/slots", methods=["GET", "POST"])
def doctor_slots():
    me = current_user()[1]
    day = request.values.get("day") or (date.today() + timedelta(days=1)).isoformat()
    if not valid_date(day) or day < date.today().isoformat():
        flash("Pick today or a future date.", "error")
        return redirect(url_for("doctor_slots"))
    if request.method == "POST":
        times = [t for t in request.form.getlist("times") if t in appointments.DAY_TIMES]
        fee = number(request.form.get("fee"), me["fee"], 0, 100000)
        appointments.set_day_slots(me["id"], day, times, fee)
        flash(f"Saved {len(times)} slot(s) for {day} at ₹{fee}.", "ok")
        return redirect(url_for("doctor_slots", day=day))
    view = appointments.day_view(me["id"], day)
    fee = next((f for t, state, f in view if f is not None), me["fee"])
    return render_template("doctor_slots.html", day=day, view=view, fee=fee, days=appointments.upcoming_days(me["id"]))


def my_patient(pid):
    """The patient, if this doctor has an accepted booking with them."""
    if pid not in data.patients or not appointments.has_access(current_user()[1]["id"], pid):
        abort(404)
    return data.patients[pid]


@app.get("/doctor/patients")
def doctor_patients():
    me = current_user()[1]
    patients = appointments.doctor_patients(me["id"])
    pid = request.args.get("patient") or (patients[0]["id"] if patients else None)
    patient = data.patients[pid] if pid and appointments.has_access(me["id"], pid) else None
    return render_template("doctor_patients.html", patients=patients, patient=patient,
                           reports=reports.list_reports(pid) if patient else [],
                           history=prescriptions.history(pid) if patient else [],
                           types=reports.REPORT_TYPES, frequencies=FREQUENCIES)


@app.post("/doctor/patients/<pid>/report")
def doctor_upload_report(pid):
    my_patient(pid)
    me = current_user()[1]
    report_from_form(pid, doctor=me["name"], uploaded_by=me["id"])
    return redirect(url_for("doctor_patients", patient=pid))


@app.post("/doctor/patients/<pid>/prescribe")
def doctor_prescribe(pid):
    patient, f = my_patient(pid), request.form
    items = [dict(medicine=med.strip()[:100], dose=dose.strip()[:50] or "1 tablet",
                  frequency=freq if freq in FREQUENCIES else FREQUENCIES[0], days=number(days, 1, 1, 365))
             for med, dose, freq, days in zip(f.getlist("medicine"), f.getlist("dose"),
                                              f.getlist("frequency"), f.getlist("days")) if med.strip()]
    if items:
        prescriptions.add_prescription(pid, current_user()[1]["id"], items, f.get("notes", ""))
        flash(f"Prescription sent to {patient['name']}. It's on their Prescriptions page now.", "ok")
    else:
        flash("Add at least one medicine.", "error")
    return redirect(url_for("doctor_patients", patient=pid))


@app.post("/doctor/patients/<pid>/undo")
def doctor_undo(pid):
    my_patient(pid)
    rx = prescriptions.withdraw_newest(pid, current_user()[1]["id"])
    flash(f"Withdrew the prescription from {rx['date']}." if rx else
          "Only the newest prescription can be withdrawn, and only by the doctor who wrote it.",
          "ok" if rx else "info")
    return redirect(url_for("doctor_patients", patient=pid))


if __name__ == "__main__":
    app.run(debug=True)
