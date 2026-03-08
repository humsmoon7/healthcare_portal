from flask import Flask, request, jsonify, session, send_from_directory, make_response
from flask_cors import CORS
from datetime import datetime, date, timedelta
import mysql.connector
from mysql.connector import Error
from functools import wraps
import pytz
import csv
import io

app = Flask(__name__)
app.secret_key = 'b4e7857af640d34b6300d085c660f0e2a7d5ab5a8c2b76e11d5b32f5af4c52c0'
CORS(app, supports_credentials=True)

# ISSUE 12: IST timezone helper
IST = pytz.timezone('Asia/Kolkata')
def get_ist_now():
    return datetime.now(IST)
def get_ist_date():
    return get_ist_now().date()

# Database configuration
DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': 'Student@12307',
    'database': 'healthcare_db'
}

def get_db_connection():
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        return conn
    except Error as e:
        print(f"Error connecting to MySQL: {e}")
        return None

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'error': 'Unauthorized'}), 401
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session or session.get('role') != 'admin':
            return jsonify({'error': 'Admin access required'}), 403
        return f(*args, **kwargs)
    return decorated_function

# Serve frontend files
@app.route('/')
def index():
    return send_from_directory('../frontend', 'index.html')

@app.route('/<path:path>')
def serve_file(path):
    return send_from_directory('../frontend', path)

# ============ AUTHENTICATION ============
@app.route('/login', methods=['POST'])
def login():
    data = request.json
    username = data.get('username')
    password = data.get('password')
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM users WHERE username = %s AND password = %s AND is_active = 1",
                   (username, password))
    user = cursor.fetchone()
    cursor.close()
    conn.close()
    if user:
        session['user_id'] = user['id']
        session['username'] = user['username']
        session['role'] = user['role']
        session['name'] = user['full_name']
        return jsonify({'success': True, 'role': user['role'], 'name': user['full_name']})
    else:
        return jsonify({'error': 'Invalid credentials'}), 401

@app.route('/check-auth')
def check_auth():
    if 'user_id' in session:
        return jsonify({'logged_in': True, 'role': session.get('role'), 'name': session.get('name')})
    return jsonify({'logged_in': False})

