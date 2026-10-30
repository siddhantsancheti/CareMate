# CareMate: A Personalized Nurse Assistant

A Flask web app for **patients, doctors and admins** where every feature runs on a **data structure or algorithm written from scratch in Python**.
It uses no built-in `heapq`, `bisect` or `sorted()` for the core logic.
Data is **stored in Supabase (Postgres)** so it survives restarts, but every query still runs on our own data structures.

## Features
### Patients
| Feature | What they can do |
|---|---|
| **Reports** | Upload reports (PDF/PNG/JPG), search, filter by type, sort, find reports between two dates or on an exact date, open files, delete their own uploads. Reports a doctor uploads appear here too |
| **Appointments** | See each doctor's free slots with the fee, pick an urgency (Emergency / Urgent / Routine), book, cancel. If a doctor is full, join the waiting list and get the next slot that opens |
| **Prescriptions** | A doctor's prescription appears the moment it's sent. Recent prescriptions are listed with *New* / *Active* badges, any one can be opened, and today's reminders come from every medicine still running |
| **Nearest medical stores** | Shortest road distance to every store around VIIT, Kondhwa, the route on a map, and which stores stock all the medicines they're taking now |

### Doctors
| Feature | What they can do |
|---|---|
| **Bookings** | Turn **auto-accept** on (bookings are confirmed instantly) or off (accept or decline each request). See the patient queue (day by day; within a day the most urgent first), call the next patient, and see the waiting list |
| **Slots & fees** | For any day, tick the time slots they offer and set that day's fee. Booked slots can't be removed |
| **My patients** | Once a booking is accepted, the doctor can open that patient's reports, **upload test reports** to them, and **write prescriptions** (with medicine autocomplete) that reach the patient immediately. They can withdraw their own newest prescription |

### Admins
| Feature | What they can do |
|---|---|
| **Insights** | Most booked doctors, most prescribed medicines, totals (patients, doctors, appointments, fees from completed visits), platform activity |
| **Users** | Add, edit, deactivate and reactivate patients, doctors and admins. Deactivated users can't sign in or be booked; their records are kept |

### Accounts
Everyone logs in with an email and password (passwords are stored hashed). **Anyone can sign up** as a patient or a doctor from the login page; admins are added by an admin.

Demo accounts:

| Role | Email | Password |
|---|---|---|
| Patient (Siddhant Sancheti) | `siddhant@caremate.in` | `siddhant123` |
| Doctor (Dr. Arjun Patil) | `arjun@caremate.in` | `arjun123` |
| Admin | `admin@caremate.in` | `admin123` |

The map covers Kondhwa around VIIT (VIIT College, Kondhwa Budruk, Kondhwa Khurd, NIBM Road, Upper Indira Nagar, Bibvewadi, Katraj, Yewalewadi, Undri, Salunke Vihar) with 4 medical stores. Distances are approximate.

## Which data structure powers what
| Feature | Data structure / algorithm | Complexity | File |
|---|---|---|---|
| Patients & doctors lookup | Hash Table | O(1) avg | `dsa/hash_table.py` |
| Reports library | Doubly Linked List | insert O(1) | `dsa/linked_list.py` |
| Reports between two dates | Binary Search Tree | O(h + k) | `dsa/bst.py` |
| Doctor's patient queue | Min-Heap Priority Queue | O(log n) | `dsa/heap.py` |
| Waiting list | Queue (FIFO) | O(1) | `dsa/queue_stack.py` |
| Prescription history | Stack (LIFO) | O(1) | `dsa/queue_stack.py` |
| Medicine autocomplete | Tree | O(P + K) | `dsa/trie.py` |
| Nearest medical store | Graph | O((V+E) log V) | `dsa/graph.py` |

## How to run (Windows)
```bash
cd "Course project\nurse_assistant"
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python app.py
```
Open **http://127.0.0.1:5000** in your browser.

Without `supabase_config.ini` the app runs **in memory** with demo data and starts fresh every time.

## System architecture
```mermaid
flowchart TB
    %% ---------- Users ----------
    subgraph Users["👥 Users (email + password login)"]
        P["🧑 Patient"]
        D["🩺 Doctor"]
        A["🛡️ Admin"]
    end

    Browser["🌐 Web browser<br/>HTML · CSS · JavaScript<br/>(autocomplete, slot editor, SVG map, PDF viewer)"]
    P --> Browser
    D --> Browser
    A --> Browser

    %% ---------- Web layer ----------
    subgraph Web["Web layer · Flask (app.py)"]
        Routes["Routes by role<br/>Reports · Appointments · Prescriptions · Stores<br/>Bookings · Slots & fees · My patients<br/>Insights · Users"]
        Guard["Checks<br/>role locks · input validation<br/>report access only after accepted booking"]
        Tpl["Jinja2 templates + static/style.css"]
        Routes --> Guard
        Routes --> Tpl
    end
    Browser <-->|"HTTP requests / pages"| Routes

    %% ---------- Service layer ----------
    subgraph Service["Service layer · services.py (Care Mate)"]
        Logic["Business logic<br/>booking · accept/decline · waiting list<br/>prescriptions · reminders · store search<br/>admin rankings · activity log"]
    end
    Guard --> Logic

    %% ---------- Storage ----------
    subgraph Storage["Storage"]
        DB["db.py<br/>write-through on every change<br/>restore() on startup"]
        SB[("☁️ Supabase Postgres<br/>Mumbai · ap-south-1<br/>15 tables · Row Level Security")]
        Files[("📁 uploads/<br/>report PDFs & images")]
        DB <-->|"psycopg · parameterised SQL"| SB
    end
    Logic -->|"save each change"| DB
    DB -->|"data loaded into memory at startup"| Logic
    Guard -->|"upload / serve files"| Files

    classDef user fill:#fde8e1,stroke:#d9583b,color:#15302d
    classDef web fill:#e3f0ec,stroke:#0e6b5f,color:#15302d
    classDef store fill:#e8eefc,stroke:#2f4fa8,color:#15302d
    class P,D,A,Browser user
    class Routes,Guard,Tpl,Logic web
    class DB,SB,Files store
```
