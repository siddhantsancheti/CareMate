"""
Users: patients, doctors and admins. Sign-up and login.
Passwords are never stored as they are, only as a hash.
"""

from werkzeug.security import check_password_hash, generate_password_hash

import data
from appointments import PriorityQueue, Queue
from prescriptions import Stack
from reports import BST, DoublyLinkedList
from sorting_searching import merge_sort


def add_patient(name, age, gender, blood_group, location, phone, email, password):
    pid = data.new_id("P")
    data.patients[pid] = dict(id=pid, name=name, age=age, gender=gender, blood_group=blood_group,
                              location=location, phone=phone, email=email,
                              password=generate_password_hash(password))
    data.emails[email] = pid
    data.reports[pid] = DoublyLinkedList()
    data.report_dates[pid] = BST()
    data.prescriptions[pid] = Stack()
    return pid


def add_doctor(name, specialty, clinic, fee, phone, email, password, auto_accept=True):
    did = data.new_id("D")
    data.doctors[did] = dict(id=did, name=name, specialty=specialty, clinic=clinic, fee=fee,
                             auto_accept=auto_accept, phone=phone, email=email,
                             password=generate_password_hash(password))
    data.emails[email] = did
    data.free_slots[did] = []
    data.requests[did] = DoublyLinkedList()
    data.queue[did] = PriorityQueue()
    data.waitlist[did] = Queue()
    return did


def add_admin(name, email, password):
    aid = data.new_id("A")
    data.admins[aid] = dict(id=aid, name=name, email=email, password=generate_password_hash(password))
    data.emails[email] = aid
    return aid


def find_user(user_id):
    """(role, user) for an id, or (None, None)."""
    for role, table in (("patient", data.patients), ("doctor", data.doctors), ("admin", data.admins)):
        if user_id in table:
            return role, table[user_id]
    return None, None


def login(email, password):
    """The user if the email and password are right, else None."""
    role, user = find_user(data.emails.get(email.strip().lower()))
    if user and check_password_hash(user["password"], password):
        return user
    return None


def email_taken(email):
    return email.strip().lower() in data.emails


def all_doctors():
    return merge_sort(list(data.doctors.values()), key=lambda d: d["name"])
