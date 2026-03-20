"""
Digi Doctor — Enhanced Flask Backend
Features:
  - Flask-Login based authentication with roles (receptionist / admin)
  - MySQL connection pooling via mysql.connector.pooling
  - Doctor availability + time-slot conflict checking
  - Role-based route protection
  - .env config — no hardcoded credentials
"""

from flask import Flask, request, jsonify, render_template, redirect, url_for, flash, session
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_cors import CORS
import mysql.connector
from mysql.connector import pooling, Error
import bcrypt
import os
from datetime import datetime, timedelta, date
from functools import wraps
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'dev-secret-change-in-production')
CORS(app)

# ─────────────────────────────────────────────
# DATABASE CONNECTION POOL
# ─────────────────────────────────────────────

pool = None

def init_pool():
    global pool
    try:
        pool = mysql.connector.pooling.MySQLConnectionPool(
            pool_name="digipool",
            pool_size=5,
            host=os.getenv('DB_HOST', 'localhost'),
            user=os.getenv('DB_USER', 'root'),
            password=os.getenv('DB_PASSWORD', ''),
            database=os.getenv('DB_NAME', 'digi_doctor_db'),
            port=int(os.getenv('DB_PORT', '3306')),
            autocommit=True,
            connection_timeout=10
        )
        print("✅ Connection pool initialized")
        return True
    except Error as e:
        print(f"❌ Pool init failed: {e}")
        return False

def get_db():
    global pool
    if pool is None:
        init_pool()
    try:
        return pool.get_connection()
    except Error as e:
        print(f"❌ DB connection error: {e}")
        return None


# ─────────────────────────────────────────────
# FLASK-LOGIN SETUP
# ─────────────────────────────────────────────

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please log in to access this page.'
login_manager.login_message_category = 'warning'


class User(UserMixin):
    def __init__(self, user_id, username, full_name, role):
        self.id = user_id
        self.username = username
        self.full_name = full_name
        self.role = role

    def is_admin(self):
        return self.role == 'admin'

    def is_receptionist(self):
        return self.role in ('receptionist', 'admin')


@login_manager.user_loader
def load_user(user_id):
    db = get_db()
    if not db:
        return None
    try:
        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE user_id = %s AND is_active = TRUE", (user_id,))
        u = cursor.fetchone()
        cursor.close()
        db.close()
        if u:
            return User(u['user_id'], u['username'], u['full_name'], u['role'])
        return None
    except Error:
        return None


def receptionist_required(f):
    """Decorator: only receptionist or admin can access"""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated:
            return jsonify({'error': 'Authentication required', 'redirect': '/login'}), 401
        if not current_user.is_receptionist():
            return jsonify({'error': 'Access denied'}), 403
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    """Decorator: only admin can access"""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated:
            return jsonify({'error': 'Authentication required', 'redirect': '/login'}), 401
        if not current_user.is_admin():
            return jsonify({'error': 'Admin access required'}), 403
        return f(*args, **kwargs)
    return decorated


# ─────────────────────────────────────────────
# PAGE ROUTES
# ─────────────────────────────────────────────

@app.route('/')
def home_page():
    return render_template('index.html')


