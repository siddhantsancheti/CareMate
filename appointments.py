"""
Appointments: doctors' slots and fees, booking, accepting, the patient queue
and the waiting list.

Data structures used here:
    Queue         -> a doctor's waiting list (first come, first served)
    PriorityQueue -> a doctor's patient queue (earliest day, then most urgent)
"""

from datetime import date, datetime

from sorting_searching import binary_search, merge_sort

PRIORITY_LABELS = {1: "Emergency", 2: "Urgent", 3: "Routine"}
HOLDS_SLOT = ("Pending", "Confirmed", "Completed")      # these statuses keep the slot taken
GIVES_ACCESS = ("Confirmed", "Completed")               # doctor may see the patient's reports
DAY_TIMES = [f"{h:02d}:{m:02d}" for h in range(8, 20) for m in (0, 30)]   # 08:00 .. 19:30


def now_slot():
    return datetime.now().strftime("%Y-%m-%d %H:%M")


# A node of a singly linked list: it holds data and points to the next node.
class Node:
    def __init__(self, data):
        self.data = data
        self.next = None


# =====================================================================
# Queue (FIFO: first in, first out) built on a linked list
# =====================================================================
class Queue:
    def __init__(self):
        self.front = None
        self.rear = None
        self.size = 0

    def enqueue(self, data):
        node = Node(data)
        if self.rear is None:
            self.front = node
            self.rear = node
        else:
            self.rear.next = node
            self.rear = node
        self.size += 1

    def dequeue(self):
        if self.front is None:
            return None
        node = self.front
        self.front = node.next
        if self.front is None:
            self.rear = None
        self.size -= 1
        return node.data

    def peek(self):
        return self.front.data if self.front else None

    def is_empty(self):
        return self.size == 0

    def to_list(self):
        items = []
        current = self.front
        while current is not None:
            items.append(current.data)
            current = current.next
        return items

    def __len__(self):
        return self.size


# =====================================================================
# Priority Queue built on a sorted list
# Every item has a priority; the smallest priority is served first.
# A new item is placed just after the items with the same or smaller priority,
# so patients with equal priority keep their booking order.
# =====================================================================
class PriorityQueue:
    def __init__(self):
        self.items = []                # list of (priority, item), kept sorted

    def push(self, priority, item):
        i = len(self.items)
        while i > 0 and self.items[i - 1][0] > priority:
            i -= 1
        self.items.insert(i, (priority, item))

    def pop(self):
        if not self.items:
            return None
        return self.items.pop(0)[1]

    def remove(self, match):
        for i in range(len(self.items)):
            if match(self.items[i][1]):
                return self.items.pop(i)[1]
        return None

    def to_list(self):
        return [item for _, item in self.items]

    def __len__(self):
        return len(self.items)


# =====================================================================
# The appointments part of CareMate
# =====================================================================
class Appointments:
    # ---------------------------------------------------------------- doctor slots & fees
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
                self.slot_fee.pop(self._fee_key(did, s), None)
                self._delete("doctor_slots", doctor_id=did, slot=s)
            else:
                keep.append(s)
        for s in wanted - taken:
            if self._fee_key(did, s) in self.slot_fee:  # already offered: new fee
                self._update("doctor_slots", dict(fee=fee), doctor_id=did, slot=s)
            else:
                keep.append(s)
                self._save("doctor_slots", doctor_id=did, slot=s, fee=fee)
            self.slot_fee[self._fee_key(did, s)] = fee
        self.free_slots[did] = merge_sort(keep)
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

    # ---------------------------------------------------------------- booking
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
        self.appointments[aid] = appt
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
            self.free_slots[did] = merge_sort(slots)

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
        return self.doctor_queue.get(doctor_id).to_list()

    def has_access(self, doctor_id, patient_id):
        """A doctor may open a patient's reports once that patient's booking is accepted."""
        return any(a["doctor_id"] == doctor_id and a["patient_id"] == patient_id
                   and a["status"] in GIVES_ACCESS for a in self.appointments.values())

    def doctor_patients(self, doctor_id):
        ids = {a["patient_id"] for a in self.appointments.values()
               if a["doctor_id"] == doctor_id and a["status"] in GIVES_ACCESS}
        return merge_sort([self.patients.get(p) for p in ids], key=lambda p: p["name"])
