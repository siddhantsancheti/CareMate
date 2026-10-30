"""
Admin insights: most booked doctors, most prescribed medicines and totals.
"""

from appointments import HOLDS_SLOT
from sorting_searching import merge_sort


class Admin:
    def most_booked_doctors(self, k=5):
        counts = {}
        for a in self.appointments.values():
            if a["status"] in HOLDS_SLOT:
                counts[a["doctor_id"]] = counts.get(a["doctor_id"], 0) + 1
        top = merge_sort(list(counts.items()), key=lambda pair: pair[1], reverse=True)[:k]
        return [(self.doctors.get(did), n) for did, n in top]

    def most_prescribed_medicines(self, k=5):
        counts = {}
        for stack in self.prescriptions.values():
            for rx in stack.to_list():
                for it in rx["items"]:
                    counts[it["medicine"]] = counts.get(it["medicine"], 0) + 1
        return merge_sort(list(counts.items()), key=lambda pair: pair[1], reverse=True)[:k]

    def platform_totals(self):
        by_status = {}
        for a in self.appointments.values():
            by_status[a["status"]] = by_status.get(a["status"], 0) + 1
        return dict(patients=len(self.patients), doctors=len(self.doctors),
                    appointments=len(self.appointments),
                    pending=by_status.get("Pending", 0), confirmed=by_status.get("Confirmed", 0),
                    completed=by_status.get("Completed", 0),
                    fees=sum(float(a["fee"]) for a in self.appointments.values()
                             if a["status"] == "Completed"),
                    prescriptions=sum(len(s) for s in self.prescriptions.values()))
