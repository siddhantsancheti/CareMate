"""
Sample lab-report PDFs for the demo data, so every demo report has a real
multi-page file to open. Written with a tiny hand-made PDF writer (no extra
library). Every page says SAMPLE: these are demo files, not real results.
"""

import os
import re

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads")

# title -> (lab section, rows of (test, result, unit, reference range, flag), interpretation lines)
SAMPLES = {
    "Complete Blood Count": ("Haematology", [
        ("Haemoglobin", "14.2", "g/dL", "13.0 - 17.0", ""),
        ("RBC count", "4.9", "mill/uL", "4.5 - 5.5", ""),
        ("Packed cell volume (PCV)", "43", "%", "40 - 50", ""),
        ("MCV", "88", "fL", "83 - 101", ""),
        ("Total WBC count", "7,200", "/uL", "4,000 - 11,000", ""),
        ("Neutrophils", "58", "%", "40 - 75", ""),
        ("Lymphocytes", "33", "%", "20 - 45", ""),
        ("Platelet count", "2.6", "lakh/uL", "1.5 - 4.1", ""),
    ], ["All blood counts are within normal limits.", "No evidence of anaemia or infection."]),
    "Chest X-Ray PA view": ("Radiology", [
        ("Lung fields", "Clear", "", "", ""),
        ("Cardiac silhouette", "Normal (CTR 0.45)", "", "CTR < 0.50", ""),
        ("Costophrenic angles", "Clear", "", "", ""),
        ("Hila and mediastinum", "Normal", "", "", ""),
        ("Bony thorax", "No abnormality", "", "", ""),
    ], ["Impression: No active lesion in the lungs.", "Heart size within normal limits."]),
    "Lipid Profile": ("Biochemistry", [
        ("Total cholesterol", "218", "mg/dL", "< 200", "H"),
        ("LDL cholesterol", "142", "mg/dL", "< 100", "H"),
        ("HDL cholesterol", "44", "mg/dL", "> 40", ""),
        ("Triglycerides", "160", "mg/dL", "< 150", "H"),
        ("VLDL cholesterol", "32", "mg/dL", "< 30", "H"),
        ("Non-HDL cholesterol", "174", "mg/dL", "< 130", "H"),
        ("Total cholesterol / HDL ratio", "4.95", "", "< 5.0", ""),
    ], ["LDL is borderline high; triglycerides mildly raised.",
        "Suggest diet control, exercise and a repeat test in 3 months."]),
    "ECG - resting": ("Cardiology", [
        ("Heart rate", "72", "bpm", "60 - 100", ""),
        ("Rhythm", "Sinus", "", "", ""),
        ("PR interval", "160", "ms", "120 - 200", ""),
        ("QRS duration", "88", "ms", "< 120", ""),
        ("QTc interval", "410", "ms", "< 440", ""),
        ("Electrical axis", "+45", "degrees", "-30 to +90", ""),
    ], ["Impression: Normal sinus rhythm.", "No ST-T changes. No conduction block."]),
    "HbA1c": ("Biochemistry", [
        ("HbA1c (glycated haemoglobin)", "6.1", "%", "< 5.7", "H"),
        ("Estimated average glucose", "128", "mg/dL", "< 117", "H"),
        ("Fasting plasma glucose", "108", "mg/dL", "70 - 100", "H"),
    ], ["HbA1c 5.7 - 6.4 % is the prediabetic range.",
        "Lifestyle changes advised; repeat HbA1c in 3 months."]),
    "Thyroid Profile": ("Endocrinology", [
        ("TSH", "5.8", "uIU/mL", "0.4 - 4.5", "H"),
        ("Free T4", "1.0", "ng/dL", "0.8 - 1.8", ""),
        ("Free T3", "2.9", "pg/mL", "2.3 - 4.2", ""),
        ("Anti-TPO antibodies", "48", "IU/mL", "< 35", "H"),
    ], ["Mildly raised TSH with normal free T4: subclinical hypothyroidism.",
        "Positive anti-TPO. Clinical correlation advised."]),
    "Knee MRI": ("Radiology", [
        ("Medial joint space", "Narrowed", "", "", ""),
        ("Osteophytes", "Marginal, small", "", "", ""),
        ("Articular cartilage", "Grade 2 thinning", "", "", ""),
        ("Menisci", "Intact", "", "", ""),
        ("Ligaments (ACL, PCL)", "Intact", "", "", ""),
        ("Joint effusion", "Mild", "", "", ""),
    ], ["Impression: Grade 2 osteoarthritis of the right knee.", "No ligament or meniscal tear."]),
    "Urine Routine": ("Clinical Pathology", [
        ("Colour", "Pale yellow", "", "", ""),
        ("pH", "6.0", "", "4.6 - 8.0", ""),
        ("Specific gravity", "1.015", "", "1.005 - 1.030", ""),
        ("Protein", "Nil", "", "Nil", ""),
        ("Glucose", "Nil", "", "Nil", ""),
        ("Pus cells", "1 - 2", "/hpf", "0 - 5", ""),
        ("Red blood cells", "Nil", "/hpf", "Nil", ""),
    ], ["Urine examination is within normal limits."]),
}


