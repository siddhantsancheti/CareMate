"""
CareMate: puts all the parts of the app together.

    users.py          -> patients, doctors, admins, sign-up and login
    reports.py        -> report library            (Doubly Linked List + BST)
    appointments.py   -> slots, booking, queues    (Queue + Priority Queue)
    prescriptions.py  -> prescriptions, reminders  (Stack)
    stores.py         -> nearest medical store     (Graph)
    admin.py          -> admin insights
    sorting_searching.py -> merge sort, quick sort, binary search, linear search

Flask routes (app.py) only call methods on the `CareMate` object.

Storage: if a database `db` is given (Supabase Postgres), every change is ALSO
written to it, and on startup `restore()` loads the rows back into these same
data structures. The database never answers the app's queries.
"""

from datetime import date, timedelta
from itertools import count

from admin import Admin
from appointments import HOLDS_SLOT, Appointments
from prescriptions import Prescriptions, Stack
from reports import Reports
from sample_reports import ensure_sample_file
from sorting_searching import binary_search, merge_sort
from stores import Graph, Stores
from users import Users


class CareMate(Users, Reports, Appointments, Prescriptions, Stores, Admin):
    def __init__(self, db=None):
        self._ids = count(1)
        self.db = db                        # database storage (None = in memory only)
        self._restoring = False             # True while loading rows back from the database

        self.patients = {}
        self.doctors = {}
        self.admins = {}
        self.by_email = {}         # email -> user id (for logging in)
        self.stores = {}

        self.reports = {}          # patient_id -> DoublyLinkedList of reports
        self.report_index = {}     # patient_id -> BST keyed by date
        self.report_by_id = {}     # report_id  -> report

        self.free_slots = {}       # doctor_id -> sorted list of free slot strings
        self.slot_fee = {}         # "doctor_id|slot" -> fee
        self.pending = {}          # doctor_id -> DoublyLinkedList of requests to accept/reject
        self.doctor_queue = {}     # doctor_id -> PriorityQueue of confirmed appointments
        self.waitlist = {}         # doctor_id -> Queue of waiting requests
        self.appointments = {}     # appt_id   -> appointment

        self.prescriptions = {}    # patient_id -> Stack of prescriptions
        self.rx_by_id = {}         # prescription_id -> prescription
        self.medicine_names = []          # sorted list of medicine names

        self.city = Graph()
        self.activity = Stack()             # activity log (newest on top)

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

    def restore(self):
        """Rebuild every data structure from the database rows.
        Rows are replayed in creation order (the number inside each id), so the
        linked lists, stacks and queues end up in exactly the same order."""
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
                             p["phone"], p["active"], pid=p["id"], email=p["email"], password_hash=p["password_hash"])
        for d in by_id(db.all("doctors")):
            self.add_doctor(d["name"], d["specialty"], d["clinic"], float(d["fee"]),
                            d["auto_accept"], d["phone"], d["active"], did=d["id"],
                            email=d["email"], password_hash=d["password_hash"])
        for a in by_id(db.all("admins")):
            self.add_admin(a["name"], a["active"], aid=a["id"], email=a["email"], password_hash=a["password_hash"])

        for did, rows in group(db.all("doctor_slots"), "doctor_id").items():
            for r in rows:
                self.slot_fee[self._fee_key(did, r["slot"])] = float(r["fee"])
            self.free_slots[did] = merge_sort([r["slot"] for r in rows])

        for r in by_id(db.all("reports")):
            self.add_report(r["patient_id"], r["title"], r["type"], r["date"].isoformat(),
                            r["doctor"], r["notes"], r["filename"], r["uploaded_by"], rid=r["id"])

        # free slots = offered slots minus those held by an appointment
        for a in by_id(db.all("appointments")):
            appt = dict(a, fee=float(a["fee"]))
            self.appointments[a["id"]] = appt
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
# Demo logins (shown in the README):
DEMO_ACCOUNTS = [
    ("patient", "siddhant@caremate.in", "siddhant123"),
    ("doctor", "arjun@caremate.in", "arjun123"),
    ("admin", "admin@caremate.in", "admin123"),
]


