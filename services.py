"""
Service layer: all app data lives here, inside OUR OWN data structures.
Flask routes (app.py) only call methods on the `CareMate` object.

Three kinds of users: patients, doctors and admins.

Feature -> data structure map
  Patients / doctors / admins / stores .... HashTable
  Reports library ......................... DoublyLinkedList (+ BST index by date)
  Report sort / search .................... merge_sort, binary_search, linear_search
  Booking requests awaiting the doctor .... DoublyLinkedList (accept/reject any one, O(1) add)
  Doctor's patient queue (triage) ......... MinHeap priority queue
  Waiting list when slots are full ........ Queue (FIFO)
  Free time slots ......................... sorted list + binary_search, fee per slot in a HashTable
  Prescription history + undo ............. Stack (LIFO)
  Medicine autocomplete ................... Trie
  Nearest medical store ................... Graph + Dijkstra, quick_sort by distance
  Most booked doctors / medicines ......... HashTable counting + MinHeap top-k

Storage: if a database `db` is given (Supabase Postgres), every change is ALSO
written to it, and on startup `restore()` loads the rows back into these same
data structures. The database never answers the app's queries.
"""

from datetime import date, datetime, timedelta
from itertools import count

from sample_reports import ensure_sample_file
from dsa import (BST, DoublyLinkedList, Graph, HashTable, MinHeap, Queue, Stack,
                 Trie, binary_search, linear_search, merge_sort, quick_sort, top_k)

PRIORITY_LABELS = {1: "Emergency", 2: "Urgent", 3: "Routine"}
REPORT_TYPES = ["Blood Test", "X-Ray", "MRI / CT Scan", "ECG", "Urine Test", "Discharge Summary", "Other"]
HOLDS_SLOT = ("Pending", "Confirmed", "Completed")      # these statuses keep the slot taken
GIVES_ACCESS = ("Confirmed", "Completed")               # doctor may see the patient's reports
DAY_TIMES = [f"{h:02d}:{m:02d}" for h in range(8, 20) for m in (0, 30)]   # 08:00 .. 19:30
FREQ_TIMES = {"Once a day": ["09:00"], "Twice a day": ["09:00", "21:00"],
              "Thrice a day": ["08:00", "14:00", "20:00"], "At bedtime": ["22:00"],
              "As needed": ["When required"]}


def now_slot():
    return datetime.now().strftime("%Y-%m-%d %H:%M")