@app.route('/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'success': True})

# ============ PATIENTS ============
@app.route('/patients', methods=['GET'])
@login_required
def get_patients():
    search = request.args.get('search', '')
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    if search:
        cursor.execute("""
            SELECT * FROM patients
            WHERE full_name LIKE %s OR phone LIKE %s OR patient_id LIKE %s
            ORDER BY created_at DESC
        """, (f'%{search}%', f'%{search}%', f'%{search}%'))
    else:
        cursor.execute("SELECT * FROM patients ORDER BY created_at DESC")
    patients = cursor.fetchall()
    cursor.close()
    conn.close()
    return jsonify(patients)

@app.route('/patients/<int:id>', methods=['GET'])
@login_required
def get_patient(id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM patients WHERE id = %s", (id,))
    patient = cursor.fetchone()
    cursor.close()
    conn.close()
    if patient:
        return jsonify(patient)
    return jsonify({'error': 'Patient not found'}), 404

@app.route('/patients', methods=['POST'])
@login_required
def add_patient():
    data = request.json
    conn = get_db_connection()
    cursor = conn.cursor()
    # FIX: Use MAX(id) instead of COUNT to avoid duplicates after deletions
    cursor.execute("SELECT MAX(id) as max_id FROM patients")
    result = cursor.fetchone()[0]
    next_num = (result or 0) + 1
    patient_id = f"P{next_num:05d}"
    try:
        cursor.execute("""
            INSERT INTO patients (patient_id, full_name, age, gender, phone, email, address, blood_group, medical_history)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (patient_id, data['full_name'], data['age'], data['gender'],
              data['phone'], data.get('email'), data.get('address'),
              data.get('blood_group'), data.get('medical_history')))
        conn.commit()
        return jsonify({'success': True, 'patient_id': patient_id}), 201
    except Error as e:
        conn.rollback()
        return jsonify({'error': str(e)}), 400
    finally:
        cursor.close()
        conn.close()

@app.route('/patients/<int:id>', methods=['PUT'])
@login_required
def update_patient(id):
    data = request.json
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            UPDATE patients SET full_name=%s, age=%s, gender=%s, phone=%s,
            email=%s, address=%s, blood_group=%s, medical_history=%s WHERE id=%s
        """, (data['full_name'], data['age'], data['gender'], data['phone'],
              data.get('email'), data.get('address'), data.get('blood_group'),
              data.get('medical_history'), id))
        conn.commit()
        return jsonify({'success': True})
    except Error as e:
        conn.rollback()
        return jsonify({'error': str(e)}), 400
    finally:
        cursor.close()
        conn.close()

@app.route('/patients/<int:id>', methods=['DELETE'])
@login_required
def delete_patient(id):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM patients WHERE id=%s", (id,))
        conn.commit()
        return jsonify({'success': True})
    except Error as e:
        conn.rollback()
        return jsonify({'error': str(e)}), 400
    finally:
        cursor.close()
        conn.close()

@app.route('/patients/<int:id>/history', methods=['GET'])
@login_required
def get_patient_history(id):
    date_filter = request.args.get('date')
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    query = """
        SELECT a.*, d.full_name as doctor_name, d.department
        FROM appointments a
        JOIN doctors d ON a.doctor_id = d.id
        WHERE a.patient_id = %s
    """
    params = [id]
    if date_filter:
        query += " AND a.appointment_date = %s"
        params.append(date_filter)
    query += " ORDER BY a.appointment_date DESC, a.appointment_time DESC"
    cursor.execute(query, params)
    history = cursor.fetchall()
    for item in history:
        if isinstance(item.get('appointment_time'), timedelta):
            total_seconds = int(item['appointment_time'].total_seconds())
            h, rem = divmod(total_seconds, 3600)
            m, s = divmod(rem, 60)
            item['appointment_time'] = f"{h:02d}:{m:02d}"
    cursor.close()
    conn.close()
    return jsonify(history)

@app.route('/patients/<int:patient_id>/today-doctor', methods=['GET'])
@login_required
def get_patient_today_doctor(patient_id):
    today = get_ist_date()
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT d.id as doctor_id, d.full_name as doctor_name
        FROM appointments a
        JOIN doctors d ON a.doctor_id = d.id
        WHERE a.patient_id = %s AND a.appointment_date = %s AND a.status = 'Scheduled' AND d.is_active = 1
        LIMIT 1
    """, (patient_id, today))
    result = cursor.fetchone()
    cursor.close()
    conn.close()
    return jsonify(result or {'doctor_id': None, 'doctor_name': None})

# ============ DOCTORS ============
@app.route('/doctors', methods=['GET'])
@login_required
def get_doctors():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    include_all = request.args.get('all', 'false').lower() == 'true'
    if include_all:
        # ISSUE 13: Active+inactive first, then soft-deleted at bottom
        cursor.execute("""
            SELECT *,
                CASE WHEN is_deleted=1 THEN 1 ELSE 0 END as sort_deleted,
                CASE WHEN is_active=1 THEN 0 ELSE 1 END as sort_inactive
            FROM doctors
            ORDER BY sort_deleted ASC, sort_inactive ASC, full_name ASC
        """)
    else:
        # Only active non-deleted doctors for dropdowns
        cursor.execute("SELECT * FROM doctors WHERE is_active = 1 AND (is_deleted IS NULL OR is_deleted=0) ORDER BY full_name")
    doctors = cursor.fetchall()
    cursor.close()
    conn.close()
    return jsonify(doctors)

@app.route('/doctors', methods=['POST'])
@login_required
def add_doctor():
    data = request.json
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO doctors (full_name, specialization, department, phone, email, is_active, working_hours)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (data['full_name'], data['specialization'], data['department'],
              data['phone'], data.get('email'), data.get('is_active', True),
              data.get('working_hours')))
        conn.commit()
        return jsonify({'success': True}), 201
    except Error as e:
        conn.rollback()
        return jsonify({'error': str(e)}), 400
    finally:
        cursor.close()
        conn.close()

@app.route('/doctors/<int:id>', methods=['PUT'])
@login_required
def update_doctor(id):
    data = request.json
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            UPDATE doctors SET full_name=%s, specialization=%s, department=%s,
            phone=%s, email=%s, is_active=%s, working_hours=%s WHERE id=%s
        """, (data['full_name'], data['specialization'], data['department'],
              data['phone'], data.get('email'), data.get('is_active', True),
              data.get('working_hours'), id))
        conn.commit()
        return jsonify({'success': True})
    except Error as e:
        conn.rollback()
        return jsonify({'error': str(e)}), 400
    finally:
        cursor.close()
        conn.close()

# *** NEW: Dedicated toggle-active endpoint for doctors ***
@app.route('/doctors/<int:id>/toggle-active', methods=['PUT'])
@login_required
def toggle_doctor_active(id):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE doctors SET is_active = NOT is_active WHERE id = %s", (id,))
        conn.commit()
        return jsonify({'success': True})
    except Error as e:
        conn.rollback()
        return jsonify({'error': str(e)}), 400
    finally:
        cursor.close()
        conn.close()

@app.route('/doctors/<int:id>', methods=['DELETE'])
@login_required
def delete_doctor(id):
    # ISSUE 13: Soft delete — mark as deleted so history still shows below list
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE doctors SET is_deleted=1, is_active=0 WHERE id=%s", (id,))
        conn.commit()
        return jsonify({'success': True})
    except Error as e:
        conn.rollback()
        return jsonify({'error': str(e)}), 400
    finally:
        cursor.close()
        conn.close()

# ============ APPOINTMENTS ============
@app.route('/appointments', methods=['GET'])
@login_required
def get_appointments():
    date_filter = request.args.get('date')
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    base_query = """
        SELECT a.*, p.full_name as patient_name, p.patient_id as patient_code,
        p.id as patient_db_id,
        d.full_name as doctor_name, d.department
        FROM appointments a
        JOIN patients p ON a.patient_id = p.id
        JOIN doctors d ON a.doctor_id = d.id
    """
    try:
        if date_filter:
            query = base_query + " WHERE a.appointment_date = %s ORDER BY a.appointment_time ASC"
            cursor.execute(query, (date_filter,))
        else:
            query = base_query + " ORDER BY a.appointment_date DESC, a.appointment_time DESC"
            cursor.execute(query)
        appointments = cursor.fetchall()
        for appt in appointments:
            if isinstance(appt.get('appointment_time'), timedelta):
                total_seconds = int(appt['appointment_time'].total_seconds())
                h, rem = divmod(total_seconds, 3600)
                m, s = divmod(rem, 60)
                appt['appointment_time'] = f"{h:02d}:{m:02d}"
        return jsonify(appointments)
    except Exception as e:
        return jsonify({'error': 'Failed to fetch appointments'}), 500
    finally:
        cursor.close()
        conn.close()

@app.route('/appointments', methods=['POST'])
@login_required
def create_appointment():
    data = request.json
    conn = get_db_connection()
    cursor = conn.cursor()
    # Check doctor time conflict
    cursor.execute("""
        SELECT * FROM appointments
        WHERE doctor_id=%s AND appointment_date=%s AND appointment_time=%s AND status='Scheduled'
    """, (data['doctor_id'], data['appointment_date'], data['appointment_time']))
    if cursor.fetchone():
        return jsonify({'error': 'Time slot already booked for this doctor'}), 400
    # ISSUE 5 FIX: Same patient cannot have more than 1 appointment at the same date+time
    cursor.execute("""
        SELECT * FROM appointments
        WHERE patient_id=%s AND appointment_date=%s AND appointment_time=%s AND status='Scheduled'
    """, (data['patient_id'], data['appointment_date'], data['appointment_time']))
    if cursor.fetchone():
        return jsonify({'error': 'This patient already has an appointment at the same date and time'}), 400
    # FIX: Use MAX(id) instead of COUNT to avoid duplicates after deletions
    cursor.execute("SELECT MAX(id) as max_id FROM appointments")
    result = cursor.fetchone()[0]
    next_num = (result or 0) + 1
    appointment_id = f"APT{next_num:05d}"
    try:
        cursor.execute("""
            INSERT INTO appointments (appointment_id, patient_id, doctor_id,
            appointment_date, appointment_time, reason, status)
            VALUES (%s, %s, %s, %s, %s, %s, 'Scheduled')
        """, (appointment_id, data['patient_id'], data['doctor_id'],
              data['appointment_date'], data['appointment_time'], data.get('reason')))
        conn.commit()
        return jsonify({'success': True, 'appointment_id': appointment_id}), 201
    except Error as e:
        conn.rollback()
        return jsonify({'error': str(e)}), 400
    finally:
        cursor.close()
        conn.close()

@app.route('/appointments/today', methods=['GET'])
@login_required
def get_today_appointments():
    """Returns today's appointments for the queue page - includes cancelled ones (greyed out)"""
    today = get_ist_date()
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT a.id, a.patient_id as patient_db_id, a.doctor_id, a.status,
                   p.full_name as patient_name, p.patient_id as patient_code,
                   d.full_name as doctor_name
            FROM appointments a
            JOIN patients p ON a.patient_id = p.id
            JOIN doctors d ON a.doctor_id = d.id
            WHERE a.appointment_date = %s
            ORDER BY a.appointment_time ASC
        """, (today,))
        appointments = cursor.fetchall()
        return jsonify(appointments)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        conn.close()

@app.route('/appointments/status/<int:id>', methods=['PUT'])
@login_required
def update_appointment_status(id):
    data = request.json
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE appointments SET status=%s WHERE id=%s", (data['status'], id))
        conn.commit()
        return jsonify({'success': True})
    except Error as e:
        conn.rollback()
        return jsonify({'error': str(e)}), 400
    finally:
        cursor.close()
        conn.close()

# ============ QUEUE MANAGEMENT ============
@app.route('/queue/generate', methods=['POST'])
@login_required
def generate_token():
    data = request.json
    conn = get_db_connection()
    cursor = conn.cursor()
    today = get_ist_date()
    patient_id = data['patient_id']
    doctor_id = data['doctor_id']

    # ISSUE 3 FIX: Block duplicate token for same patient same day
    cursor.execute("""
        SELECT id FROM queue
        WHERE patient_id = %s AND DATE(created_at) = %s
    """, (patient_id, today))
    if cursor.fetchone():
        cursor.close()
        conn.close()
        return jsonify({'error': 'Token already generated for this patient today'}), 400

    # ISSUE 3 FIX: Require a valid Scheduled appointment for today with selected doctor
    cursor.execute("""
        SELECT id FROM appointments
        WHERE patient_id = %s AND doctor_id = %s
        AND appointment_date = %s AND status = 'Scheduled'
    """, (patient_id, doctor_id, today))
    if not cursor.fetchone():
        cursor.close()
        conn.close()
        return jsonify({'error': 'No scheduled appointment found for this patient with the selected doctor today'}), 400

    cursor.execute("""
        SELECT MAX(token_number) as max_token FROM queue
        WHERE doctor_id = %s AND DATE(created_at) = %s
    """, (doctor_id, today))
    result = cursor.fetchone()
    next_token = (result[0] or 0) + 1

    priority = 0
    if data.get('is_emergency', False):
        priority = 2
    else:
        cursor.execute("SELECT age FROM patients WHERE id = %s", (patient_id,))
        age_result = cursor.fetchone()
        if age_result and age_result[0] >= 60:
            priority = 1
    try:
        cursor.execute("""
            INSERT INTO queue (token_number, patient_id, doctor_id, status, priority)
            VALUES (%s, %s, %s, 'Waiting', %s)
        """, (next_token, patient_id, doctor_id, priority))
        conn.commit()
        return jsonify({'success': True, 'token_number': next_token}), 201
    except Error as e:
        conn.rollback()
        return jsonify({'error': str(e)}), 400
    finally:
        cursor.close()
        conn.close()

@app.route('/queue', methods=['GET'])
@login_required
def get_queue():
    doctor_id = request.args.get('doctor_id')
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    query = """
        SELECT q.*, p.full_name as patient_name, p.patient_id,
        d.full_name as doctor_name
        FROM queue q
        JOIN patients p ON q.patient_id = p.id
        JOIN doctors d ON q.doctor_id = d.id
        WHERE DATE(q.created_at) = CURDATE()
    """
    params = []
    if doctor_id:
        query += " AND q.doctor_id = %s"
        params.append(doctor_id)
    query += " ORDER BY q.priority DESC, q.token_number ASC"
    cursor.execute(query, params)
    queue = cursor.fetchall()
    cursor.close()
    conn.close()
    return jsonify(queue)

@app.route('/queue/<int:id>/call', methods=['PUT'])
@login_required
def call_token(id):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE queue SET status='Called', called_at=NOW() WHERE id=%s", (id,))
        conn.commit()
        return jsonify({'success': True})
    finally:
        cursor.close()
        conn.close()

@app.route('/queue/<int:id>/complete', methods=['PUT'])
@login_required
def complete_token(id):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE queue SET status='Completed', completed_at=NOW() WHERE id=%s", (id,))
        conn.commit()
        return jsonify({'success': True})
    finally:
        cursor.close()
        conn.close()

# ============ PRESCRIPTION SYSTEM ============
@app.route('/prescription_templates', methods=['GET'])
@login_required
def get_templates():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id, name FROM prescription_templates ORDER BY name")
    templates = cursor.fetchall()
    cursor.close()
    conn.close()
    return jsonify(templates)

@app.route('/prescription_templates', methods=['POST'])
@login_required
def add_template():
    data = request.json
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO prescription_templates (name, content) VALUES (%s, %s)",
                       (data['name'], data['content']))
        conn.commit()
        return jsonify({'success': True}), 201
    except Error as e:
        conn.rollback()
        return jsonify({'error': str(e)}), 400
    finally:
        cursor.close()
        conn.close()

@app.route('/prescriptions', methods=['POST'])
@login_required
def create_prescription():
    data = request.json
    patient_id = data['patient_id']
    doctor_id = session.get('user_id', 1)
    appointment_id = data.get('appointment_id')
    template_id = data.get('template_id')
    content = data.get('content')
    today = get_ist_date()
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        if template_id:
            cursor.execute("SELECT content FROM prescription_templates WHERE id = %s", (template_id,))
            template = cursor.fetchone()
            if not template:
                return jsonify({'error': 'Template not found'}), 404
            content = template['content']
        cursor.execute("SELECT full_name FROM patients WHERE id = %s", (patient_id,))
        patient_row = cursor.fetchone()
        if not patient_row:
            return jsonify({'error': 'Patient not found'}), 404
        patient_name = patient_row['full_name']
        cursor.execute("SELECT full_name FROM doctors WHERE id = %s", (doctor_id,))
        doctor_row = cursor.fetchone()
        doctor_name = doctor_row['full_name'] if doctor_row else 'Doctor'
        if content:
            content = content.replace('{patient_name}', patient_name)
            content = content.replace('{date}', str(today))
            content = content.replace('{doctor_name}', doctor_name)
        if not content:
            return jsonify({'error': 'Prescription content required'}), 400
        cursor.execute("""
            INSERT INTO prescriptions (patient_id, doctor_id, appointment_id, prescription_date, content)
            VALUES (%s, %s, %s, %s, %s)
        """, (patient_id, doctor_id, appointment_id, today, content))
        conn.commit()
        return jsonify({'success': True}), 201
    except Error as e:
        conn.rollback()
        return jsonify({'error': str(e)}), 400
    finally:
        cursor.close()
        conn.close()

@app.route('/patients/<int:id>/prescriptions', methods=['GET'])
@login_required
def get_patient_prescriptions(id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT p.*, d.full_name as doctor_name
        FROM prescriptions p
        JOIN doctors d ON p.doctor_id = d.id
        WHERE p.patient_id = %s
        ORDER BY p.prescription_date DESC, p.created_at DESC
    """, (id,))
    prescriptions = cursor.fetchall()
    cursor.close()
    conn.close()
    return jsonify(prescriptions)

