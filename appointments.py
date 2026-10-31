"""
Appointments: doctors' slots and fees, booking, the doctor's queue and the waiting list.

    Queue         -> waiting list: first come, first served
    PriorityQueue -> the doctor's queue: earliest day first, then the most urgent patient
"""

from datetime import date, datetime

import data
from sorting_searching import binary_search, merge_sort

PRIORITY_LABELS = {1: "Emergency", 2: "Urgent", 3: "Routine"}
DAY_TIMES = [f"{h:02d}:{m:02d}" for h in range(8, 20) for m in (0, 30)]   # 08:00 to 19:30
HOLDS_SLOT = ("Pending", "Confirmed", "Completed")   # these keep a slot taken
GIVES_ACCESS = ("Confirmed", "Completed")            # the doctor may then open the patient's reports


def now_slot():
    return datetime.now().strftime("%Y-%m-%d %H:%M")


# ---------------------------------------------------------------- Queue (first in, first out)
class Node:
    def __init__(self, data):
        self.data = data
        self.next = None


class Queue:
    def __init__(self):
        self.front = None
        self.rear = None
        self.size = 0

    def enqueue(self, item):            # add at the rear, O(1)
        node = Node(item)
        if self.rear:
            self.rear.next = node
        else:
            self.front = node
        self.rear = node
        self.size += 1

    def dequeue(self):                  # remove from the front, O(1)
        if not self.front:
            return None
        node = self.front
        self.front = node.next
        if not self.front:
            self.rear = None
        self.size -= 1
        return node.data

    def peek(self):
        return self.front.data if self.front else None

    def is_empty(self):
        return self.size == 0

    def to_list(self):
        items, node = [], self.front
        while node:
            items.append(node.data)
            node = node.next
        return items

    def __len__(self):
        return self.size


# ---------------------------------------------------------------- Priority Queue (sorted list)
class PriorityQueue:
    """Smallest priority is served first. Equal priorities keep the order they arrived in."""
    def __init__(self):
        self.items = []                 # (priority, item), always kept sorted

    def push(self, priority, item):     # O(n): walk back to the right place
        i = len(self.items)
        while i > 0 and self.items[i - 1][0] > priority:
            i -= 1
        self.items.insert(i, (priority, item))

    def pop(self):
        return self.items.pop(0)[1] if self.items else None

    def remove(self, match):
        for i in range(len(self.items)):
            if match(self.items[i][1]):
                return self.items.pop(i)[1]
        return None

    def to_list(self):
        return [item for priority, item in self.items]


# ---------------------------------------------------------------- slots and fees
def set_day_slots(doctor_id, day, times, fee):
    """The doctor ticks the times offered on one day and sets that day's fee.
    Booked slots are never removed."""
    taken = taken_slots(doctor_id)
    keep = [s for s in data.free_slots[doctor_id] if not s.startswith(day)]
    for t in times:
        slot = f"{day} {t}"
        if slot not in taken:
            keep.append(slot)
        data.slot_fee[(doctor_id, slot)] = fee
    data.free_slots[doctor_id] = merge_sort(keep)


def taken_slots(doctor_id):
    return {a["slot"] for a in data.appointments.values()
            if a["doctor_id"] == doctor_id and a["status"] in HOLDS_SLOT}


def day_view(doctor_id, day):
    """[(time, 'free' | 'booked' | 'off', fee)] for the slot editor."""
    free, taken = data.free_slots[doctor_id], taken_slots(doctor_id)
    view = []
    for t in DAY_TIMES:
        slot = f"{day} {t}"
        state = "booked" if slot in taken else "free" if binary_search(free, slot) != -1 else "off"
        view.append((t, state, data.slot_fee.get((doctor_id, slot))))
    return view


def upcoming_days(doctor_id):
    """[(day, free, booked, fee)] from today on."""
    today, days = date.today().isoformat(), {}
    for slot in data.free_slots[doctor_id]:
        if slot >= today:
            days.setdefault(slot[:10], [0, 0, data.slot_fee.get((doctor_id, slot))])[0] += 1
    for slot in taken_slots(doctor_id):
        if slot >= today:
            days.setdefault(slot[:10], [0, 0, data.slot_fee.get((doctor_id, slot))])[1] += 1
    return [(d, *days[d]) for d in merge_sort(list(days))]


def bookable_slots(doctor_id):
    """Free slots still in the future, with their fee."""
    fee = data.doctors[doctor_id]["fee"]
    return [(s, data.slot_fee.get((doctor_id, s), fee)) for s in data.free_slots[doctor_id] if s > now_slot()]