def make_pdf(pages):
    """pages: list of pages, each a list of drawing commands:
    ("text", x, y, size, bold, string) or ("line", x1, y1, x2, y2). Returns PDF bytes (A4)."""
    def esc(s):
        return s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

    objs = [b"<< /Type /Catalog /Pages 2 0 R >>",
            None,                                                     # page tree, filled in below
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>"]
    kids = []
    for cmds in pages:
        ops = []
        for c in cmds:
            if c[0] == "text":
                _, x, y, size, bold, s = c
                ops.append(f"BT /{'F2' if bold else 'F1'} {size} Tf {x} {y} Td ({esc(s)}) Tj ET")
            else:
                _, x1, y1, x2, y2 = c
                ops.append(f"0.6 G 0.5 w {x1} {y1} m {x2} {y2} l S")
        stream = "\n".join(ops).encode("latin-1", "replace")
        objs.append(b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream")
        content_no = len(objs)
        objs.append(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
                    f"/Resources << /Font << /F1 3 0 R /F2 4 0 R >> >> /Contents {content_no} 0 R >>".encode())
        kids.append(f"{len(objs)} 0 R")
    objs[1] = f"<< /Type /Pages /Kids [{' '.join(kids)}] /Count {len(kids)} >>".encode()

    out, offsets = b"%PDF-1.4\n", []
    for i, body in enumerate(objs, 1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % i + body + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1)
    out += b"".join(b"%010d 00000 n \n" % off for off in offsets)
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objs) + 1, xref)
    return out


def _header(report, patient, page, total):
    return [
        ("text", 50, 800, 16, True, "CareMate Diagnostics"),
        ("text", 400, 800, 9, False, "SAMPLE REPORT - demo data"),
        ("text", 50, 784, 9, False, "Pune  |  This file was generated for the CareMate course demo."),
        ("line", 50, 775, 545, 775),
        ("text", 50, 756, 10, True, f"Patient: {patient['name']}"),
        ("text", 300, 756, 10, False, f"Age / Sex: {patient['age']} / {patient['gender']}"),
        ("text", 50, 740, 10, False, f"Report date: {report['date']}"),
        ("text", 300, 740, 10, False, f"Referred by: {report['doctor'] or '-'}"),
        ("line", 50, 730, 545, 730),
        ("text", 480, 40, 9, False, f"Page {page} of {total}"),
    ]


def sample_pdf(report, patient):
    """Two-page sample PDF for a demo report, or None if there is no sample for its title."""
    if report["title"] not in SAMPLES:
        return None
    section, rows, notes = SAMPLES[report["title"]]
    p1 = _header(report, patient, 1, 2) + [
        ("text", 50, 705, 14, True, report["title"]),
        ("text", 50, 688, 10, False, f"Department of {section}"),
        ("text", 50, 660, 10, True, "Test"), ("text", 260, 660, 10, True, "Result"),
        ("text", 360, 660, 10, True, "Unit"), ("text", 430, 660, 10, True, "Reference range"),
        ("line", 50, 652, 545, 652),
    ]
    y = 632
    for test, result, unit, ref, flag in rows:
        p1 += [("text", 50, y, 10, False, test),
               ("text", 260, y, 10, bool(flag), result + (f"  {flag}" if flag else "")),
               ("text", 360, y, 10, False, unit), ("text", 430, y, 10, False, ref)]
        y -= 22
    p1 += [("line", 50, y + 8, 545, y + 8), ("text", 50, y - 12, 9, False, "H = above the reference range.")]

    p2 = _header(report, patient, 2, 2) + [
        ("text", 50, 705, 14, True, "Interpretation"),
        *[("text", 50, 680 - 18 * i, 11, False, line) for i, line in enumerate(notes)],
        ("text", 50, 600, 14, True, "Notes"),
        ("text", 50, 578, 10, False, f"Summary on file: {report['notes']}"),
        ("text", 50, 560, 10, False, "Results relate only to the sample tested. Reference ranges vary by lab."),
        ("line", 50, 480, 250, 480),
        ("text", 50, 465, 10, False, "Consultant pathologist / radiologist"),
        ("text", 50, 420, 9, False, "SAMPLE - generated demo file, not a real medical report."),
    ]
    return make_pdf([p1, p2])


def sample_filename(report):
    return "sample_%s_%s.pdf" % (report["patient_id"], re.sub(r"[^a-z0-9]+", "-", report["title"].lower()).strip("-"))


def ensure_sample_file(report, patient):
    """Write the sample PDF to uploads/ (once) and return its file name, or None."""
    data = sample_pdf(report, patient)
    if data is None:
        return None
    name = sample_filename(report)
    path = os.path.join(UPLOAD_DIR, name)
    if not os.path.exists(path):
        os.makedirs(UPLOAD_DIR, exist_ok=True)
        with open(path, "wb") as f:
            f.write(data)
    return name
