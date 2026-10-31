"""
Demo data: the map of Kondhwa around VIIT, 4 medical stores and three demo logins.

    Patient  siddhant@caremate.in / siddhant123
    Doctor   arjun@caremate.in    / arjun123
    Admin    admin@caremate.in    / admin123
"""

from datetime import date, timedelta

import appointments
import prescriptions
import reports
import stores
import users


def day(offset):
    return (date.today() + timedelta(days=offset)).isoformat()


def load():
    # places: (x, y) is only for drawing; roads are approximate km
    places = {"VIIT College": (330, 250), "Kondhwa Budruk": (420, 290), "Upper Indira Nagar": (235, 205),
              "Bibvewadi": (180, 130), "Katraj": (170, 380), "Kondhwa Khurd": (470, 170),
              "NIBM Road": (565, 205), "Salunke Vihar": (525, 95), "Yewalewadi": (430, 410), "Undri": (600, 330)}
    for name, (x, y) in places.items():
        stores.city.add_place(name, x, y)
    for a, b, km in [("VIIT College", "Upper Indira Nagar", 1.2), ("VIIT College", "Kondhwa Budruk", 1.0),
                     ("VIIT College", "Katraj", 3.0), ("Upper Indira Nagar", "Bibvewadi", 1.5),
                     ("Bibvewadi", "Katraj", 3.0), ("Kondhwa Budruk", "Kondhwa Khurd", 2.0),
                     ("Kondhwa Budruk", "Yewalewadi", 2.0), ("Kondhwa Khurd", "NIBM Road", 1.8),
                     ("Kondhwa Khurd", "Salunke Vihar", 2.2), ("Salunke Vihar", "NIBM Road", 1.6),
                     ("NIBM Road", "Undri", 2.5), ("Yewalewadi", "Undri", 3.0), ("Katraj", "Yewalewadi", 3.5)]:
        stores.city.add_road(a, b, km)

    stores.add_store("VIIT Medical", "VIIT College", 300, 285, 0.3, "8 AM - 10 PM", "020-2693 1001",
                     ["Paracetamol 500mg", "Cetirizine 10mg", "ORS Sachet", "Azithromycin 500mg", "Pantoprazole 40mg"])
    stores.add_store("Kondhwa Chemist", "Kondhwa Budruk", 455, 320, 0.4, "9 AM - 11 PM", "020-2693 1002",
                     ["Paracetamol 500mg", "Metformin 500mg", "Atorvastatin 10mg", "Amlodipine 5mg", "Vitamin D3 60K"])
    stores.add_store("NIBM Wellness Pharmacy", "NIBM Road", 600, 240, 0.5, "24 x 7", "020-2693 1003",
                     ["Paracetamol 500mg", "Atorvastatin 10mg", "Metformin 500mg", "Azithromycin 500mg",
                      "Cetirizine 10mg", "Pantoprazole 40mg", "Vitamin D3 60K"])
    stores.add_store("Jan Aushadhi Kendra", "Katraj", 140, 415, 0.6, "9 AM - 9 PM", "020-2693 1004",
                     ["Paracetamol 500mg", "Metformin 500mg", "Atorvastatin 10mg", "Pantoprazole 40mg", "Amoxicillin 500mg"])

    for m in ["Paracetamol 500mg", "Pantoprazole 40mg", "Amoxicillin 500mg", "Azithromycin 500mg",
              "Amlodipine 5mg", "Atorvastatin 10mg", "Metformin 500mg", "Metoprolol 25mg", "Cetirizine 10mg",
              "Ibuprofen 400mg", "ORS Sachet", "Vitamin D3 60K", "Montelukast 10mg", "Omeprazole 20mg",
              "Losartan 50mg", "Levocetirizine 5mg", "Diclofenac 50mg", "Dolo 650", "Thyroxine 25mcg"]:
        prescriptions.add_medicine(m)

    p = users.add_patient("Siddhant Sancheti", 20, "Male", "B+", "VIIT College", "90000 00001",
                          "siddhant@caremate.in", "siddhant123")
    d = users.add_doctor("Dr. Arjun Patil", "General Physician", "CareMate Clinic, Kondhwa Budruk", 500,
                         "90000 00002", "arjun@caremate.in", "arjun123", auto_accept=False)
    users.add_admin("Admin", "admin@caremate.in", "admin123")

    for offset in (1, 2, 3):
        appointments.set_day_slots(d, day(offset), ["10:00", "11:00", "12:00", "17:00"], 500)

    # reports, each with a sample PDF from the uploads folder
    reports.add_report(p, "Complete Blood Count", "Blood Test", day(-120), "Dr. Arjun Patil",
                       "Hb 14.2, WBC normal", "sample_P5_complete-blood-count.pdf")
    reports.add_report(p, "Chest X-Ray PA view", "X-Ray", day(-95), "Dr. Arjun Patil",
                       "No active lesion", "sample_P5_chest-x-ray-pa-view.pdf")
    reports.add_report(p, "Lipid Profile", "Blood Test", day(-40), "Dr. Arjun Patil",
                       "LDL 142 mg/dL - borderline high", "sample_P5_lipid-profile.pdf", uploaded_by=d)
    reports.add_report(p, "ECG - resting", "ECG", day(-40), "Dr. Arjun Patil",
                       "Normal sinus rhythm", "sample_P5_ecg-resting.pdf", uploaded_by=d)
    reports.add_report(p, "HbA1c", "Blood Test", day(-10), "Dr. Arjun Patil",
                       "HbA1c 6.1% - prediabetic range", "sample_P5_hba1c.pdf")

    # one accepted visit, and one request waiting for Dr. Arjun
    slots = [s for s, fee in appointments.bookable_slots(d)]
    status, first = appointments.book(p, d, slots[0], 3, "Review lipid profile")
    appointments.accept(first["id"], d)
    appointments.book(p, d, slots[5], 3, "Persistent cough")

    prescriptions.add_prescription(p, d, [
        dict(medicine="Paracetamol 500mg", dose="1 tablet", frequency="Thrice a day", days=3),
        dict(medicine="Cetirizine 10mg", dose="1 tablet", frequency="At bedtime", days=5),
    ], "Viral fever. Drink plenty of fluids.", day(-20))
    prescriptions.add_prescription(p, d, [
        dict(medicine="Atorvastatin 10mg", dose="1 tablet", frequency="At bedtime", days=30),
        dict(medicine="Metformin 500mg", dose="1 tablet", frequency="Twice a day", days=30),
    ], "Low-fat diet, 30 min walk daily. Repeat lipid profile after 3 months.", day(-9))
