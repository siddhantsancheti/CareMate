patients = {}
doctors = {}
admins = {}
emails = {}

reports = {}
report_dates = {}
report_by_id = {}

free_slots = {}
slot_fee = {}
requests = {}
queue = {}
waitlist = {}
appointments = {}

prescriptions = {}
rx_by_id = {}
medicines = []

stores = {}
activity = []

counter = 0


def new_id(prefix):
    global counter
    counter += 1
    return prefix + str(counter)


def log(text, patient_id=None, doctor_id=None):
    activity.append(dict(text=text, patient_id=patient_id, doctor_id=doctor_id))


def activity_for(role, user_id, limit=6):
    events = [e["text"] for e in reversed(activity) if role == "admin" or e.get(role + "_id") == user_id]
    return events[:limit]
