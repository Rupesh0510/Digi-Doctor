-- ============================================================
-- DIGI DOCTOR - Enhanced Database Schema
-- ============================================================

CREATE DATABASE IF NOT EXISTS digi_doctor_db;
USE digi_doctor_db;

-- -------------------------------------------------------
-- 1. USERS TABLE (Receptionist + Admin login)
-- -------------------------------------------------------
CREATE TABLE IF NOT EXISTS users (
    user_id     INT AUTO_INCREMENT PRIMARY KEY,
    username    VARCHAR(50)  NOT NULL UNIQUE,
    password    VARCHAR(255) NOT NULL,          -- bcrypt hashed
    full_name   VARCHAR(100) NOT NULL,
    role        ENUM('receptionist','admin') NOT NULL DEFAULT 'receptionist',
    is_active   BOOLEAN NOT NULL DEFAULT TRUE,
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- -------------------------------------------------------
-- 2. DOCTORS TABLE
-- -------------------------------------------------------
CREATE TABLE IF NOT EXISTS doctors (
    doctor_id       INT AUTO_INCREMENT PRIMARY KEY,
    name            VARCHAR(100) NOT NULL,
    specialization  VARCHAR(100) NOT NULL,
    email           VARCHAR(100) UNIQUE,
    phone           VARCHAR(15),
    experience_yrs  INT DEFAULT 0,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- -------------------------------------------------------
-- 3. DOCTOR AVAILABILITY TABLE
-- -------------------------------------------------------
CREATE TABLE IF NOT EXISTS doctor_availability (
    availability_id INT AUTO_INCREMENT PRIMARY KEY,
    doctor_id       INT NOT NULL,
    day_of_week     ENUM('Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday') NOT NULL,
    start_time      TIME NOT NULL,
    end_time        TIME NOT NULL,
    slot_duration   INT NOT NULL DEFAULT 30,    -- minutes per slot
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    FOREIGN KEY (doctor_id) REFERENCES doctors(doctor_id) ON DELETE CASCADE,
    UNIQUE KEY uniq_doc_day (doctor_id, day_of_week)
);

-- -------------------------------------------------------
-- 4. PATIENTS TABLE
-- -------------------------------------------------------
CREATE TABLE IF NOT EXISTS patients (
    patient_id  INT AUTO_INCREMENT PRIMARY KEY,
    name        VARCHAR(100) NOT NULL,
    age         INT,
    gender      VARCHAR(10),
    email       VARCHAR(100) UNIQUE,
    phone       VARCHAR(15) UNIQUE,
    address     TEXT,
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- -------------------------------------------------------
-- 5. APPOINTMENTS TABLE
-- -------------------------------------------------------
CREATE TABLE IF NOT EXISTS appointments (
    appointment_id      INT AUTO_INCREMENT PRIMARY KEY,
    doctor_id           INT NOT NULL,
    patient_id          INT NOT NULL,
    appointment_date    DATE NOT NULL,
    appointment_time    TIME NOT NULL,
    status              ENUM('Pending','Confirmed','Completed','Cancelled') NOT NULL DEFAULT 'Pending',
    notes               TEXT,
    booked_by           INT,                    -- user_id of receptionist
    created_at          DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at          DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (doctor_id)   REFERENCES doctors(doctor_id) ON DELETE CASCADE,
    FOREIGN KEY (patient_id)  REFERENCES patients(patient_id) ON DELETE CASCADE,
    FOREIGN KEY (booked_by)   REFERENCES users(user_id) ON DELETE SET NULL,
    UNIQUE KEY no_double_book (doctor_id, appointment_date, appointment_time)
);

-- -------------------------------------------------------
-- SEED DATA
-- -------------------------------------------------------

-- Default admin + receptionist (password: Admin@123 and Recept@123 - change after setup)
INSERT INTO users (username, password, full_name, role) VALUES
('admin',       '$2b$12$8K1p/a0dR0bWl.A4sTgJieR0HnmmXHiuLCNp8hREOG0B68R1sX7Ky', 'System Admin', 'admin'),
('reception1',  '$2b$12$LXx3l.WRvlxXKqzgM9GW3OD/bMbVU6y6jtSwVNPvL3k2L5Rqm.8Ju', 'Priya Receptionist', 'receptionist');

-- Sample doctors
INSERT INTO doctors (name, specialization, email, phone, experience_yrs) VALUES
('Dr. Ravi Kumar',    'Cardiologist',     'ravi.kumar@digidoctor.com',   '9876543210', 15),
('Dr. Priya Sharma',  'Dermatologist',    'priya.sharma@digidoctor.com', '9123456780', 12),
('Dr. Amit Verma',    'Orthopedic',       'amit.verma@digidoctor.com',   '9988776601', 18),
('Dr. Sneha Reddy',   'Gynecologist',     'sneha.reddy@digidoctor.com',  '9988776602', 10),
('Dr. Kiran Bhat',    'Pediatrician',     'kiran.bhat@digidoctor.com',   '9988776603', 8),
('Dr. Suresh Rao',    'Neurologist',      'suresh.rao@digidoctor.com',   '9988776604', 20),
('Dr. Meena Pillai',  'General Physician','meena.pillai@digidoctor.com', '9988776605', 6);

-- Sample availability (Mon-Sat, 9am-5pm, 30min slots)
INSERT INTO doctor_availability (doctor_id, day_of_week, start_time, end_time, slot_duration) VALUES
(1,'Monday','09:00','17:00',30),(1,'Tuesday','09:00','17:00',30),(1,'Wednesday','09:00','17:00',30),
(1,'Thursday','09:00','17:00',30),(1,'Friday','09:00','17:00',30),(1,'Saturday','09:00','13:00',30),
(2,'Monday','10:00','18:00',30),(2,'Tuesday','10:00','18:00',30),(2,'Wednesday','10:00','18:00',30),
(2,'Thursday','10:00','18:00',30),(2,'Friday','10:00','18:00',30),
(3,'Monday','08:00','16:00',30),(3,'Wednesday','08:00','16:00',30),(3,'Friday','08:00','16:00',30),
(4,'Tuesday','09:00','17:00',30),(4,'Thursday','09:00','17:00',30),(4,'Saturday','09:00','13:00',30),
(5,'Monday','09:00','17:00',30),(5,'Tuesday','09:00','17:00',30),(5,'Wednesday','09:00','17:00',30),
(5,'Thursday','09:00','17:00',30),(5,'Friday','09:00','17:00',30),
(6,'Monday','10:00','18:00',30),(6,'Wednesday','10:00','18:00',30),(6,'Friday','10:00','18:00',30),
(7,'Monday','09:00','17:00',30),(7,'Tuesday','09:00','17:00',30),(7,'Wednesday','09:00','17:00',30),
(7,'Thursday','09:00','17:00',30),(7,'Friday','09:00','17:00',30),(7,'Saturday','09:00','13:00',30);

-- Sample patients
INSERT INTO patients (name, age, gender, email, phone, address) VALUES
('Amit Verma',  30, 'Male',   'amit.v@gmail.com',  '9988776655', 'Hyderabad'),
('Sneha Reddy', 25, 'Female', 'sneha.r@gmail.com', '8877665544', 'Secunderabad');