# ---------------------------------------------------------------- booking
def book(patient_id, doctor_id, slot, priority, reason):
    """Returns 'confirmed', 'pending' or 'waitlisted', and the appointment (None if waitlisted)."""
    slots = data.free_slots[doctor_id]
    i = binary_search(slots, slot) if slot else -1
    if i == -1:                         # no free slot chosen: join the waiting list
        data.waitlist[doctor_id].enqueue(dict(patient_id=patient_id, priority=priority, reason=reason))
        data.log(f"{data.patients[patient_id]['name']} joined {data.doctors[doctor_id]['name']}'s waiting list",
                 patient_id, doctor_id)
        return "waitlisted", None
    slots.pop(i)
    appt = create_appointment(patient_id, doctor_id, slot, priority, reason)
    return appt["status"].lower(), appt


def create_appointment(patient_id, doctor_id, slot, priority, reason):
    doctor = data.doctors[doctor_id]
    appt = dict(id=data.new_id("AP"), patient_id=patient_id, doctor_id=doctor_id, slot=slot,
                fee=data.slot_fee.get((doctor_id, slot), doctor["fee"]), priority=priority,
                priority_label=PRIORITY_LABELS[priority], reason=reason,
                status="Confirmed" if doctor["auto_accept"] else "Pending")
    data.appointments[appt["id"]] = appt
    if appt["status"] == "Pending":
        data.requests[doctor_id].add_last(appt)
    else:
        add_to_queue(appt)
    data.log(f"{data.patients[patient_id]['name']} booked {doctor['name']} at {slot} "
             f"({appt['priority_label']}): {appt['status'].lower()}", patient_id, doctor_id)
    return appt


def add_to_queue(appt):
    # (day, urgency, time): earlier days first, emergencies first within a day
    data.queue[appt["doctor_id"]].push((appt["slot"][:10], appt["priority"], appt["slot"]), appt)


def accept(appt_id, doctor_id):
    appt = data.appointments.get(appt_id)
    if not appt or appt["doctor_id"] != doctor_id or appt["status"] != "Pending":
        return None
    data.requests[doctor_id].remove(lambda a: a["id"] == appt_id)
    appt["status"] = "Confirmed"
    add_to_queue(appt)
    data.log(f"{data.doctors[doctor_id]['name']} accepted {data.patients[appt['patient_id']]['name']} "
             f"for {appt['slot']}", appt["patient_id"], doctor_id)
    return appt


def reject(appt_id, doctor_id):
    appt = data.appointments.get(appt_id)
    if not appt or appt["doctor_id"] != doctor_id or appt["status"] != "Pending":
        return None
    data.requests[doctor_id].remove(lambda a: a["id"] == appt_id)
    appt["status"] = "Rejected"
    data.log(f"{data.doctors[doctor_id]['name']} could not take the {appt['slot']} request",
             appt["patient_id"], doctor_id)
    slot_opened(doctor_id, appt["slot"])
    return appt


def cancel(appt_id, patient_id):
    appt = data.appointments.get(appt_id)
    if not appt or appt["patient_id"] != patient_id or appt["status"] not in ("Pending", "Confirmed"):
        return None
    doctor_id = appt["doctor_id"]
    if appt["status"] == "Pending":
        data.requests[doctor_id].remove(lambda a: a["id"] == appt_id)
    else:
        data.queue[doctor_id].remove(lambda a: a["id"] == appt_id)
    appt["status"] = "Cancelled"
    data.log(f"Appointment {appt['slot']} cancelled", patient_id, doctor_id)
    slot_opened(doctor_id, appt["slot"])
    return appt


def slot_opened(doctor_id, slot):
    """The first patient on the waiting list gets the slot; otherwise it is free again."""
    if slot > now_slot() and not data.waitlist[doctor_id].is_empty():
        w = data.waitlist[doctor_id].dequeue()
        create_appointment(w["patient_id"], doctor_id, slot, w["priority"], w["reason"])
    else:
        data.free_slots[doctor_id] = merge_sort(data.free_slots[doctor_id] + [slot])


def call_next(doctor_id):
    appt = data.queue[doctor_id].pop()
    if appt:
        appt["status"] = "Completed"
        data.log(f"{data.doctors[doctor_id]['name']} saw {data.patients[appt['patient_id']]['name']}",
                 appt["patient_id"], doctor_id)
    return appt


def set_auto_accept(doctor_id, on):
    data.doctors[doctor_id]["auto_accept"] = on
    if on:                              # accept everything already waiting
        for appt in data.requests[doctor_id].to_list():
            accept(appt["id"], doctor_id)


def patient_appointments(patient_id):
    mine = [a for a in data.appointments.values() if a["patient_id"] == patient_id]
    return merge_sort(mine, key=lambda a: a["slot"])


def has_access(doctor_id, patient_id):
    """A doctor may open a patient's reports once that patient's booking is accepted."""
    return any(a["doctor_id"] == doctor_id and a["patient_id"] == patient_id and a["status"] in GIVES_ACCESS
               for a in data.appointments.values())


def doctor_patients(doctor_id):
    ids = {a["patient_id"] for a in data.appointments.values()
           if a["doctor_id"] == doctor_id and a["status"] in GIVES_ACCESS}
    return merge_sort([data.patients[p] for p in ids], key=lambda p: p["name"])