def build_demo(db=None):
    na = CareMate(db)
    today = date.today()

    def d(offset):
        return (today + timedelta(days=offset)).isoformat()

    pw = {email: na.hash_password(password) for _, email, password in DEMO_ACCOUNTS}

    # --- map of Kondhwa around VIIT (x,y only for drawing; distances are approximate road km) ---
    places = {
        "VIIT College": (330, 250), "Kondhwa Budruk": (420, 290), "Upper Indira Nagar": (235, 205),
        "Bibvewadi": (180, 130), "Katraj": (170, 380), "Kondhwa Khurd": (470, 170),
        "NIBM Road": (565, 205), "Salunke Vihar": (525, 95), "Yewalewadi": (430, 410), "Undri": (600, 330),
    }
    for p, (x, y) in places.items():
        na.add_place(p, x, y)
    roads = [
        ("VIIT College", "Upper Indira Nagar", 1.2), ("VIIT College", "Kondhwa Budruk", 1.0),
        ("VIIT College", "Katraj", 3.0), ("Upper Indira Nagar", "Bibvewadi", 1.5),
        ("Bibvewadi", "Katraj", 3.0), ("Kondhwa Budruk", "Kondhwa Khurd", 2.0),
        ("Kondhwa Budruk", "Yewalewadi", 2.0), ("Kondhwa Khurd", "NIBM Road", 1.8),
        ("Kondhwa Khurd", "Salunke Vihar", 2.2), ("Salunke Vihar", "NIBM Road", 1.6),
        ("NIBM Road", "Undri", 2.5), ("Yewalewadi", "Undri", 3.0), ("Katraj", "Yewalewadi", 3.5),
    ]
    for a, b, w in roads:
        na.add_road(a, b, w)

    stores = [
        ("VIIT Medical", "VIIT College", 300, 285, 0.3, "8 AM - 10 PM", "020-2693 1001",
         ["Paracetamol 500mg", "Cetirizine 10mg", "ORS Sachet", "Azithromycin 500mg", "Pantoprazole 40mg"]),
        ("Kondhwa Chemist", "Kondhwa Budruk", 455, 320, 0.4, "9 AM - 11 PM", "020-2693 1002",
         ["Paracetamol 500mg", "Metformin 500mg", "Atorvastatin 10mg", "Amlodipine 5mg", "Vitamin D3 60K"]),
        ("NIBM Wellness Pharmacy", "NIBM Road", 600, 240, 0.5, "24 x 7", "020-2693 1003",
         ["Paracetamol 500mg", "Atorvastatin 10mg", "Metformin 500mg", "Azithromycin 500mg",
          "Cetirizine 10mg", "Pantoprazole 40mg", "Vitamin D3 60K"]),
        ("Jan Aushadhi Kendra", "Katraj", 140, 415, 0.6, "9 AM - 9 PM", "020-2693 1004",
         ["Paracetamol 500mg", "Metformin 500mg", "Atorvastatin 10mg", "Pantoprazole 40mg", "Amoxicillin 500mg"]),
    ]
    for name, near, x, y, km, hours, phone, stock in stores:
        node = f"store:{name}"
        na.add_place(node, x, y)
        na.add_road(near, node, km)
        na.add_store(name, node, hours, phone, stock)

    # --- medicines for autocomplete ---
    for m in ["Paracetamol 500mg", "Pantoprazole 40mg", "Amoxicillin 500mg", "Azithromycin 500mg",
              "Amlodipine 5mg", "Atorvastatin 10mg", "Metformin 500mg", "Metoprolol 25mg",
              "Cetirizine 10mg", "Ibuprofen 400mg", "ORS Sachet", "Vitamin D3 60K",
              "Montelukast 10mg", "Omeprazole 20mg", "Losartan 50mg", "Levocetirizine 5mg",
              "Diclofenac 50mg", "Dolo 650", "Thyroxine 25mcg"]:
        na.add_medicine_name(m)

    # --- users: one patient, one doctor, one admin ---
    p1 = na.add_patient("Siddhant Sancheti", 20, "Male", "B+", "VIIT College", "90000 00001",
                        email="siddhant@caremate.in", password_hash=pw["siddhant@caremate.in"])
    d1 = na.add_doctor("Dr. Arjun Patil", "General Physician", "CareMate Clinic, Kondhwa Budruk",
                       fee=500, auto_accept=False, phone="90000 00002",
                       email="arjun@caremate.in", password_hash=pw["arjun@caremate.in"])
    na.add_admin("Admin", email="admin@caremate.in", password_hash=pw["admin@caremate.in"])

    # --- Dr. Arjun's slots for the next three days ---
    for day in (1, 2, 3):
        na.set_day_slots(d1, d(day), ["10:00", "11:00", "12:00", "17:00"], 500)

    # --- reports, each with a sample PDF ---
    na.add_report(p1, "Complete Blood Count", "Blood Test", d(-120), "Dr. Arjun Patil", "Hb 14.2, WBC normal")
    na.add_report(p1, "Chest X-Ray PA view", "X-Ray", d(-95), "Dr. Arjun Patil", "No active lesion")
    na.add_report(p1, "Lipid Profile", "Blood Test", d(-40), "Dr. Arjun Patil",
                  "LDL 142 mg/dL - borderline high", uploaded_by=d1)
    na.add_report(p1, "ECG - resting", "ECG", d(-40), "Dr. Arjun Patil", "Normal sinus rhythm", uploaded_by=d1)
    na.add_report(p1, "HbA1c", "Blood Test", d(-10), "Dr. Arjun Patil", "HbA1c 6.1% - prediabetic range")
    for r in na.report_by_id.values():
        na.attach_file(r["id"], ensure_sample_file(r, na.patients.get(r["patient_id"])))

    # --- appointments: one confirmed visit, one request waiting for Dr. Arjun ---
    s = na.free_slots.get(d1)
    _, a1 = na.book_appointment(p1, d1, s[0], 3, "Review lipid profile")
    na.accept_appointment(a1["id"], d1)
    na.book_appointment(p1, d1, s[5], 3, "Persistent cough")

    # --- prescriptions ---
    na.add_prescription(p1, d1, [
        dict(medicine="Paracetamol 500mg", dose="1 tablet", frequency="Thrice a day", days=3),
        dict(medicine="Cetirizine 10mg", dose="1 tablet", frequency="At bedtime", days=5),
    ], "Viral fever. Drink plenty of fluids.", d(-20))
    na.add_prescription(p1, d1, [
        dict(medicine="Atorvastatin 10mg", dose="1 tablet", frequency="At bedtime", days=30),
        dict(medicine="Metformin 500mg", dose="1 tablet", frequency="Twice a day", days=30),
    ], "Low-fat diet, 30 min walk daily. Repeat lipid profile after 3 months.", d(-9))

    return na
