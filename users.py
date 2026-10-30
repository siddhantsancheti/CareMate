"""
Users: patients, doctors and admins. Sign-up, login and editing users.
Users are kept in Python dictionaries: user id -> user details.
"""

from werkzeug.security import check_password_hash, generate_password_hash

from appointments import PriorityQueue, Queue
from prescriptions import Stack
from reports import BST, DoublyLinkedList
from sorting_searching import merge_sort


class Users:
    def add_patient(self, name, age, gender, blood_group, location, phone="", active=True, pid=None,
                    email=None, password_hash=None):
        pid = pid or self._next_id("P")
        patient = dict(id=pid, name=name, age=age, gender=gender, blood_group=blood_group,
                       location=location, phone=phone, active=active, email=email, password_hash=password_hash)
        self.patients[pid] = patient
        self._index_email(email, pid)
        self.reports[pid] = DoublyLinkedList()
        self.report_index[pid] = BST()
        self.prescriptions[pid] = Stack()
        self._save("patients", **patient)
        return pid

    def add_doctor(self, name, specialty, clinic, fee=500, auto_accept=True, phone="",
                   active=True, did=None, email=None, password_hash=None):
        did = did or self._next_id("D")
        doctor = dict(id=did, name=name, specialty=specialty, clinic=clinic, fee=fee,
                      auto_accept=auto_accept, phone=phone, active=active, email=email, password_hash=password_hash)
        self.doctors[did] = doctor
        self._index_email(email, did)
        self.free_slots[did] = []
        self.pending[did] = DoublyLinkedList()
        self.doctor_queue[did] = PriorityQueue()
        self.waitlist[did] = Queue()
        self._save("doctors", **doctor)
        return did

    def add_admin(self, name, active=True, aid=None, email=None, password_hash=None):
        aid = aid or self._next_id("AD")
        admin = dict(id=aid, name=name, active=active, email=email, password_hash=password_hash)
        self.admins[aid] = admin
        self._index_email(email, aid)
        self._save("admins", **admin)
        return aid

    # ---------------------------------------------------------------- sign-up / login
    def _index_email(self, email, uid):
        if email:
            self.by_email[email.strip().lower()] = uid

    @staticmethod
    def hash_password(password):
        return generate_password_hash(password)

    def email_taken(self, email):
        return (email or "").strip().lower() in self.by_email

    def authenticate(self, email, password):
        """The user with this email and password, or None (wrong details or deactivated)."""
        uid = self.by_email.get((email or "").strip().lower())
        u = self.user(uid) if uid else None
        if u and u["active"] and u.get("password_hash") and check_password_hash(u["password_hash"], password or ""):
            return u
        return None

    def _table_of(self, uid):
        for role, table, db_table in (("patient", self.patients, "patients"),
                                      ("doctor", self.doctors, "doctors"),
                                      ("admin", self.admins, "admins")):
            if uid and uid in table:
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
