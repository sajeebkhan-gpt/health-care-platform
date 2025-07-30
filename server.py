import http.server
import socketserver
import sqlite3
import urllib.parse
import hashlib
import uuid
import datetime
import os

PORT = 8000
DB_FILE = "healthcare.db"
SESSIONS = {}  # In-memory session store

# Initialize SQLite database
def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        role TEXT NOT NULL
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS symptoms (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        description TEXT NOT NULL,
        date TEXT NOT NULL,
        user_id INTEGER,
        FOREIGN KEY (user_id) REFERENCES users(id)
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS recommendations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        text TEXT NOT NULL,
        date TEXT NOT NULL,
        user_id INTEGER,
        symptom_id INTEGER,
        FOREIGN KEY (user_id) REFERENCES users(id),
        FOREIGN KEY (symptom_id) REFERENCES symptoms(id)
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS appointments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT NOT NULL,
        patient_id INTEGER,
        doctor_id INTEGER,
        FOREIGN KEY (patient_id) REFERENCES users(id),
        FOREIGN KEY (doctor_id) REFERENCES users(id)
    )''')
    conn.commit()
    conn.close()

# Hash password
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# Check session
def get_user_from_session(session_id):
    return SESSIONS.get(session_id)

# HTTP Request Handler
class Handler(http.server.BaseHTTPRequestHandler):
    def log_request(self, code='-', size='-'):
        print(f"Request: {self.path} - Status: {code}")

    def do_GET(self):
        parsed_path = urllib.parse.urlparse(self.path)
        path = parsed_path.path
        user = get_user_from_session(self.headers.get('Cookie', '').replace('session=', ''))

        try:
            if path == '/':
                self.send_response(200)
                self.send_header('Content-type', 'text/html')
                self.end_headers()
                with open('templates/base.html', 'r') as f:
                    self.wfile.write(f.read().encode())
                print(f"Served: {path}")
            elif path == '/static/styles.css':
                self.send_response(200)
                self.send_header('Content-type', 'text/css')
                self.end_headers()
                with open('static/styles.css', 'r') as f:
                    self.wfile.write(f.read().encode())
                print(f"Served: {path}")
            elif path == '/login':
                self.send_response(200)
                self.send_header('Content-type', 'text/html')
                self.end_headers()
                with open('templates/login.html', 'r') as f:
                    self.wfile.write(f.read().encode())
                print(f"Served: {path}")
            elif path == '/signup':
                self.send_response(200)
                self.send_header('Content-type', 'text/html')
                self.end_headers()
                with open('templates/signup.html', 'r') as f:
                    self.wfile.write(f.read().encode())
                print(f"Served: {path}")
            elif path == '/symptom_upload' and user and user['role'] == 'patient':
                self.send_response(200)
                self.send_header('Content-type', 'text/html')
                self.end_headers()
                with open('templates/symptom_upload.html', 'r') as f:
                    self.wfile.write(f.read().encode())
                print(f"Served: {path}")
            elif path == '/dashboard' and user:
                self.send_response(200)
                self.send_header('Content-type', 'text/html')
                self.end_headers()
                conn = sqlite3.connect(DB_FILE)
                c = conn.cursor()
                if user['role'] == 'patient':
                    c.execute("SELECT description, date FROM symptoms WHERE user_id = ?", (user['id'],))
                    symptoms = c.fetchall()
                    c.execute("SELECT r.text, r.date, s.description FROM recommendations r JOIN symptoms s ON r.symptom_id = s.id WHERE r.user_id = ?", (user['id'],))
                    recommendations = c.fetchall()
                    c.execute("SELECT a.date, u.name FROM appointments a JOIN users u ON a.doctor_id = u.id WHERE a.patient_id = ?", (user['id'],))
                    appointments = c.fetchall()
                    template = 'templates/dashboard_patient.html'
                else:
                    c.execute("SELECT s.id, s.description, s.date, u.name FROM symptoms s JOIN users u ON s.user_id = u.id")
                    symptoms = c.fetchall()
                    recommendations = []
                    appointments = []
                    template = 'templates/dashboard_doctor.html'
                conn.close()
                with open(template, 'r') as f:
                    content = f.read()
                    symptom_list = ''.join([f'<li class="p-2 border-b border-cyan-500">{s[0]} ({s[1]})</li>' for s in symptoms]) if user['role'] == 'patient' else ''.join([f'<li class="p-2 border-b border-cyan-500">{s[1]} by {s[3]} ({s[2]}) [<a href="/recommendation?symptom_id={s[0]}" class="text-cyan-400">Add Recommendation</a>]</li>' for s in symptoms])
                    rec_list = ''.join([f'<li class="p-2 border-b border-cyan-500">{r[0]} for {r[2]} ({r[1]})</li>' for r in recommendations])
                    appt_list = ''.join([f'<li class="p-2 border-b border-cyan-500">{a[0]} with {a[1]}</li>' for a in appointments])
                    content = content.replace('{{symptoms}}', symptom_list).replace('{{recommendations}}', rec_list).replace('{{appointments}}', appt_list)
                    self.wfile.write(content.encode())
                print(f"Served: {path}")
            elif path == '/book_appointment' and user and user['role'] == 'patient':
                self.send_response(200)
                self.send_header('Content-type', 'text/html')
                self.end_headers()
                conn = sqlite3.connect(DB_FILE)
                c = conn.cursor()
                c.execute("SELECT id, name FROM users WHERE role = 'doctor'")
                doctors = c.fetchall()
                conn.close()
                with open('templates/book_appointment.html', 'r') as f:
                    content = f.read()
                    doctor_options = ''.join([f'<option value="{d[0]}">{d[1]}</option>' for d in doctors])
                    content = content.replace('{{doctors}}', doctor_options)
                    self.wfile.write(content.encode())
                print(f"Served: {path}")
            elif path == '/recommendation' and user and user['role'] == 'doctor':
                symptom_id = urllib.parse.parse_qs(parsed_path.query).get('symptom_id', [''])[0]
                self.send_response(200)
                self.send_header('Content-type', 'text/html')
                self.end_headers()
                with open('templates/recommendation.html', 'r') as f:
                    content = f.read().replace('{{symptom_id}}', symptom_id)
                    self.wfile.write(content.encode())
                print(f"Served: {path}")
            elif path == '/logout' and user:
                session_id = self.headers.get('Cookie', '').replace('session=', '')
                if session_id in SESSIONS:
                    del SESSIONS[session_id]
                self.send_response(302)
                self.send_header('Location', '/')
                self.send_header('Set-Cookie', 'session=; Max-Age=0')
                self.end_headers()
                print(f"Served: {path}")
            else:
                self.send_response(403)
                self.end_headers()
                self.wfile.write(b'Forbidden')
                print(f"Failed: {path} - Forbidden")
        except FileNotFoundError as e:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(f"File not found: {str(e)}".encode())
            print(f"Failed: {path} - FileNotFoundError: {e}")
        except Exception as e:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(f"Server error: {str(e)}".encode())
            print(f"Failed: {path} - Error: {e}")

    def do_POST(self):
        parsed_path = urllib.parse.urlparse(self.path)
        path = parsed_path.path
        try:
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length).decode()
            fields = urllib.parse.parse_qs(post_data)

            if path == '/signup':
                name = fields.get('name', [''])[0]
                email = fields.get('email', [''])[0]
                password = fields.get('password', [''])[0]
                role = fields.get('role', [''])[0]
                conn = sqlite3.connect(DB_FILE)
                c = conn.cursor()
                try:
                    c.execute("INSERT INTO users (name, email, password, role) VALUES (?, ?, ?, ?)",
                              (name, email, hash_password(password), role))
                    conn.commit()
                    self.send_response(302)
                    self.send_header('Location', '/login')
                    self.end_headers()
                except sqlite3.IntegrityError:
                    conn.close()
                    self.send_response(400)
                    self.end_headers()
                    self.wfile.write(b'Email already exists')
                conn.close()
                print(f"Processed: {path}")
            elif path == '/login':
                email = fields.get('email', [''])[0]
                password = fields.get('password', [''])[0]
                conn = sqlite3.connect(DB_FILE)
                c = conn.cursor()
                c.execute("SELECT id, name, email, password, role FROM users WHERE email = ?", (email,))
                user = c.fetchone()
                conn.close()
                if user and user[3] == hash_password(password):
                    session_id = str(uuid.uuid4())
                    SESSIONS[session_id] = {'id': user[0], 'name': user[1], 'email': user[2], 'role': user[4]}
                    self.send_response(302)
                    self.send_header('Location', '/dashboard')
                    self.send_header('Set-Cookie', f'session={session_id}')
                    self.end_headers()
                else:
                    self.send_response(400)
                    self.end_headers()
                    self.wfile.write(b'Invalid credentials')
                print(f"Processed: {path}")
            elif path == '/symptom_upload':
                user = get_user_from_session(self.headers.get('Cookie', '').replace('session=', ''))
                if user and user['role'] == 'patient':
                    symptoms = fields.get('symptoms', [''])[0]
                    conn = sqlite3.connect(DB_FILE)
                    c = conn.cursor()
                    c.execute("INSERT INTO symptoms (description, date, user_id) VALUES (?, ?, ?)",
                              (symptoms, datetime.datetime.now().isoformat(), user['id']))
                    conn.commit()
                    conn.close()
                    self.send_response(302)
                    self.send_header('Location', '/dashboard')
                    self.end_headers()
                else:
                    self.send_response(403)
                    self.end_headers()
                    self.wfile.write(b'Forbidden')
                print(f"Processed: {path}")
            elif path == '/book_appointment':
                user = get_user_from_session(self.headers.get('Cookie', '').replace('session=', ''))
                if user and user['role'] == 'patient':
                    doctor_id = fields.get('doctor_id', [''])[0]
                    date = fields.get('date', [''])[0]
                    conn = sqlite3.connect(DB_FILE)
                    c = conn.cursor()
                    c.execute("INSERT INTO appointments (date, patient_id, doctor_id) VALUES (?, ?, ?)",
                              (date, user['id'], doctor_id))
                    conn.commit()
                    conn.close()
                    self.send_response(302)
                    self.send_header('Location', '/dashboard')
                    self.end_headers()
                else:
                    self.send_response(403)
                    self.end_headers()
                    self.wfile.write(b'Forbidden')
                print(f"Processed: {path}")
            elif path == '/recommendation':
                user = get_user_from_session(self.headers.get('Cookie', '').replace('session=', ''))
                if user and user['role'] == 'doctor':
                    text = fields.get('text', [''])[0]
                    symptom_id = fields.get('symptom_id', [''])[0]
                    conn = sqlite3.connect(DB_FILE)
                    c = conn.cursor()
                    c.execute("SELECT user_id FROM symptoms WHERE id = ?", (symptom_id,))
                    patient_id = c.fetchone()
                    if patient_id:
                        patient_id = patient_id[0]
                        c.execute("INSERT INTO recommendations (text, date, user_id, symptom_id) VALUES (?, ?, ?, ?)",
                                  (text, datetime.datetime.now().isoformat(), patient_id, symptom_id))
                        conn.commit()
                        self.send_response(302)
                        self.send_header('Location', '/dashboard')
                        self.end_headers()
                    else:
                        self.send_response(400)
                        self.end_headers()
                        self.wfile.write(b'Invalid symptom ID')
                    conn.close()
                else:
                    self.send_response(403)
                    self.end_headers()
                    self.wfile.write(b'Forbidden')
                print(f"Processed: {path}")
            else:
                self.send_response(404)
                self.end_headers()
                self.wfile.write(b'Not Found')
                print(f"Failed: {path} - Not Found")
        except Exception as e:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(f"Server error: {str(e)}".encode())
            print(f"Failed: {path} - Error: {e}")

# Run server
if __name__ == '__main__':
    init_db()
    try:
        with socketserver.TCPServer(("", PORT), Handler) as httpd:
            print(f"Serving at port {PORT} - Open http://localhost:{PORT} in your browser")
            httpd.serve_forever()
    except Exception as e:
        print(f"Failed to start server: {e}")