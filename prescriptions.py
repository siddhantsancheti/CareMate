"""
Prescriptions: doctors write them, patients see them and get today's reminders.

    Stack -> each patient's prescription history, newest on top,
             so withdrawing the newest one is just pop()
"""

from datetime import date, timedelta

import data
from sorting_searching import merge_sort

FREQ_TIMES = {"Once a day": ["09:00"], "Twice a day": ["09:00", "21:00"],
              "Thrice a day": ["08:00", "14:00", "20:00"], "At bedtime": ["22:00"],
              "As needed": ["When required"]}


# ---------------------------------------------------------------- Stack (last in, first out)
class Node:
    def __init__(self, data):
        self.data = data
        self.next = None


class Stack:
    def __init__(self):
        self.top = None
        self.size = 0

    def push(self, item):               # put on top, O(1)
        node = Node(item)
        node.next = self.top
        self.top = node
        self.size += 1

    def pop(self):                      # take from the top, O(1)
        if not self.top:
            return None
        node = self.top
        self.top = node.next
        self.size -= 1
        return node.data

    def peek(self):
        return self.top.data if self.top else None

    def is_empty(self):
        return self.size == 0

    def to_list(self):
        """Top first."""
        items, node = [], self.top
        while node:
            items.append(node.data)
            node = node.next
        return items

    def __len__(self):
        return self.size


# ---------------------------------------------------------------- prescription features
def add_medicine(name):
    if name.lower() not in [m.lower() for m in data.medicines]:
        data.medicines.append(name)
        data.medicines[:] = merge_sort(data.medicines, key=str.lower)


def suggest(prefix):
    """Medicine names starting with what the doctor typed (at most 8)."""
    return [m for m in data.medicines if m.lower().startswith(prefix.lower())][:8]


def add_prescription(patient_id, doctor_id, items, notes="", rx_date=None):
    rx = dict(id=data.new_id("RX"), patient_id=patient_id, doctor_id=doctor_id,
              date=rx_date or date.today().isoformat(), items=items, notes=notes)
    for item in items:
        add_medicine(item["medicine"])
    data.prescriptions[patient_id].push(rx)
    data.rx_by_id[rx["id"]] = rx
    data.log(f"{data.doctors[doctor_id]['name']} sent a prescription to {data.patients[patient_id]['name']}",
             patient_id, doctor_id)
    return rx


def withdraw_newest(patient_id, doctor_id):
    """Only the newest prescription, and only by the doctor who wrote it."""
    stack = data.prescriptions[patient_id]
    if stack.is_empty() or stack.peek()["doctor_id"] != doctor_id:
        return None
    rx = stack.pop()
    del data.rx_by_id[rx["id"]]
    data.log(f"Prescription {rx['id']} withdrawn", patient_id, doctor_id)
    return rx


def history(patient_id):
    return data.prescriptions[patient_id].to_list()      # newest first


def is_active(rx, item):
    """A medicine is taken for `days` days from the prescription date."""
    start = date.fromisoformat(rx["date"])
    return start <= date.today() < start + timedelta(days=int(item["days"]))


def todays_reminders(patient_id):
    reminders = []
    for rx in history(patient_id):
        for item in rx["items"]:
            if is_active(rx, item):
                for t in FREQ_TIMES.get(item["frequency"], ["09:00"]):
                    reminders.append(dict(time=t, medicine=item["medicine"], dose=item["dose"],
                                          doctor_id=rx["doctor_id"]))
    return merge_sort(reminders, key=lambda r: r["time"])


def current_medicines(patient_id):
    names = []
    for rx in history(patient_id):
        for item in rx["items"]:
            if is_active(rx, item) and item["medicine"] not in names:
                names.append(item["medicine"])
    return names