# ============ DASHBOARD ============
@app.route('/dashboard/stats', methods=['GET'])
@login_required
def get_dashboard_stats():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    today = get_ist_date()
    cursor.execute("SELECT COUNT(*) as count FROM patients")
    total_patients = cursor.fetchone()['count']
    cursor.execute("SELECT COUNT(*) as count FROM doctors WHERE is_active=1")
    active_doctors = cursor.fetchone()['count']
    cursor.execute("SELECT COUNT(*) as count FROM appointments WHERE appointment_date=%s", (today,))
    today_appointments = cursor.fetchone()['count']
    cursor.execute("SELECT COUNT(*) as count FROM queue WHERE DATE(created_at)=%s AND status='Waiting'", (today,))
    waiting_queue = cursor.fetchone()['count']
    cursor.close()
    conn.close()
    return jsonify({
        'total_patients': total_patients,
        'active_doctors': active_doctors,
        'today_appointments': today_appointments,
        'waiting_queue': waiting_queue
    })

# ============ REPORTS ============
@app.route('/reports/daily', methods=['GET'])
@login_required
def daily_report():
    report_date = request.args.get('date', get_ist_date())
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT COUNT(*) as total_appointments,
        SUM(CASE WHEN status='Completed' THEN 1 ELSE 0 END) as completed,
        SUM(CASE WHEN status='Cancelled' THEN 1 ELSE 0 END) as cancelled
        FROM appointments WHERE appointment_date=%s
    """, (report_date,))
    report = cursor.fetchone() or {'total_appointments': 0, 'completed': 0, 'cancelled': 0}
    cursor.close()
    conn.close()
    return jsonify(report)

@app.route('/reports/doctor-visits', methods=['GET'])
@login_required
def doctor_visits_report():
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    if not start_date or not end_date:
        return jsonify({'error': 'start_date and end_date required'}), 400
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT d.full_name, d.department,
        COUNT(a.id) as visit_count,
        GROUP_CONCAT(DISTINCT p.full_name SEPARATOR ', ') as visitors
        FROM doctors d
        LEFT JOIN appointments a ON a.doctor_id = d.id AND a.appointment_date BETWEEN %s AND %s
        LEFT JOIN patients p ON a.patient_id = p.id
        GROUP BY d.id
        ORDER BY visit_count DESC
    """, (start_date, end_date))
    report = cursor.fetchall()
    cursor.close()
    conn.close()
    return jsonify(report)

