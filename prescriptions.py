"""
Prescriptions: doctors write them, patients see them and get daily reminders.

Data structure used here:
    Stack -> each patient's prescription history (newest on top), so the doctor
             can withdraw the newest one with pop()
Medicine suggestions come from a sorted list of names.
"""

from datetime import date, timedelta

from sorting_searching import merge_sort

FREQ_TIMES = {"Once a day": ["09:00"], "Twice a day": ["09:00", "21:00"],
              "Thrice a day": ["08:00", "14:00", "20:00"], "At bedtime": ["22:00"],
              "As needed": ["When required"]}


# A node of a singly linked list: it holds data and points to the next node.
class Node:
    def __init__(self, data):
        self.data = data
        self.next = None


# =====================================================================
# Stack (LIFO: last in, first out) built on a linked list
# =====================================================================
class Stack:
    def __init__(self):
        self.top = None
        self.size = 0

    def push(self, data):
        node = Node(data)
        node.next = self.top
        self.top = node
        self.size += 1

    def pop(self):
        if self.top is None:
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
        """Top of the stack first."""
        items = []
        current = self.top
        while current is not None:
            items.append(current.data)
            current = current.next
        return items

    def __len__(self):
        return self.size


# =====================================================================
# The prescriptions part of CareMate
# =====================================================================
class Prescriptions:
    def add_medicine_name(self, name):
        if any(m.lower() == name.lower() for m in self.medicine_names):
            return
        self.medicine_names = merge_sort(self.medicine_names + [name], key=str.lower)
        self._save("medicines", ignore=True, name=name)

    def suggest_medicines(self, prefix):
        """Medicine names that start with what the doctor typed (alphabetical, at most 8)."""
        prefix = prefix.lower()
        return [m for m in self.medicine_names if m.lower().startswith(prefix)][:8]

    def add_prescription(self, patient_id, doctor_id, items, notes="", pdate=None, rx_id=None):
        rx = dict(id=rx_id or self._next_id("RX"), patient_id=patient_id, doctor_id=doctor_id,
                  date=pdate or date.today().isoformat(), items=items, notes=notes)
        self._save("prescriptions", id=rx["id"], patient_id=patient_id, doctor_id=doctor_id,
                   date=rx["date"], notes=notes)
        for it in items:
            self.add_medicine_name(it["medicine"])       # learn new medicine names
            self._save("prescription_items", prescription_id=rx["id"], **it)
        self.prescriptions.get(patient_id).push(rx)
        self.rx_by_id[rx["id"]] = rx
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
        self.rx_by_id.pop(rx["id"], None)
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