class CareMate:
    def __init__(self, db=None):
        self._ids = count(1)
        self.db = db                        # database storage (None = in memory only)
        self._restoring = False             # True while loading rows back from the database

        self.patients = HashTable()
        self.doctors = HashTable()
        self.admins = HashTable()
        self.stores = HashTable()

        self.reports = HashTable()          # patient_id -> DoublyLinkedList of reports
        self.report_index = HashTable()     # patient_id -> BST keyed by date
        self.report_by_id = HashTable()     # report_id  -> report

        self.free_slots = HashTable()       # doctor_id -> sorted list of free slot strings
        self.slot_fee = HashTable()         # "doctor_id|slot" -> fee
        self.pending = HashTable()          # doctor_id -> DoublyLinkedList of requests to accept/reject
        self.doctor_queue = HashTable()     # doctor_id -> MinHeap of confirmed appointments
        self.waitlist = HashTable()         # doctor_id -> Queue of waiting requests
        self.appointments = HashTable()     # appt_id   -> appointment

        self.prescriptions = HashTable()    # patient_id -> Stack of prescriptions
        self.rx_by_id = HashTable()         # prescription_id -> prescription
        self.medicine_trie = Trie()

        self.city = Graph()
        self.activity = Stack()             # activity log (newest on top)

    # ================================================================ STORAGE HELPERS
    def _save(self, table, ignore=False, **row):
        if self.db and not self._restoring:
            self.db.insert(table, row, ignore)

    def _update(self, table, fields, **where):
        if self.db and not self._restoring:
            self.db.update(table, fields, **where)

    def _delete(self, table, **where):
        if self.db and not self._restoring:
            self.db.delete(table, **where)

    def _next_id(self, prefix):
        return f"{prefix}{next(self._ids)}"

    def log(self, text, patient_id=None, doctor_id=None):
        if self._restoring:
            return
        self.activity.push(dict(text=text, patient_id=patient_id, doctor_id=doctor_id))
        self._save("activity_log", message=text[:255], patient_id=patient_id, doctor_id=doctor_id)

    def activity_for(self, role, uid, limit=6):
        """Patients and doctors see their own events; the admin sees everything."""
        out = []
        for e in self.activity.to_list():               # newest first (stack)
            if role == "admin" or e.get(f"{role}_id") == uid:
                out.append(e["text"])
                if len(out) == limit:
                    break
        return out

    # ================================================================ USERS
    def add_patient(self, name, age, gender, blood_group, location, phone="", active=True, pid=None):
        pid = pid or self._next_id("P")
        patient = dict(id=pid, name=name, age=age, gender=gender, blood_group=blood_group,
                       location=location, phone=phone, active=active)
        self.patients.put(pid, patient)
        self.reports.put(pid, DoublyLinkedList())
        self.report_index.put(pid, BST())
        self.prescriptions.put(pid, Stack())
        self._save("patients", **patient)
        return pid

    def add_doctor(self, name, specialty, clinic, fee=500, auto_accept=True, phone="",
                   active=True, did=None):
        did = did or self._next_id("D")
        doctor = dict(id=did, name=name, specialty=specialty, clinic=clinic, fee=fee,
                      auto_accept=auto_accept, phone=phone, active=active)
        self.doctors.put(did, doctor)
        self.free_slots.put(did, [])
        self.pending.put(did, DoublyLinkedList())
        self.doctor_queue.put(did, MinHeap())
        self.waitlist.put(did, Queue())
        self._save("doctors", **doctor)
        return did

    def add_admin(self, name, active=True, aid=None):
        aid = aid or self._next_id("AD")
        admin = dict(id=aid, name=name, active=active)
        self.admins.put(aid, admin)
        self._save("admins", **admin)
        return aid

    def _table_of(self, uid):
        for role, table, db_table in (("patient", self.patients, "patients"),
                                      ("doctor", self.doctors, "doctors"),
                                      ("admin", self.admins, "admins")):
            if uid and table.contains(uid):
                return role, table, db_table
        return None, None, None

    def role_of(self, uid):
        return self._table_of(uid)[0]

    def user(self, uid):
        table = self._table_of(uid)[1]
        return table.get(uid) if table else None

    def update_user(self, uid, **fields):
        role, table, db_table = self._table_of(uid)
        if not role:
            return None
        table.get(uid).update(fields)
        self._update(db_table, fields, id=uid)
        return table.get(uid)

    def _people(self, table, active_only):
        return merge_sort([u for u in table.values() if u["active"] or not active_only],
                          key=lambda u: u["name"])

    def all_patients(self, active_only=False):
        return self._people(self.patients, active_only)

    def all_doctors(self, active_only=False):
        return self._people(self.doctors, active_only)

    def all_admins(self, active_only=False):
        return self._people(self.admins, active_only)

    # ================================================================ REPORTS
    def add_report(self, patient_id, title, rtype, rdate, doctor="", notes="", filename=None,
                   uploaded_by=None, rid=None):
        rid = rid or self._next_id("R")
        report = dict(id=rid, patient_id=patient_id, title=title, type=rtype, date=rdate,
                      doctor=doctor, notes=notes, filename=filename, uploaded_by=uploaded_by)
        self.reports.get(patient_id).add_first(report)           # O(1) newest first
        self.report_index.get(patient_id).insert(rdate, report)   # BST by date
        self.report_by_id.put(rid, report)
        self._save("reports", **report)
        who = self.doctors.get(uploaded_by)["name"] if uploaded_by else "you"
        self.log(f"Report '{title}' added by {who}", patient_id, uploaded_by)
        return rid

    def attach_file(self, report_id, filename):
        """Attach (or replace) the file of an existing report."""
        report = self.report_by_id.get(report_id)
        if report and filename:
            report["filename"] = filename
            self._update("reports", dict(filename=filename), id=report_id)
        return report

    def can_view_report(self, role, uid, report):
        """The patient who owns it, or a doctor whose booking with that patient was accepted."""
        return bool(report) and ((role == "patient" and report["patient_id"] == uid) or
                                 (role == "doctor" and self.has_access(uid, report["patient_id"])))

    def can_change_file(self, role, uid, report):
        """Attach a file if there is none; only the uploader may REPLACE an existing one."""
        if not self.can_view_report(role, uid, report):
            return False
        if not report["filename"]:
            return True
        uploader = report["uploaded_by"]            # None = the patient uploaded it
        return uploader == uid if role == "doctor" else uploader is None

    def delete_report(self, patient_id, report_id):
        report = self.reports.get(patient_id).remove(lambda r: r["id"] == report_id)
        if report:
            self.report_index.get(patient_id).remove_value(report["date"], lambda r: r["id"] == report_id)
            self.report_by_id.remove(report_id)
            self._delete("reports", id=report_id)
            self.log(f"Report '{report['title']}' deleted", patient_id)
        return report

    def list_reports(self, patient_id, query="", rtype="", sort_by="date",
                     order="desc", date_from="", date_to=""):
        # 1) Range query on the BST if a date range is given, else full linked-list traversal
        if date_from or date_to:
            items = self.report_index.get(patient_id).range_query(date_from or "0000-00-00",
                                                                  date_to or "9999-12-31")
        else:
            items = self.reports.get(patient_id).to_list()
        # 2) Linear search on keyword + filter on type
        items = linear_search(items, query, ["title", "notes", "doctor", "type"])
        if rtype:
            items = [r for r in items if r["type"] == rtype]
        # 3) Merge sort
        key = {"date": lambda r: r["date"], "title": lambda r: r["title"].lower(),
               "type": lambda r: r["type"]}.get(sort_by, lambda r: r["date"])
        return merge_sort(items, key=key, reverse=(order == "desc"))

    def find_report_on_date(self, patient_id, on_date):
        """Binary search on reports sorted by date (BST inorder already sorted)."""
        sorted_reports = self.report_index.get(patient_id).inorder()
        idx = binary_search(sorted_reports, on_date, key=lambda r: r["date"])
        if idx == -1:
            return []
        out = []
        while idx < len(sorted_reports) and sorted_reports[idx]["date"] == on_date:
            out.append(sorted_reports[idx]); idx += 1
        return out

    # ================================================================ DOCTOR SLOTS & FEES
    def _fee_key(self, did, slot):
        return f"{did}|{slot}"

    def taken_slots(self, did):
        # scans all appointments, O(n); an index by doctor would be faster at scale
        return {a["slot"] for a in self.appointments.values()
                if a["doctor_id"] == did and a["status"] in HOLDS_SLOT}

    def set_day_slots(self, did, day, times, fee):
        """The doctor picks which slots to offer on one day, and the fee.
        Slots somebody already booked are never removed."""
        wanted = {f"{day} {t}" for t in times}
        taken = self.taken_slots(did)
        keep = []
        for s in self.free_slots.get(did):
            if s.startswith(day) and s not in wanted:          # doctor unticked it
                self.slot_fee.remove(self._fee_key(did, s))
                self._delete("doctor_slots", doctor_id=did, slot=s)
            else:
                keep.append(s)
        for s in wanted - taken:
            if self.slot_fee.contains(self._fee_key(did, s)):  # already offered: new fee
                self._update("doctor_slots", dict(fee=fee), doctor_id=did, slot=s)
            else:
                keep.append(s)
                self._save("doctor_slots", doctor_id=did, slot=s, fee=fee)
            self.slot_fee.put(self._fee_key(did, s), fee)
        self.free_slots.put(did, merge_sort(keep))
        self.log(f"{self.doctors.get(did)['name']} updated slots for {day}", doctor_id=did)

    def day_view(self, did, day):
        """[(time, 'free' | 'booked' | 'off', fee)] for the slot editor:
        the standard half-hour grid plus any custom times the doctor added that day."""
        free = self.free_slots.get(did)
        taken = self.taken_slots(did)
        custom = {s[11:] for s in free if s.startswith(day)} | {s[11:] for s in taken if s.startswith(day)}
        out = []
        for t in merge_sort(list(set(DAY_TIMES) | custom)):
            s = f"{day} {t}"
            state = "booked" if s in taken else "free" if binary_search(free, s) != -1 else "off"
            out.append((t, state, self.slot_fee.get(self._fee_key(did, s))))
        return out

    def upcoming_days(self, did):
        """Per day from today on: how many slots are free / booked, and the fee."""
        today = date.today().isoformat()
        days = {}
        for s in self.free_slots.get(did):
            if s[:10] >= today:
                days.setdefault(s[:10], [0, 0, self.slot_fee.get(self._fee_key(did, s))])[0] += 1
        for s in self.taken_slots(did):
            if s[:10] >= today:
                days.setdefault(s[:10], [0, 0, self.slot_fee.get(self._fee_key(did, s))])[1] += 1
        return [(d, *days[d]) for d in merge_sort(list(days))]

    def bookable_slots(self, did):
        """Free slots that are still in the future, with their fee."""
        now = now_slot()
        return [(s, self.slot_fee.get(self._fee_key(did, s), self.doctors.get(did)["fee"]))
                for s in self.free_slots.get(did) if s > now]

    # ================================================================ APPOINTMENTS
    def book_appointment(self, patient_id, doctor_id, slot, priority, reason):
        """Returns (status, appointment_or_None). status: 'confirmed' | 'pending' | 'waitlisted'."""
        slots = self.free_slots.get(doctor_id)
        idx = binary_search(slots, slot) if slot else -1
        if idx == -1:
            # no free slot chosen -> FIFO waiting list
            w = dict(id=self._next_id("W"), doctor_id=doctor_id, patient_id=patient_id,
                     priority=priority, reason=reason, requested=slot or "Any")
            self.waitlist.get(doctor_id).enqueue(w)
            self._save("waitlist", **w)
            self.log(f"{self.patients.get(patient_id)['name']} joined "
                     f"{self.doctors.get(doctor_id)['name']}'s waiting list", patient_id, doctor_id)
            return "waitlisted", None
        slots.pop(idx)
        appt = self._create_appointment(patient_id, doctor_id, slot, priority, reason)
        return appt["status"].lower(), appt

    def _create_appointment(self, patient_id, doctor_id, slot, priority, reason):
        doctor = self.doctors.get(doctor_id)
        aid = self._next_id("A")
        appt = dict(id=aid, patient_id=patient_id, doctor_id=doctor_id, slot=slot,
                    fee=self.slot_fee.get(self._fee_key(doctor_id, slot), doctor["fee"]),
                    priority=priority, reason=reason,
                    status="Confirmed" if doctor["auto_accept"] else "Pending")
        self.appointments.put(aid, appt)
        self._save("appointments", **appt)
        self._place(appt)
        self.log(f"{self.patients.get(patient_id)['name']} booked {doctor['name']} at {slot} "
                 f"({PRIORITY_LABELS[priority]}): {appt['status'].lower()}", patient_id, doctor_id)
        return appt

    def _place(self, appt):
        """Put an appointment into the right structure for its status."""
        appt["priority_label"] = PRIORITY_LABELS[appt["priority"]]
        if appt["status"] == "Pending":
            self.pending.get(appt["doctor_id"]).add_last(appt)
        elif appt["status"] == "Confirmed":
            # priority key = (day, urgency, time): earlier days first; within a day emergencies
            # first, then the earliest slot (ties keep booking order)
            self.doctor_queue.get(appt["doctor_id"]).push((appt["slot"][:10], appt["priority"], appt["slot"]), appt)

    def _set_status(self, appt, status):
        appt["status"] = status
        self._update("appointments", dict(status=status), id=appt["id"])

    def accept_appointment(self, appt_id, doctor_id):
        appt = self.appointments.get(appt_id)
        if not appt or appt["doctor_id"] != doctor_id or appt["status"] != "Pending":
            return None
        self.pending.get(doctor_id).remove(lambda a: a["id"] == appt_id)
        self._set_status(appt, "Confirmed")
        self._place(appt)
        self.log(f"{self.doctors.get(doctor_id)['name']} accepted "
                 f"{self.patients.get(appt['patient_id'])['name']} for {appt['slot']}",
                 appt["patient_id"], doctor_id)
        return appt

    def reject_appointment(self, appt_id, doctor_id):
        appt = self.appointments.get(appt_id)
        if not appt or appt["doctor_id"] != doctor_id or appt["status"] != "Pending":
            return None
        self.pending.get(doctor_id).remove(lambda a: a["id"] == appt_id)
        self._set_status(appt, "Rejected")
        self.log(f"{self.doctors.get(doctor_id)['name']} could not take the {appt['slot']} request",
                 appt["patient_id"], doctor_id)
        self._free_slot(doctor_id, appt["slot"])
        return appt

    def cancel_appointment(self, appt_id, patient_id):
        appt = self.appointments.get(appt_id)
        if not appt or appt["patient_id"] != patient_id or appt["status"] not in ("Pending", "Confirmed"):
            return None
        did = appt["doctor_id"]
        if appt["status"] == "Pending":
            self.pending.get(did).remove(lambda a: a["id"] == appt_id)
        else:
            self.doctor_queue.get(did).remove(lambda a: a["id"] == appt_id)
        self._set_status(appt, "Cancelled")
        self.log(f"Appointment {appt['slot']} cancelled", patient_id, did)
        self._free_slot(did, appt["slot"])
        return appt

    def _free_slot(self, did, slot):
        """A slot opened up: the FRONT of the waiting list gets it, else it is free again."""
        wl = self.waitlist.get(did)
        if not wl.is_empty() and slot > now_slot():
            w = wl.dequeue()
            self._delete("waitlist", id=w["id"])
            self._create_appointment(w["patient_id"], did, slot, w["priority"], w["reason"])
        else:
            slots = self.free_slots.get(did)
            slots.append(slot)
            self.free_slots.put(did, merge_sort(slots))

    def call_next_patient(self, doctor_id):
        appt = self.doctor_queue.get(doctor_id).pop()
        if appt:
            self._set_status(appt, "Completed")
            self.log(f"{self.doctors.get(doctor_id)['name']} saw "
                     f"{self.patients.get(appt['patient_id'])['name']}", appt["patient_id"], doctor_id)
        return appt

    def set_auto_accept(self, doctor_id, on):
        self.update_user(doctor_id, auto_accept=on)
        if on:                                          # accept everything already waiting
            for appt in self.pending.get(doctor_id).to_list():
                self.accept_appointment(appt["id"], doctor_id)

    def patient_appointments(self, patient_id):
        items = [a for a in self.appointments.values() if a["patient_id"] == patient_id]
        return merge_sort(items, key=lambda a: a["slot"])

    def pending_requests(self, doctor_id):
        return self.pending.get(doctor_id).to_list()      # oldest request first

    def doctor_queue_view(self, doctor_id):
        return self.doctor_queue.get(doctor_id).sorted_items()

    def has_access(self, doctor_id, patient_id):
        """A doctor may open a patient's reports once that patient's booking is accepted."""
        return any(a["doctor_id"] == doctor_id and a["patient_id"] == patient_id
                   and a["status"] in GIVES_ACCESS for a in self.appointments.values())

    def doctor_patients(self, doctor_id):
        ids = {a["patient_id"] for a in self.appointments.values()
               if a["doctor_id"] == doctor_id and a["status"] in GIVES_ACCESS}
        return merge_sort([self.patients.get(p) for p in ids], key=lambda p: p["name"])

    # ================================================================ PRESCRIPTIONS
    def add_medicine_name(self, name):
        self.medicine_trie.insert(name)
        self._save("medicines", ignore=True, name=name)

    def suggest_medicines(self, prefix):
        return self.medicine_trie.starts_with(prefix, limit=8)

    def add_prescription(self, patient_id, doctor_id, items, notes="", pdate=None, rx_id=None):
        rx = dict(id=rx_id or self._next_id("RX"), patient_id=patient_id, doctor_id=doctor_id,
                  date=pdate or date.today().isoformat(), items=items, notes=notes)
        self._save("prescriptions", id=rx["id"], patient_id=patient_id, doctor_id=doctor_id,
                   date=rx["date"], notes=notes)
        for it in items:
            self.add_medicine_name(it["medicine"])       # learn new medicine names
            self._save("prescription_items", prescription_id=rx["id"], **it)
        self.prescriptions.get(patient_id).push(rx)
        self.rx_by_id.put(rx["id"], rx)
        self.log(f"{self.doctors.get(doctor_id)['name']} sent a prescription to "
                 f"{self.patients.get(patient_id)['name']}", patient_id, doctor_id)
        return rx

    def undo_last_prescription(self, patient_id, doctor_id):
        """A doctor can take back the newest prescription only if they wrote it."""
        stack = self.prescriptions.get(patient_id)
        top = stack.peek()
        if not top or top["doctor_id"] != doctor_id:
            return None
        rx = stack.pop()
        self.rx_by_id.remove(rx["id"])
        self._delete("prescriptions", id=rx["id"])   # its items go too (ON DELETE CASCADE)
        self.log(f"Prescription {rx['id']} withdrawn", patient_id, doctor_id)
        return rx

    def prescription_history(self, patient_id):
        return self.prescriptions.get(patient_id).to_list()   # newest first

    @staticmethod
    def is_active(rx, item, today=None):
        """A medicine is taken for `days` days starting on the prescription date."""
        today = today or date.today()
        start = date.fromisoformat(rx["date"])
        return start <= today < start + timedelta(days=int(item["days"]))

    def active_items(self, patient_id):
        return [(rx, it) for rx in self.prescription_history(patient_id)
                for it in rx["items"] if self.is_active(rx, it)]

    def daily_schedule(self, patient_id):
        """Today's reminders from EVERY medicine that is still running."""
        out = []
        for rx, it in self.active_items(patient_id):
            for t in FREQ_TIMES.get(it["frequency"], ["09:00"]):
                out.append(dict(time=t, medicine=it["medicine"], dose=it["dose"],
                                doctor_id=rx["doctor_id"]))
        return merge_sort(out, key=lambda x: x["time"])

    def current_medicines(self, patient_id):
        seen, out = set(), []
        for _, it in self.active_items(patient_id):
            if it["medicine"].lower() not in seen:
                seen.add(it["medicine"].lower())
                out.append(it["medicine"])
        return out

    # ================================================================ MEDICAL STORES
    def add_place(self, name, x, y):
        self.city.add_vertex(name, x, y)
        self._save("places", name=name, x=x, y=y)

    def add_road(self, a, b, km):
        self.city.add_edge(a, b, km)
        self._save("roads", place_a=a, place_b=b, km=km)

    def add_store(self, name, node, hours, phone, stock, sid=None):
        sid = sid or self._next_id("S")
        self.stores.put(sid, dict(id=sid, name=name, node=node, hours=hours, phone=phone,
                                  stock=set(m.lower() for m in stock)))
        self._save("stores", id=sid, name=name, node=node, hours=hours, phone=phone)
        for m in set(stock):
            self._save("store_stock", ignore=True, store_id=sid, medicine=m)
        return sid

    def nearest_stores(self, from_place, needed=None):
        dist, prev = self.city.dijkstra(from_place)
        needed = [m.lower() for m in (needed or [])]
        results = []
        for s in self.stores.values():
            d = dist.get(s["node"], float("inf"))
            have = [m for m in needed if m in s["stock"]]
            results.append(dict(store=s, distance=round(d, 1),
                                path=Graph.build_path(prev, s["node"]),
                                has_all=len(have) == len(needed), available=len(have),
                                missing=[m for m in needed if m not in s["stock"]]))
        # stores that stock everything first, then by distance (quick sort)
        return quick_sort(results, key=lambda r: (not r["has_all"], r["distance"]))

    def places(self):
        return merge_sort([v for v in self.city.adj if not v.startswith("store:")])

    # ================================================================ ADMIN INSIGHTS
    def most_booked_doctors(self, k=5):
        counts = HashTable()
        for a in self.appointments.values():
            if a["status"] in HOLDS_SLOT:
                counts.put(a["doctor_id"], counts.get(a["doctor_id"], 0) + 1)
        return [(self.doctors.get(did), n) for did, n in top_k(counts.items(), k)]

    def most_prescribed_medicines(self, k=5):
        counts = HashTable()
        for stack in self.prescriptions.values():
            for rx in stack.to_list():
                for it in rx["items"]:
                    counts.put(it["medicine"], counts.get(it["medicine"], 0) + 1)
        return top_k(counts.items(), k)

    def platform_totals(self):
        by_status = HashTable()
        for a in self.appointments.values():
            by_status.put(a["status"], by_status.get(a["status"], 0) + 1)
        return dict(patients=len(self.patients), doctors=len(self.doctors),
                    appointments=len(self.appointments),
                    pending=by_status.get("Pending", 0), confirmed=by_status.get("Confirmed", 0),
                    completed=by_status.get("Completed", 0),
                    fees=sum(float(a["fee"]) for a in self.appointments.values()
                             if a["status"] == "Completed"),
                    prescriptions=sum(len(s) for s in self.prescriptions.values()))

    # ================================================================ DASHBOARD
    def dsa_stats(self):
        return {
            "Storage": f"Supabase Postgres ({self.db.name})" if self.db else "In memory (no database)",
            "Patients (HashTable)": self.patients.stats(),
            "Doctors (HashTable)": self.doctors.stats(),
            "Stores (HashTable)": self.stores.stats(),
            "Medicines in Trie": len(self.medicine_trie),
            "City graph": {"vertices": len(self.city.adj), "roads": len(self.city.edges())},
        }

    # ================================================================ LOAD FROM THE DATABASE
    def restore(self):
        """Rebuild every data structure from the database rows.
        Rows are replayed in creation order (the number inside each id), so the
        linked lists, stacks, queues and heaps end up in exactly the same order."""
        db = self.db
        self._restoring = True                       # no logging / no re-saving while loading

        def by_id(rows):
            return merge_sort(rows, key=lambda r: _num(r["id"]))

        def group(rows, key):
            out = {}
            for r in rows:
                out.setdefault(r[key], []).append(r)
            return out

        for p in db.all("places"):
            self.add_place(p["name"], p["x"], p["y"])
        for r in db.all("roads"):
            self.add_road(r["place_a"], r["place_b"], float(r["km"]))
        stock = group(db.all("store_stock"), "store_id")
        for s in by_id(db.all("stores")):
            self.add_store(s["name"], s["node"], s["hours"], s["phone"],
                           [m["medicine"] for m in stock.get(s["id"], [])], sid=s["id"])
        for m in db.all("medicines"):
            self.add_medicine_name(m["name"])

        for p in by_id(db.all("patients")):
            self.add_patient(p["name"], p["age"], p["gender"], p["blood_group"], p["location"],
                             p["phone"], p["active"], pid=p["id"])
        for d in by_id(db.all("doctors")):
            self.add_doctor(d["name"], d["specialty"], d["clinic"], float(d["fee"]),
                            d["auto_accept"], d["phone"], d["active"], did=d["id"])
        for a in by_id(db.all("admins")):
            self.add_admin(a["name"], a["active"], aid=a["id"])

        for did, rows in group(db.all("doctor_slots"), "doctor_id").items():
            for r in rows:
                self.slot_fee.put(self._fee_key(did, r["slot"]), float(r["fee"]))
            self.free_slots.put(did, merge_sort([r["slot"] for r in rows]))

        for r in by_id(db.all("reports")):
            self.add_report(r["patient_id"], r["title"], r["type"], r["date"].isoformat(),
                            r["doctor"], r["notes"], r["filename"], r["uploaded_by"], rid=r["id"])

        # free slots = offered slots minus those held by an appointment
        for a in by_id(db.all("appointments")):
            appt = dict(a, fee=float(a["fee"]))
            self.appointments.put(a["id"], appt)
            if a["status"] in HOLDS_SLOT:
                free = self.free_slots.get(a["doctor_id"])
                idx = binary_search(free, a["slot"])
                if idx != -1:
                    free.pop(idx)
            self._place(appt)
        for w in by_id(db.all("waitlist")):
            self.waitlist.get(w["doctor_id"]).enqueue(w)

        items = group(merge_sort(db.all("prescription_items"), key=lambda i: i["id"]), "prescription_id")
        for rx in by_id(db.all("prescriptions")):
            rx_items = [dict(medicine=i["medicine"], dose=i["dose"], frequency=i["frequency"],
                             days=i["days"]) for i in items.get(rx["id"], [])]
            self.add_prescription(rx["patient_id"], rx["doctor_id"], rx_items, rx["notes"] or "",
                                  rx["date"].isoformat(), rx_id=rx["id"])

        for row in merge_sort(db.all("activity_log"), key=lambda r: r["id"]):
            self.activity.push(dict(text=row["message"], patient_id=row["patient_id"],
                                    doctor_id=row["doctor_id"]))

        # new ids continue after the biggest one already stored
        used = [_num(r["id"]) for t in ("patients", "doctors", "admins", "stores", "reports",
                                        "appointments", "waitlist", "prescriptions") for r in db.all(t)]
        self._ids = count(max(used, default=0) + 1)
        self._restoring = False