# ============ STAFF MANAGEMENT ============
@app.route('/users', methods=['GET'])
@admin_required
def get_users():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id, username, full_name, role, is_active, created_at FROM users ORDER BY full_name")
    users = cursor.fetchall()
    cursor.close()
    conn.close()
    return jsonify(users)

@app.route('/users', methods=['POST'])
@admin_required
def add_user():
    data = request.json
    password = data.get('password')
    if not password:
        return jsonify({'error': 'Password required'}), 400
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO users (username, password, full_name, role, is_active)
            VALUES (%s, %s, %s, %s, %s)
        """, (data['username'], password, data['full_name'], data.get('role', 'reception'),
              data.get('is_active', True)))
        conn.commit()
        return jsonify({'success': True}), 201
    except Error as e:
        conn.rollback()
        return jsonify({'error': str(e)}), 400
    finally:
        cursor.close()
        conn.close()

@app.route('/users/<int:id>', methods=['PUT'])
@admin_required
def update_user(id):
    data = request.json
    conn = get_db_connection()
    cursor = conn.cursor()
    fields = []
    values = []
    if 'full_name' in data:
        fields.append("full_name = %s")
        values.append(data['full_name'])
    if 'role' in data:
        fields.append("role = %s")
        values.append(data['role'])
    if 'is_active' in data:
        fields.append("is_active = %s")
        values.append(1 if data['is_active'] else 0)
    if 'password' in data and data['password']:
        fields.append("password = %s")
        values.append(data['password'])
    if not fields:
        return jsonify({'error': 'No data to update'}), 400
    values.append(id)
    query = f"UPDATE users SET {', '.join(fields)} WHERE id = %s"
    try:
        cursor.execute(query, values)
        conn.commit()
        return jsonify({'success': True})
    except Error as e:
        conn.rollback()
        return jsonify({'error': str(e)}), 400
    finally:
        cursor.close()
        conn.close()

@app.route('/users/<int:id>/toggle-active', methods=['PUT'])
@admin_required
def toggle_user_active(id):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE users SET is_active = NOT is_active WHERE id = %s", (id,))
        conn.commit()
        return jsonify({'success': True})
    except Error as e:
        conn.rollback()
        return jsonify({'error': str(e)}), 400
    finally:
        cursor.close()
        conn.close()

# ============ PRESCRIPTION SESSION — reliable patient passing ============
@app.route('/prescription/set-patient', methods=['POST'])
@login_required
def set_prescription_patient():
    data = request.json
    session['prescription_patient_id'] = data.get('patient_id')
    session['prescription_appointment_id'] = data.get('appointment_id')
    return jsonify({'success': True})

@app.route('/prescription/get-patient', methods=['GET'])
@login_required
def get_prescription_patient():
    return jsonify({
        'patient_id': session.get('prescription_patient_id'),
        'appointment_id': session.get('prescription_appointment_id')
    })

# ============ ISSUE 11: PATIENT HISTORY DOWNLOAD ============
@app.route('/patients/<int:id>/history/download', methods=['GET'])
@login_required
def download_patient_history(id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    # Get patient info
    cursor.execute("SELECT * FROM patients WHERE id = %s", (id,))
    patient = cursor.fetchone()
    if not patient:
        return jsonify({'error': 'Patient not found'}), 404

    # Get appointment history with doctor info
    cursor.execute("""
        SELECT a.appointment_date, a.appointment_time, a.reason, a.status,
               d.full_name as doctor_name, d.specialization, d.department
        FROM appointments a
        JOIN doctors d ON a.doctor_id = d.id
        WHERE a.patient_id = %s
        ORDER BY a.appointment_date DESC, a.appointment_time DESC
    """, (id,))
    appointments = cursor.fetchall()
    for appt in appointments:
        if isinstance(appt.get('appointment_time'), timedelta):
            total_seconds = int(appt['appointment_time'].total_seconds())
            h, rem = divmod(total_seconds, 3600)
            m, s = divmod(rem, 60)
            appt['appointment_time'] = f"{h:02d}:{m:02d}"

    # Get prescription history
    cursor.execute("""
        SELECT p.prescription_date, p.content, d.full_name as doctor_name
        FROM prescriptions p
        JOIN doctors d ON p.doctor_id = d.id
        WHERE p.patient_id = %s
        ORDER BY p.prescription_date DESC
    """, (id,))
    prescriptions = cursor.fetchall()
    cursor.close()
    conn.close()

    # Build CSV content
    output = io.StringIO()
    writer = csv.writer(output)

    # Patient details header
    writer.writerow(['PATIENT HISTORY REPORT'])
    writer.writerow(['Generated on (IST)', get_ist_now().strftime('%d-%m-%Y %I:%M %p')])
    writer.writerow([])
    writer.writerow(['PATIENT DETAILS'])
    writer.writerow(['Patient ID', patient['patient_id']])
    writer.writerow(['Name', patient['full_name']])
    writer.writerow(['Age', patient['age']])
    writer.writerow(['Gender', patient['gender']])
    writer.writerow(['Phone', patient['phone']])
    writer.writerow(['Blood Group', patient.get('blood_group') or 'N/A'])
    writer.writerow(['Medical History', patient.get('medical_history') or 'None'])
    writer.writerow([])

    # Appointment history
    writer.writerow(['APPOINTMENT HISTORY'])
    writer.writerow(['Date', 'Time', 'Doctor', 'Specialization', 'Department', 'Reason', 'Status'])
    if appointments:
        for appt in appointments:
            writer.writerow([
                appt['appointment_date'],
                appt['appointment_time'],
                appt['doctor_name'],
                appt['specialization'],
                appt['department'],
                appt.get('reason') or '-',
                appt['status']
            ])
    else:
        writer.writerow(['No appointments found'])
    writer.writerow([])

    # Prescription history
    writer.writerow(['PRESCRIPTION HISTORY'])
    writer.writerow(['Date', 'Doctor', 'Prescription'])
    if prescriptions:
        for presc in prescriptions:
            writer.writerow([
                presc['prescription_date'],
                presc['doctor_name'],
                presc['content'].replace('\n', ' | ')
            ])
    else:
        writer.writerow(['No prescriptions found'])

    csv_data = output.getvalue()
    output.close()

    response = make_response(csv_data)
    response.headers['Content-Type'] = 'text/csv'
    filename = f"patient_history_{patient['patient_id']}_{get_ist_date()}.csv"
    response.headers['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response

if __name__ == '__main__':
    app.run(debug=True, host='localhost', port=5000)