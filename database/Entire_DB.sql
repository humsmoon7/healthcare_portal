-- ============================================================
--  HealthCare Reception Portal — Complete Database Setup
--  Run this file in MySQL Workbench or MySQL CLI to set up
--  the entire database from scratch.
--  Command: mysql -u root -p < healthcare_db.sql
-- ============================================================

-- Create and select database
CREATE DATABASE IF NOT EXISTS healthcare_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE healthcare_db;

-- ============================================================
--  TABLE: users
--  Stores reception staff and admin login accounts
-- ============================================================
CREATE TABLE IF NOT EXISTS users (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    username    VARCHAR(50) UNIQUE NOT NULL,
    password    VARCHAR(255) NOT NULL,
    full_name   VARCHAR(100) NOT NULL,
    role        ENUM('admin', 'reception') DEFAULT 'reception',
    is_active   TINYINT(1) DEFAULT 1,
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================
--  TABLE: patients
--  Stores patient records
-- ============================================================
CREATE TABLE IF NOT EXISTS patients (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    patient_id      VARCHAR(20) UNIQUE NOT NULL,
    full_name       VARCHAR(100) NOT NULL,
    age             INT NOT NULL,
    gender          ENUM('Male', 'Female', 'Other') NOT NULL,
    phone           VARCHAR(10) NOT NULL,
    email           VARCHAR(100),
    address         TEXT,
    blood_group     VARCHAR(5),
    medical_history TEXT,
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================
--  TABLE: doctors
--  Stores doctor profiles
--  is_deleted = 1 means soft-deleted (shows in history section)
-- ============================================================
CREATE TABLE IF NOT EXISTS doctors (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    full_name       VARCHAR(100) NOT NULL,
    specialization  VARCHAR(100) NOT NULL,
    department      VARCHAR(100) NOT NULL,
    phone           VARCHAR(10) NOT NULL,
    email           VARCHAR(100),
    is_active       TINYINT(1) DEFAULT 1,
    is_deleted      TINYINT(1) DEFAULT 0,
    working_hours   VARCHAR(100),
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================
--  TABLE: appointments
--  Stores all patient appointments
-- ============================================================
CREATE TABLE IF NOT EXISTS appointments (
    id                  INT AUTO_INCREMENT PRIMARY KEY,
    appointment_id      VARCHAR(20) UNIQUE NOT NULL,
    patient_id          INT NOT NULL,
    doctor_id           INT NOT NULL,
    appointment_date    DATE NOT NULL,
    appointment_time    TIME NOT NULL,
    reason              TEXT,
    status              ENUM('Scheduled', 'Completed', 'Cancelled') DEFAULT 'Scheduled',
    created_at          DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (patient_id) REFERENCES patients(id) ON DELETE CASCADE,
    FOREIGN KEY (doctor_id)  REFERENCES doctors(id)  ON DELETE CASCADE
);

-- ============================================================
--  TABLE: queue
--  Stores daily queue tokens
--  priority: 0 = Normal, 1 = Senior Citizen (60+), 2 = Emergency
-- ============================================================
CREATE TABLE IF NOT EXISTS queue (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    token_number    INT NOT NULL,
    patient_id      INT NOT NULL,
    doctor_id       INT NOT NULL,
    status          ENUM('Waiting', 'Called', 'Completed') DEFAULT 'Waiting',
    priority        INT DEFAULT 0,
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    called_at       DATETIME,
    completed_at    DATETIME,
    FOREIGN KEY (patient_id) REFERENCES patients(id) ON DELETE CASCADE,
    FOREIGN KEY (doctor_id)  REFERENCES doctors(id)  ON DELETE CASCADE
);

-- ============================================================
--  TABLE: prescription_templates
--  Reusable prescription templates
-- ============================================================
CREATE TABLE IF NOT EXISTS prescription_templates (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    name        VARCHAR(100) NOT NULL,
    content     TEXT NOT NULL,
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================
--  TABLE: prescriptions
--  Stores written prescriptions per patient visit
-- ============================================================
CREATE TABLE IF NOT EXISTS prescriptions (
    id                  INT AUTO_INCREMENT PRIMARY KEY,
    patient_id          INT NOT NULL,
    doctor_id           INT NOT NULL,
    appointment_id      INT,
    prescription_date   DATE NOT NULL,
    content             TEXT NOT NULL,
    created_at          DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (patient_id)     REFERENCES patients(id)     ON DELETE CASCADE,
    FOREIGN KEY (doctor_id)      REFERENCES doctors(id)      ON DELETE CASCADE,
    FOREIGN KEY (appointment_id) REFERENCES appointments(id) ON DELETE SET NULL
);

-- ============================================================
--  INDEXES — for faster queries
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_appointments_date     ON appointments(appointment_date);
CREATE INDEX IF NOT EXISTS idx_appointments_patient  ON appointments(patient_id);
CREATE INDEX IF NOT EXISTS idx_appointments_doctor   ON appointments(doctor_id);
CREATE INDEX IF NOT EXISTS idx_queue_created         ON queue(created_at);
CREATE INDEX IF NOT EXISTS idx_queue_doctor          ON queue(doctor_id);
CREATE INDEX IF NOT EXISTS idx_prescriptions_patient ON prescriptions(patient_id);

-- ============================================================
--  SEED DATA: Default admin and reception user
--  Admin    → username: admin    / password: admin123
--  Reception → username: reception / password: reception123
-- ============================================================
INSERT INTO users (username, password, full_name, role, is_active) VALUES
('admin',     'admin123',      'Administrator',   'admin',     1),
('reception', 'reception123',  'Reception Staff', 'reception', 1)
ON DUPLICATE KEY UPDATE username = username;

-- ============================================================
--  SEED DATA: Sample doctors
-- ============================================================
INSERT INTO doctors (full_name, specialization, department, phone, email, is_active, is_deleted, working_hours) VALUES
('Dr. Arjun Sharma',    'Cardiologist',     'Cardiology',       '9876543210', 'arjun.sharma@hospital.com',   1, 0, 'Mon-Sat 9AM-5PM'),
('Dr. Priya Nair',      'Pediatrician',     'Pediatrics',       '9876543211', 'priya.nair@hospital.com',     1, 0, 'Mon-Fri 10AM-6PM'),
('Dr. Ramesh Iyer',     'Orthopedic Surgeon','Orthopedics',     '9876543212', 'ramesh.iyer@hospital.com',    1, 0, 'Mon-Sat 8AM-4PM'),
('Dr. Sunita Reddy',    'General Physician', 'General Medicine','9876543213', 'sunita.reddy@hospital.com',   1, 0, 'Mon-Sun 8AM-8PM'),
('Dr. Vikram Mehta',    'Neurologist',      'Neurology',        '9876543214', 'vikram.mehta@hospital.com',   1, 0, 'Tue-Sat 9AM-5PM')
ON DUPLICATE KEY UPDATE full_name = full_name;

-- ============================================================
--  SEED DATA: Sample patients
-- ============================================================
INSERT INTO patients (patient_id, full_name, age, gender, phone, email, blood_group, medical_history) VALUES
('P00001', 'Anitha Krishnan',  34, 'Female', '9845012345', 'anitha.k@email.com',  'B+', 'Hypertension'),
('P00002', 'Mohan Das',        62, 'Male',   '9845012346', 'mohan.d@email.com',   'O+', 'Diabetes Type 2'),
('P00003', 'Lakshmi Venkat',   28, 'Female', '9845012347', NULL,                  'A+', NULL),
('P00004', 'Suresh Babu',      45, 'Male',   '9845012348', 'suresh.b@email.com',  'AB+','Asthma'),
('P00005', 'Deepa Menon',      55, 'Female', '9845012349', NULL,                  'B-', 'Thyroid')
ON DUPLICATE KEY UPDATE patient_id = patient_id;

-- ============================================================
--  SEED DATA: Sample prescription templates
-- ============================================================
INSERT INTO prescription_templates (name, content) VALUES
(
  'General Checkup',
  'Patient Name: {patient_name}\nDate: {date}\nPrescribed by: Dr. {doctor_name}\n\n---\n\nDiagnosis:\n\nMedications:\n1. \n2. \n3. \n\nInstructions:\n- Take medicines as prescribed\n- Drink plenty of water\n- Follow up in 7 days\n\nNext Visit: '
),
(
  'Fever & Cold',
  'Patient Name: {patient_name}\nDate: {date}\nPrescribed by: Dr. {doctor_name}\n\n---\n\nDiagnosis: Viral fever / Upper respiratory infection\n\nMedications:\n1. Paracetamol 500mg — 1 tab every 6 hrs (if temp > 100F)\n2. Cetirizine 10mg — 1 tab at night\n3. Vitamin C 500mg — 1 tab daily\n\nInstructions:\n- Rest for 3 days\n- Drink warm fluids\n- Avoid cold food/drinks\n- Return if fever persists beyond 3 days\n\nNext Visit: If no improvement in 3 days'
)
ON DUPLICATE KEY UPDATE name = name;

-- ============================================================
--  Done! Your database is ready.
--  Default logins:
--    Admin:      username=admin       password=admin123
--    Reception:  username=reception   password=reception123
-- ============================================================
SELECT 'healthcare_db setup complete!' AS Status;

--
--bashmysql -u root -p < healthcare_db.sql

--Default logins after setup:

--Role
--Username          Password
--Admin             admin123
--Reception         reception123
--