@app.route('/login', methods=['GET'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return render_template('login.html')


@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html', user=current_user)


@app.route('/doctors-page')
def doctors_page():
    return render_template('doctors.html')


@app.route('/book-appointment')
def book_appointment_page():
    return render_template('book_appointment.html')


@app.route('/receptionist')
@login_required
def receptionist_page():
    return render_template('receptionist.html', user=current_user)


# ─────────────────────────────────────────────
# AUTH API
# ─────────────────────────────────────────────

@app.route('/api/login', methods=['POST'])
def api_login():
    data = request.json or {}
    username = data.get('username', '').strip()
    password = data.get('password', '')

    if not username or not password:
        return jsonify({'error': 'Username and password required', 'success': False}), 400

    db = get_db()
    if not db:
        return jsonify({'error': 'Database connection failed', 'success': False}), 500

    try:
        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE username = %s AND is_active = TRUE", (username,))
        user_row = cursor.fetchone()
        cursor.close()
        db.close()

        if not user_row:
            return jsonify({'error': 'Invalid username or password', 'success': False}), 401

        # Verify bcrypt password
        if not bcrypt.checkpw(password.encode('utf-8'), user_row['password'].encode('utf-8')):
            return jsonify({'error': 'Invalid username or password', 'success': False}), 401

        user = User(user_row['user_id'], user_row['username'], user_row['full_name'], user_row['role'])
        login_user(user, remember=True)

        return jsonify({
            'success': True,
            'message': f'Welcome, {user.full_name}!',
            'user': {'username': user.username, 'full_name': user.full_name, 'role': user.role},
            'redirect': '/receptionist'
        })
    except Error as e:
        return jsonify({'error': str(e), 'success': False}), 500


@app.route('/api/logout', methods=['POST'])
@login_required
def api_logout():
    logout_user()
    return jsonify({'success': True, 'redirect': '/login'})


@app.route('/api/me', methods=['GET'])
def api_me():
    if current_user.is_authenticated:
        return jsonify({
            'logged_in': True,
            'user': {
                'username': current_user.username,
                'full_name': current_user.full_name,
                'role': current_user.role
            }
        })
    return jsonify({'logged_in': False})


# ─────────────────────────────────────────────
# DOCTORS API (public read, protected write)
# ─────────────────────────────────────────────

@app.route('/api/doctors', methods=['GET'])
def get_doctors():
    db = get_db()
    if not db:
        return jsonify({'error': 'Database connection failed'}), 500
    try:
        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT * FROM doctors WHERE is_active = TRUE ORDER BY name")
        doctors = cursor.fetchall()
        cursor.close()
        db.close()
        return jsonify(doctors)
    except Error as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/doctors', methods=['POST'])
@receptionist_required
def add_doctor():
    data = request.json or {}
    if not data.get('name') or not data.get('specialization'):
        return jsonify({'error': 'Name and specialization are required', 'success': False}), 400

    db = get_db()
    if not db:
        return jsonify({'error': 'Database connection failed', 'success': False}), 500
    try:
        cursor = db.cursor()
        cursor.execute(
            "INSERT INTO doctors (name, specialization, email, phone, experience_yrs) VALUES (%s,%s,%s,%s,%s)",
            (data['name'], data['specialization'], data.get('email') or None,
             data.get('phone') or None, int(data.get('experience_yrs', 0)))
        )
        new_id = cursor.lastrowid
        cursor.close()
        db.close()
        return jsonify({'message': 'Doctor added successfully!', 'success': True, 'doctor_id': new_id}), 201
    except Error as e:
        return jsonify({'error': str(e), 'success': False}), 500


@app.route('/api/doctors/<int:doc_id>', methods=['PUT'])
@receptionist_required
def update_doctor(doc_id):
    data = request.json or {}
    db = get_db()
    if not db:
        return jsonify({'error': 'Database connection failed', 'success': False}), 500
    try:
        cursor = db.cursor()
        cursor.execute(
            "UPDATE doctors SET name=%s, specialization=%s, email=%s, phone=%s, experience_yrs=%s WHERE doctor_id=%s",
            (data.get('name'), data.get('specialization'), data.get('email') or None,
             data.get('phone') or None, int(data.get('experience_yrs', 0)), doc_id)
        )
        cursor.close()
        db.close()
        return jsonify({'message': 'Doctor updated!', 'success': True})
    except Error as e:
        return jsonify({'error': str(e), 'success': False}), 500


@app.route('/api/doctors/<int:doc_id>', methods=['DELETE'])
@admin_required
def delete_doctor(doc_id):
    db = get_db()
    if not db:
        return jsonify({'error': 'Database connection failed', 'success': False}), 500
    try:
        cursor = db.cursor()
        cursor.execute("UPDATE doctors SET is_active = FALSE WHERE doctor_id = %s", (doc_id,))
        cursor.close()
        db.close()
        return jsonify({'message': 'Doctor removed!', 'success': True})
    except Error as e:
        return jsonify({'error': str(e), 'success': False}), 500


# ─────────────────────────────────────────────
# AVAILABILITY API
# ─────────────────────────────────────────────

@app.route('/api/doctors/<int:doc_id>/availability', methods=['GET'])
def get_availability(doc_id):
    db = get_db()
    if not db:
        return jsonify({'error': 'Database connection failed'}), 500
    try:
        cursor = db.cursor(dictionary=True)
        cursor.execute(
            "SELECT * FROM doctor_availability WHERE doctor_id=%s AND is_active=TRUE ORDER BY FIELD(day_of_week,'Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday')",
            (doc_id,)
        )
        rows = cursor.fetchall()
        for r in rows:
            if isinstance(r.get('start_time'), timedelta):
                r['start_time'] = str(r['start_time'])[:5]
            if isinstance(r.get('end_time'), timedelta):
                r['end_time'] = str(r['end_time'])[:5]
        cursor.close()
        db.close()
        return jsonify(rows)
    except Error as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/doctors/<int:doc_id>/slots', methods=['GET'])
def get_available_slots(doc_id):
    """Return available time slots for a doctor on a given date"""
    date_str = request.args.get('date')
    if not date_str:
        return jsonify({'error': 'date parameter required'}), 400

    try:
        appt_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return jsonify({'error': 'Invalid date format, use YYYY-MM-DD'}), 400

    day_name = appt_date.strftime('%A')  # Monday, Tuesday...

    db = get_db()
    if not db:
        return jsonify({'error': 'Database connection failed'}), 500

    try:
        cursor = db.cursor(dictionary=True)

        # Get working hours for this day
        cursor.execute(
            "SELECT * FROM doctor_availability WHERE doctor_id=%s AND day_of_week=%s AND is_active=TRUE",
            (doc_id, day_name)
        )
        avail = cursor.fetchone()
        if not avail:
            cursor.close()
            db.close()
            return jsonify({'slots': [], 'message': f'Doctor is not available on {day_name}'})

        def td_to_time(td):
            if isinstance(td, timedelta):
                total = int(td.total_seconds())
                return f"{total//3600:02d}:{(total%3600)//60:02d}"
            return str(td)[:5]

        start = datetime.strptime(td_to_time(avail['start_time']), '%H:%M')
        end   = datetime.strptime(td_to_time(avail['end_time']),   '%H:%M')
        slot_mins = avail['slot_duration']

        # Get already booked slots
        cursor.execute(
            "SELECT appointment_time FROM appointments WHERE doctor_id=%s AND appointment_date=%s AND status NOT IN ('Cancelled')",
            (doc_id, date_str)
        )
        booked_raw = [r['appointment_time'] for r in cursor.fetchall()]
        booked = set()
        for b in booked_raw:
            if isinstance(b, timedelta):
                total = int(b.total_seconds())
                booked.add(f"{total//3600:02d}:{(total%3600)//60:02d}")
            else:
                booked.add(str(b)[:5])

        cursor.close()
        db.close()

        # Generate slots
        slots = []
        current = start
        while current + timedelta(minutes=slot_mins) <= end:
            slot_str = current.strftime('%H:%M')
            slots.append({'time': slot_str, 'available': slot_str not in booked})
            current += timedelta(minutes=slot_mins)

        return jsonify({'slots': slots, 'day': day_name})
    except Error as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/doctors/<int:doc_id>/availability', methods=['POST'])
@receptionist_required
def set_availability(doc_id):
    data = request.json or {}
    db = get_db()
    if not db:
        return jsonify({'error': 'Database connection failed', 'success': False}), 500
    try:
        cursor = db.cursor()
        cursor.execute(
            """INSERT INTO doctor_availability (doctor_id, day_of_week, start_time, end_time, slot_duration)
               VALUES (%s,%s,%s,%s,%s)
               ON DUPLICATE KEY UPDATE start_time=%s, end_time=%s, slot_duration=%s, is_active=TRUE""",
            (doc_id, data['day_of_week'], data['start_time'], data['end_time'], data.get('slot_duration', 30),
             data['start_time'], data['end_time'], data.get('slot_duration', 30))
        )
        cursor.close()
        db.close()
        return jsonify({'message': 'Availability saved!', 'success': True}), 201
    except Error as e:
        return jsonify({'error': str(e), 'success': False}), 500


# ─────────────────────────────────────────────
# PATIENTS API (receptionist only for write)
# ─────────────────────────────────────────────

@app.route('/api/patients', methods=['GET'])
@receptionist_required
def get_patients():
    db = get_db()
    if not db:
        return jsonify({'error': 'Database connection failed'}), 500
    try:
        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT * FROM patients ORDER BY name")
        patients = cursor.fetchall()
        for p in patients:
            if p.get('created_at'):
                p['created_at'] = p['created_at'].strftime('%Y-%m-%d %H:%M')
        cursor.close()
        db.close()
        return jsonify(patients)
    except Error as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/patients', methods=['POST'])
def add_patient():
    """Public: anyone can register a patient during booking"""
    data = request.json or {}
    if not data.get('name'):
        return jsonify({'error': 'Name is required', 'success': False}), 400

    db = get_db()
    if not db:
        return jsonify({'error': 'Database connection failed', 'success': False}), 500
    try:
        cursor = db.cursor(dictionary=True)

        # Check existing by phone
        phone = data.get('phone') or None
        if phone:
            cursor.execute("SELECT patient_id FROM patients WHERE phone=%s", (phone,))
            existing = cursor.fetchone()
            if existing:
                cursor.close()
                db.close()
                return jsonify({'success': True, 'patient_id': existing['patient_id'], 'existing': True})

        cursor.execute(
            "INSERT INTO patients (name, age, gender, email, phone, address) VALUES (%s,%s,%s,%s,%s,%s)",
            (data['name'], data.get('age') or None, data.get('gender') or None,
             data.get('email') or None, phone, data.get('address') or None)
        )
        new_id = cursor.lastrowid
        cursor.close()
        db.close()
        return jsonify({'message': 'Patient registered!', 'success': True, 'patient_id': new_id}), 201
    except Error as e:
        return jsonify({'error': str(e), 'success': False}), 500


# ─────────────────────────────────────────────
# APPOINTMENTS API
# ─────────────────────────────────────────────

@app.route('/api/appointments', methods=['GET'])
@receptionist_required
def get_appointments():
    db = get_db()
    if not db:
        return jsonify({'error': 'Database connection failed'}), 500
    try:
        cursor = db.cursor(dictionary=True)
        status_filter = request.args.get('status')
        sql = """
            SELECT a.*, d.name AS doctor_name, d.specialization,
                   p.name AS patient_name, p.age, p.gender, p.phone AS patient_phone,
                   u.full_name AS booked_by_name
            FROM appointments a
            JOIN doctors d ON a.doctor_id = d.doctor_id
            JOIN patients p ON a.patient_id = p.patient_id
            LEFT JOIN users u ON a.booked_by = u.user_id
            {where}
            ORDER BY a.appointment_date DESC, a.appointment_time DESC
        """.format(where="WHERE a.status = %s" if status_filter else "")

        cursor.execute(sql, (status_filter,) if status_filter else ())
        rows = cursor.fetchall()

        for r in rows:
            if r.get('appointment_date'):
                r['appointment_date'] = r['appointment_date'].strftime('%Y-%m-%d')
            if r.get('appointment_time'):
                t = r['appointment_time']
                if isinstance(t, timedelta):
                    total = int(t.total_seconds())
                    r['appointment_time'] = f"{total//3600:02d}:{(total%3600)//60:02d}"
                else:
                    r['appointment_time'] = str(t)[:5]
            if r.get('created_at'):
                r['created_at'] = r['created_at'].strftime('%Y-%m-%d %H:%M')
            if r.get('updated_at'):
                r['updated_at'] = r['updated_at'].strftime('%Y-%m-%d %H:%M')

        cursor.close()
        db.close()
        return jsonify(rows)
    except Error as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/appointments', methods=['POST'])
def book_appointment():
    """Public: patients or receptionist can book appointments"""
    data = request.json or {}

    required = ['patient_name', 'patient_phone', 'doctor_id', 'appointment_date', 'appointment_time']
    missing = [f for f in required if not data.get(f)]
    if missing:
        return jsonify({'error': f'Missing fields: {", ".join(missing)}', 'success': False}), 400

    db = get_db()
    if not db:
        return jsonify({'error': 'Database connection failed', 'success': False}), 500

    try:
        cursor = db.cursor(dictionary=True)

        # ── Conflict check ──────────────────────────────
        cursor.execute(
            "SELECT appointment_id FROM appointments WHERE doctor_id=%s AND appointment_date=%s AND appointment_time=%s AND status NOT IN ('Cancelled')",
            (data['doctor_id'], data['appointment_date'], data['appointment_time'])
        )
        if cursor.fetchone():
            cursor.close()
            db.close()
            return jsonify({'error': 'This time slot is already booked. Please choose another.', 'success': False}), 409

        # ── Patient: find or create ──────────────────────
        cursor.execute("SELECT patient_id FROM patients WHERE phone=%s", (data['patient_phone'],))
        existing = cursor.fetchone()

        if existing:
            patient_id = existing['patient_id']
        else:
            cursor.execute(
                "INSERT INTO patients (name, age, gender, email, phone, address) VALUES (%s,%s,%s,%s,%s,%s)",
                (data['patient_name'], data.get('patient_age') or None,
                 data.get('patient_gender') or None, data.get('patient_email') or None,
                 data['patient_phone'], data.get('patient_address') or None)
            )
            patient_id = cursor.lastrowid

        # ── Book ─────────────────────────────────────────
        booked_by = current_user.id if current_user.is_authenticated else None
        cursor.execute(
            "INSERT INTO appointments (doctor_id, patient_id, appointment_date, appointment_time, status, notes, booked_by) VALUES (%s,%s,%s,%s,%s,%s,%s)",
            (data['doctor_id'], patient_id, data['appointment_date'], data['appointment_time'],
             'Pending', data.get('notes') or None, booked_by)
        )
        appt_id = cursor.lastrowid
        cursor.close()
        db.close()

        return jsonify({
            'message': 'Appointment booked successfully! Awaiting confirmation.',
            'success': True,
            'appointment_id': appt_id,
            'patient_id': patient_id
        }), 201

    except Error as e:
        return jsonify({'error': str(e), 'success': False}), 500


@app.route('/api/appointments/<int:appt_id>/status', methods=['PUT'])
@receptionist_required
def update_appointment_status(appt_id):
    """Only receptionists can confirm/complete/cancel appointments"""
    data = request.json or {}
    new_status = data.get('status')
    valid = ('Pending', 'Confirmed', 'Completed', 'Cancelled')

    if new_status not in valid:
        return jsonify({'error': f'Status must be one of: {", ".join(valid)}', 'success': False}), 400

    db = get_db()
    if not db:
        return jsonify({'error': 'Database connection failed', 'success': False}), 500
    try:
        cursor = db.cursor()
        cursor.execute(
            "UPDATE appointments SET status=%s WHERE appointment_id=%s",
            (new_status, appt_id)
        )
        cursor.close()
        db.close()
        return jsonify({'message': f'Appointment {new_status}!', 'success': True})
    except Error as e:
        return jsonify({'error': str(e), 'success': False}), 500


@app.route('/api/appointments/<int:appt_id>', methods=['DELETE'])
@admin_required
def delete_appointment(appt_id):
    db = get_db()
    if not db:
        return jsonify({'error': 'Database connection failed', 'success': False}), 500
    try:
        cursor = db.cursor()
        cursor.execute("DELETE FROM appointments WHERE appointment_id=%s", (appt_id,))
        cursor.close()
        db.close()
        return jsonify({'message': 'Appointment deleted!', 'success': True})
    except Error as e:
        return jsonify({'error': str(e), 'success': False}), 500


# ─────────────────────────────────────────────
# DASHBOARD STATS (receptionist)
# ─────────────────────────────────────────────

@app.route('/api/stats', methods=['GET'])
@receptionist_required
def get_stats():
    db = get_db()
    if not db:
        return jsonify({'error': 'Database connection failed'}), 500
    try:
        cursor = db.cursor(dictionary=True)
        today = date.today().isoformat()

        cursor.execute("SELECT COUNT(*) AS cnt FROM appointments")
        total = cursor.fetchone()['cnt']

        cursor.execute("SELECT COUNT(*) AS cnt FROM appointments WHERE status='Pending'")
        pending = cursor.fetchone()['cnt']

        cursor.execute("SELECT COUNT(*) AS cnt FROM appointments WHERE status='Confirmed'")
        confirmed = cursor.fetchone()['cnt']

        cursor.execute("SELECT COUNT(*) AS cnt FROM appointments WHERE status='Completed'")
        completed = cursor.fetchone()['cnt']

        cursor.execute("SELECT COUNT(*) AS cnt FROM appointments WHERE appointment_date=%s AND status NOT IN ('Cancelled')", (today,))
        today_count = cursor.fetchone()['cnt']

        cursor.execute("SELECT COUNT(*) AS cnt FROM doctors WHERE is_active=TRUE")
        doctors = cursor.fetchone()['cnt']

        cursor.execute("SELECT COUNT(*) AS cnt FROM patients")
        patients = cursor.fetchone()['cnt']

        cursor.close()
        db.close()

        return jsonify({
            'total_appointments': total,
            'pending': pending,
            'confirmed': confirmed,
            'completed': completed,
            'today': today_count,
            'total_doctors': doctors,
            'total_patients': patients
        })
    except Error as e:
        return jsonify({'error': str(e)}), 500


# ─────────────────────────────────────────────
# STARTUP
# ─────────────────────────────────────────────

if __name__ == '__main__':
    print("\n" + "="*55)
    print("  🏥  DIGI DOCTOR — Enhanced System")
    print("="*55)
    init_pool()
    port = int(os.getenv('PORT', 5000))
    debug = os.getenv('FLASK_ENV', 'development') == 'development'
    print(f"  → http://localhost:{port}")
    print(f"  → Debug: {debug}\n")
    app.run(host='0.0.0.0', port=port, debug=debug)