def _num(item_id):
    """'RX12' -> 12 (every id shares one global counter)."""
    return int(item_id.lstrip("ABCDEFGHIJKLMNOPQRSTUVWXYZ"))


def load(db):
    """In memory: demo data. With a database: seed demo data on the first run, then load rows."""
    if db is None:
        return build_demo()
    if db.is_empty():
        return build_demo(db)        # every add_* call also inserts into the database
    na = CareMate(db)
    na.restore()
    return na


# ====================================================================== SEED DATA
def build_demo(db=None):
    na = CareMate(db)
    today = date.today()

    def d(offset):
        return (today + timedelta(days=offset)).isoformat()

    # --- city graph (Pune-like localities; x,y only for drawing) ---
    places = {
        "Shivaji Nagar": (300, 200), "Deccan": (220, 260), "Kothrud": (100, 300),
        "Swargate": (330, 340), "Camp": (460, 260), "Koregaon Park": (540, 170),
        "Aundh": (170, 80), "Baner": (60, 120), "Hadapsar": (620, 360),
        "Katraj": (300, 470), "Viman Nagar": (640, 100), "Kalyani Nagar": (560, 60),
    }
    for p, (x, y) in places.items():
        na.add_place(p, x, y)
    roads = [
        ("Shivaji Nagar", "Deccan", 2.1), ("Shivaji Nagar", "Aundh", 5.0),
        ("Shivaji Nagar", "Camp", 4.2), ("Shivaji Nagar", "Swargate", 4.0),
        ("Deccan", "Kothrud", 4.5), ("Deccan", "Swargate", 3.2), ("Kothrud", "Baner", 7.5),
        ("Aundh", "Baner", 3.4), ("Camp", "Koregaon Park", 3.0), ("Camp", "Swargate", 4.4),
        ("Camp", "Hadapsar", 7.0), ("Koregaon Park", "Kalyani Nagar", 3.1),
        ("Koregaon Park", "Viman Nagar", 5.5), ("Kalyani Nagar", "Viman Nagar", 2.6),
        ("Swargate", "Katraj", 6.2), ("Katraj", "Hadapsar", 10.5), ("Hadapsar", "Viman Nagar", 9.0),
    ]
    for a, b, w in roads:
        na.add_road(a, b, w)

    stores = [
        ("Apollo Pharmacy", "Deccan", 250, 290, 0.6, "24 x 7", "020-2551 0001",
         ["Paracetamol 500mg", "Amoxicillin 500mg", "Cetirizine 10mg", "Pantoprazole 40mg", "ORS Sachet"]),
        ("MedPlus", "Camp", 490, 290, 0.8, "8 AM - 11 PM", "020-2633 0002",
         ["Paracetamol 500mg", "Metformin 500mg", "Amlodipine 5mg", "Atorvastatin 10mg", "Vitamin D3 60K"]),
        ("Wellness Forever", "Koregaon Park", 570, 200, 0.5, "24 x 7", "020-2615 0003",
         ["Paracetamol 500mg", "Amoxicillin 500mg", "Azithromycin 500mg", "Cetirizine 10mg",
          "Pantoprazole 40mg", "Metformin 500mg", "Vitamin D3 60K", "Thyroxine 25mcg"]),
        ("Noble Chemist", "Kothrud", 70, 330, 0.4, "9 AM - 10 PM", "020-2543 0004",
         ["Paracetamol 500mg", "Ibuprofen 400mg", "ORS Sachet", "Cetirizine 10mg"]),
        ("Jan Aushadhi Kendra", "Swargate", 360, 370, 0.7, "9 AM - 9 PM", "020-2444 0005",
         ["Paracetamol 500mg", "Metformin 500mg", "Amlodipine 5mg", "Amoxicillin 500mg",
          "Atorvastatin 10mg", "Pantoprazole 40mg", "Thyroxine 25mcg"]),
        ("Aundh Medicals", "Aundh", 245, 100, 0.3, "8 AM - 10 PM", "020-2588 0006",
         ["Ibuprofen 400mg", "Cetirizine 10mg", "Azithromycin 500mg", "Vitamin D3 60K"]),
    ]
    for name, near, x, y, km, hours, phone, stock in stores:
        node = f"store:{name}"
        na.add_place(node, x, y)
        na.add_road(near, node, km)
        na.add_store(name, node, hours, phone, stock)

    # --- medicines (Trie) ---
    for m in ["Paracetamol 500mg", "Pantoprazole 40mg", "Amoxicillin 500mg", "Azithromycin 500mg",
              "Amlodipine 5mg", "Atorvastatin 10mg", "Metformin 500mg", "Metoprolol 25mg",
              "Cetirizine 10mg", "Ibuprofen 400mg", "ORS Sachet", "Vitamin D3 60K",
              "Montelukast 10mg", "Omeprazole 20mg", "Losartan 50mg", "Levocetirizine 5mg",
              "Diclofenac 50mg", "Dolo 650", "Thyroxine 25mcg"]:
        na.add_medicine_name(m)

    # --- users ---
    p1 = na.add_patient("Aarav Sharma", 34, "Male", "B+", "Shivaji Nagar", "98200 11111")
    p2 = na.add_patient("Priya Deshmukh", 58, "Female", "O+", "Kalyani Nagar", "98200 22222")
    p3 = na.add_patient("Rohan Kulkarni", 22, "Male", "A-", "Kothrud", "98200 33333")
    # Dr. Meera accepts bookings by hand; the others auto-accept
    d1 = na.add_doctor("Dr. Meera Iyer", "General Physician", "City Care Clinic, Deccan",
                       fee=400, auto_accept=False, phone="98220 44444")
    d2 = na.add_doctor("Dr. Arjun Patil", "Cardiologist", "HeartLine Hospital, Camp",
                       fee=900, phone="98220 55555")
    d3 = na.add_doctor("Dr. Sana Khan", "Endocrinologist", "Sugar & Thyroid Centre, Aundh",
                       fee=700, phone="98220 66666")
    na.add_admin("Platform Admin")

    # --- each doctor picks the slots (and fee) for every day ---
    for day in (1, 2, 3):
        na.set_day_slots(d1, d(day), ["10:00", "11:00", "12:00", "17:00"], 400)
    for day in (1, 3):
        na.set_day_slots(d2, d(day), ["09:30", "15:00"], 900)
    for day in (2, 4):
        na.set_day_slots(d3, d(day), ["11:30", "16:30"], 700)

    # --- reports (some uploaded by the doctor after a test) ---
    na.add_report(p1, "Complete Blood Count", "Blood Test", d(-120), "Dr. Meera Iyer", "Hb 14.2, WBC normal")
    na.add_report(p1, "Chest X-Ray PA view", "X-Ray", d(-95), "Dr. Meera Iyer", "No active lesion")
    na.add_report(p1, "Lipid Profile", "Blood Test", d(-40), "Dr. Arjun Patil",
                  "LDL 142 mg/dL - borderline high", uploaded_by=d2)
    na.add_report(p1, "ECG - resting", "ECG", d(-40), "Dr. Arjun Patil", "Normal sinus rhythm", uploaded_by=d2)
    na.add_report(p1, "HbA1c", "Blood Test", d(-10), "Dr. Sana Khan", "HbA1c 6.1% - prediabetic range")
    na.add_report(p2, "Thyroid Profile", "Blood Test", d(-60), "Dr. Sana Khan", "TSH 5.8 - mildly raised")
    na.add_report(p2, "Knee MRI", "MRI / CT Scan", d(-30), "Dr. Meera Iyer", "Grade 2 osteoarthritis")
    na.add_report(p3, "Urine Routine", "Urine Test", d(-5), "Dr. Meera Iyer", "Normal")
    for r in na.report_by_id.values():           # a 2-page sample PDF for every demo report
        na.attach_file(r["id"], ensure_sample_file(r, na.patients.get(r["patient_id"])))

    # --- appointments (mixed priorities to show the heap) ---
    s = na.free_slots.get(d1)
    _, a1 = na.book_appointment(p2, d1, s[0], 3, "Knee pain follow-up")
    _, a2 = na.book_appointment(p3, d1, s[0], 2, "High fever for 3 days")   # s[0] is now the next slot
    na.accept_appointment(a1["id"], d1)
    na.accept_appointment(a2["id"], d1)
    na.book_appointment(p1, d1, s[-1], 3, "Persistent cough")               # left Pending for Dr. Meera
    na.book_appointment(p1, d2, na.free_slots.get(d2)[0], 3, "Review lipid profile")

    # --- prescriptions ---
    na.add_prescription(p1, d1, [
        dict(medicine="Paracetamol 500mg", dose="1 tablet", frequency="Thrice a day", days=3),
        dict(medicine="Cetirizine 10mg", dose="1 tablet", frequency="At bedtime", days=5),
    ], "Viral fever. Drink plenty of fluids.", d(-20))
    na.add_prescription(p1, d2, [
        dict(medicine="Atorvastatin 10mg", dose="1 tablet", frequency="At bedtime", days=30),
        dict(medicine="Metformin 500mg", dose="1 tablet", frequency="Twice a day", days=30),
    ], "Low-fat diet, 30 min walk daily. Repeat lipid profile after 3 months.", d(-9))
    na.add_prescription(p2, d1, [
        dict(medicine="Diclofenac 50mg", dose="1 tablet", frequency="Twice a day", days=5),
        dict(medicine="Pantoprazole 40mg", dose="1 tablet", frequency="Once a day", days=5),
    ], "Take after food.", d(-28))
    na.add_prescription(p2, d3, [
        dict(medicine="Thyroxine 25mcg", dose="1 tablet", frequency="Once a day", days=60),
    ], "Empty stomach, 30 min before breakfast. Recheck TSH in 6 weeks.", d(-2))

    return na
