-- CareMate schema (Supabase Postgres)
-- The database only STORES the data so it survives a restart.
-- On startup every row is loaded back into our own data structures (dsa/),
-- and those structures answer every query in the app.
-- Safe to run again: every statement uses IF NOT EXISTS.
--
-- Row Level Security is ON for every table with no policies: Supabase's public
-- REST API (anon key) can read nothing. The app connects as the table owner,
-- which RLS does not restrict.

-- ---------------------------------------------------------------- users
CREATE TABLE IF NOT EXISTS patients (
    id          VARCHAR(10)  PRIMARY KEY,          -- e.g. P1
    name        VARCHAR(100) NOT NULL,
    age         INT,
    gender      VARCHAR(10),
    blood_group VARCHAR(5),
    location    VARCHAR(100),                      -- a place on the city map
    phone       VARCHAR(20),
    active      BOOLEAN NOT NULL DEFAULT TRUE      -- admin can deactivate
);

CREATE TABLE IF NOT EXISTS doctors (
    id          VARCHAR(10)  PRIMARY KEY,          -- e.g. D4
    name        VARCHAR(100) NOT NULL,
    specialty   VARCHAR(100),
    clinic      VARCHAR(150),
    fee         NUMERIC(8,2) NOT NULL DEFAULT 500, -- default booking fee (paid at clinic)
    auto_accept BOOLEAN NOT NULL DEFAULT TRUE,     -- confirm bookings instantly?
    phone       VARCHAR(20),
    active      BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS admins (
    id     VARCHAR(10)  PRIMARY KEY,               -- e.g. AD7
    name   VARCHAR(100) NOT NULL,
    active BOOLEAN NOT NULL DEFAULT TRUE
);

-- every slot a doctor offers, with its fee. Which ones are still free is worked out from appointments
CREATE TABLE IF NOT EXISTS doctor_slots (
    doctor_id VARCHAR(10)  NOT NULL REFERENCES doctors(id) ON DELETE CASCADE,
    slot      VARCHAR(16)  NOT NULL,               -- 'YYYY-MM-DD HH:MM'
    fee       NUMERIC(8,2) NOT NULL,
    PRIMARY KEY (doctor_id, slot)
);

-- ---------------------------------------------------------------- reports
CREATE TABLE IF NOT EXISTS reports (
    id          VARCHAR(10)  PRIMARY KEY,
    patient_id  VARCHAR(10)  NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    title       VARCHAR(150) NOT NULL,
    type        VARCHAR(50),
    date        DATE         NOT NULL,
    doctor      VARCHAR(100),
    notes       TEXT,
    filename    VARCHAR(255),                      -- file saved in uploads/
    uploaded_by VARCHAR(10)  REFERENCES doctors(id) -- NULL = uploaded by the patient
);

-- ---------------------------------------------------------------- appointments
CREATE TABLE IF NOT EXISTS appointments (
    id         VARCHAR(10)  PRIMARY KEY,
    patient_id VARCHAR(10)  NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    doctor_id  VARCHAR(10)  NOT NULL REFERENCES doctors(id)  ON DELETE CASCADE,
    slot       VARCHAR(16)  NOT NULL,
    fee        NUMERIC(8,2) NOT NULL,
    priority   SMALLINT     NOT NULL,              -- 1 Emergency, 2 Urgent, 3 Routine
    reason     VARCHAR(255),
    status     VARCHAR(10)  NOT NULL               -- Pending / Confirmed / Rejected / Cancelled / Completed
);

-- people waiting for a slot (loaded back into the FIFO Queue in id order)
CREATE TABLE IF NOT EXISTS waitlist (
    id         VARCHAR(10)  PRIMARY KEY,
    doctor_id  VARCHAR(10)  NOT NULL REFERENCES doctors(id)  ON DELETE CASCADE,
    patient_id VARCHAR(10)  NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    priority   SMALLINT     NOT NULL,
    reason     VARCHAR(255),
    requested  VARCHAR(16)                         -- the slot they asked for, or 'Any'
);

-- ---------------------------------------------------------------- prescriptions
CREATE TABLE IF NOT EXISTS prescriptions (
    id         VARCHAR(10) PRIMARY KEY,
    patient_id VARCHAR(10) NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    doctor_id  VARCHAR(10) NOT NULL REFERENCES doctors(id)  ON DELETE CASCADE,
    date       DATE        NOT NULL,
    notes      TEXT
);

-- one row per medicine in a prescription (one-to-many)
CREATE TABLE IF NOT EXISTS prescription_items (
    id              INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    prescription_id VARCHAR(10)  NOT NULL REFERENCES prescriptions(id) ON DELETE CASCADE,
    medicine        VARCHAR(100) NOT NULL,
    dose            VARCHAR(50),
    frequency       VARCHAR(20),
    days            INT
);

-- every medicine name the autocomplete Trie knows
CREATE TABLE IF NOT EXISTS medicines (
    name VARCHAR(100) PRIMARY KEY
);

-- ---------------------------------------------------------------- city map + stores
CREATE TABLE IF NOT EXISTS places (                -- graph vertices
    name VARCHAR(100) PRIMARY KEY,
    x    INT NOT NULL,                             -- only used to draw the map
    y    INT NOT NULL
);

CREATE TABLE IF NOT EXISTS roads (                 -- graph edges (undirected)
    id      INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    place_a VARCHAR(100) NOT NULL REFERENCES places(name) ON DELETE CASCADE,
    place_b VARCHAR(100) NOT NULL REFERENCES places(name) ON DELETE CASCADE,
    km      NUMERIC(5,1) NOT NULL
);

CREATE TABLE IF NOT EXISTS stores (
    id    VARCHAR(10)  PRIMARY KEY,
    name  VARCHAR(100) NOT NULL,
    node  VARCHAR(100) NOT NULL REFERENCES places(name),  -- the store's vertex on the map
    hours VARCHAR(50),
    phone VARCHAR(20)
);

CREATE TABLE IF NOT EXISTS store_stock (           -- many-to-many: store <-> medicine
    store_id VARCHAR(10)  NOT NULL REFERENCES stores(id) ON DELETE CASCADE,
    medicine VARCHAR(100) NOT NULL,
    PRIMARY KEY (store_id, medicine)
);

-- ---------------------------------------------------------------- activity log (a Stack in the app)
CREATE TABLE IF NOT EXISTS activity_log (
    id         INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    message    VARCHAR(255) NOT NULL,
    patient_id VARCHAR(10),                        -- who may see this event
    doctor_id  VARCHAR(10),
    created_at TIMESTAMPTZ DEFAULT now()
);

-- ---------------------------------------------------------------- lock the public REST API out
ALTER TABLE patients           ENABLE ROW LEVEL SECURITY;
ALTER TABLE doctors            ENABLE ROW LEVEL SECURITY;
ALTER TABLE admins             ENABLE ROW LEVEL SECURITY;
ALTER TABLE doctor_slots       ENABLE ROW LEVEL SECURITY;
ALTER TABLE reports            ENABLE ROW LEVEL SECURITY;
ALTER TABLE appointments       ENABLE ROW LEVEL SECURITY;
ALTER TABLE waitlist           ENABLE ROW LEVEL SECURITY;
ALTER TABLE prescriptions      ENABLE ROW LEVEL SECURITY;
ALTER TABLE prescription_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE medicines          ENABLE ROW LEVEL SECURITY;
ALTER TABLE places             ENABLE ROW LEVEL SECURITY;
ALTER TABLE roads              ENABLE ROW LEVEL SECURITY;
ALTER TABLE stores             ENABLE ROW LEVEL SECURITY;
ALTER TABLE store_stock        ENABLE ROW LEVEL SECURITY;
ALTER TABLE activity_log       ENABLE ROW LEVEL SECURITY;
