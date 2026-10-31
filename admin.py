import data
from appointments import HOLDS_SLOT
from sorting_searching import merge_sort

def top(counts, k):
    return merge_sort(list(counts.items()), key=lambda pair: pair[1], reverse=True)[:k]

def most_booked_doctors(k=5):
    counts = {}
    for a in data.appointments.values():
        if a["status"] in HOLDS_SLOT:
            counts[a["doctor_id"]] = counts.get(a["doctor_id"], 0) + 1
    return [(data.doctors[did], n) for did, n in top(counts, k)]

def most_prescribed_medicines(k=5):
    counts = {}
    for stack in data.prescriptions.values():
        for rx in stack.to_list():
            for item in rx["items"]:
                counts[item["medicine"]] = counts.get(item["medicine"], 0) + 1
    return top(counts, k)

def totals():
    statuses = [a["status"] for a in data.appointments.values()]
    return dict(patients=len(data.patients), doctors=len(data.doctors), appointments=len(statuses),
                pending=statuses.count("Pending"), confirmed=statuses.count("Confirmed"),
                completed=statuses.count("Completed"),
                fees=sum(a["fee"] for a in data.appointments.values() if a["status"] == "Completed"),
                prescriptions=len(data.rx_by_id))
