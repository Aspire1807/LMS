from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, date

app = Flask(__name__)
app.secret_key = "lms-secret-key"
DB_PATH = "library.db"

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL,
        email TEXT NOT NULL UNIQUE,
        password TEXT NOT NULL
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS issues(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        book_name TEXT NOT NULL,
        student_name TEXT NOT NULL,
        student_id TEXT NOT NULL,
        branch TEXT NOT NULL,
        year_semester TEXT NOT NULL,
        issue_date TEXT NOT NULL,
        return_date TEXT,
        fine INTEGER DEFAULT 0,
        status TEXT NOT NULL DEFAULT 'Issued'
    )""")
    conn.commit(); conn.close()

init_db()

@app.route('/register', methods=['GET','POST'])
def register():
    if request.method == 'POST':
        username = request.form['username'].strip()
        email = request.form['email'].strip().lower()
        password = generate_password_hash(request.form['password'])
        if not username or not email:
            flash('All fields are required.', 'danger'); return redirect(url_for('register'))
        conn = get_db(); c = conn.cursor()
        try:
            c.execute('INSERT INTO users(username,email,password) VALUES(?,?,?)',(username,email,password))
            conn.commit(); flash('Registration successful. Login now.', 'success')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('Email already exists.', 'danger')
        finally:
            conn.close()
    return render_template('register.html')

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        email = request.form['email'].strip().lower()
        password = request.form['password']
        conn = get_db(); c = conn.cursor()
        c.execute('SELECT * FROM users WHERE email=?',(email,))
        u = c.fetchone(); conn.close()
        if u and check_password_hash(u['password'], password):
            session['user_id'] = u['id']; session['username'] = u['username']
            return redirect(url_for('dashboard'))
        flash('Invalid email or password.', 'danger')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear(); flash('Logged out.', 'info')
    return redirect(url_for('login'))

def login_required(fn):
    from functools import wraps
    @wraps(fn)
    def wrapper(*a, **kw):
        if 'user_id' not in session: return redirect(url_for('login'))
        return fn(*a, **kw)
    return wrapper

@app.route('/')
def home():
    return redirect(url_for('dashboard') if 'user_id' in session else url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    conn = get_db(); c = conn.cursor()
    c.execute('SELECT * FROM issues ORDER BY id DESC')
    rows = c.fetchall(); conn.close()
    return render_template('dashboard.html', rows=rows)

@app.route('/issue', methods=['POST'])
@login_required
def create_issue():
    f = request.form
    conn = get_db(); c = conn.cursor()
    c.execute("""INSERT INTO issues(book_name,student_name,student_id,branch,year_semester,issue_date,status)
                 VALUES(?,?,?,?,?,?, 'Issued')""", 
              (f['book_name'].strip(), f['student_name'].strip(), f['student_id'].strip(),
               f['branch'].strip(), f['year_semester'].strip(), f['issue_date']))
    conn.commit(); conn.close()
    flash('Book issued.', 'success')
    return redirect(url_for('dashboard'))

@app.route('/return/<int:issue_id>', methods=['POST'])
@login_required
def mark_return(issue_id):
    return_date = request.form.get('return_date') or date.today().strftime('%Y-%m-%d')
    DUE_DAYS = 14
    conn = get_db(); c = conn.cursor()
    c.execute('SELECT issue_date FROM issues WHERE id=?', (issue_id,))
    r = c.fetchone()
    fine = 0
    if r:
        try:
            issue_dt = datetime.strptime(r['issue_date'], '%Y-%m-%d').date()
            due_dt = issue_dt.fromordinal(issue_dt.toordinal() + DUE_DAYS)
            ret_dt = datetime.strptime(return_date, '%Y-%m-%d').date()
            late_days = (ret_dt - due_dt).days
            fine = max(0, late_days * 2)
        except Exception:
            fine = 0
    c.execute("""UPDATE issues SET status='Returned', return_date=?, fine=? WHERE id=?""",
              (return_date, fine, issue_id))
    conn.commit(); conn.close()
    flash(f'Returned. Fine ₹{fine}.', 'info')
    return redirect(url_for('dashboard'))

@app.route('/delete/<int:issue_id>')
@login_required
def delete_issue(issue_id):
    conn = get_db(); c = conn.cursor()
    c.execute('DELETE FROM issues WHERE id=?', (issue_id,))
    conn.commit(); conn.close()
    flash('Record deleted.', 'warning')
    return redirect(url_for('dashboard'))

@app.route('/delete_all')
@login_required
def delete_all():
    conn = get_db(); c = conn.cursor()
    c.execute('DELETE FROM issues')
    conn.commit(); conn.close()
    flash('All records deleted.', 'danger')
    return redirect(url_for('dashboard'))

if __name__ == '__main__':
    app.run(debug=True)
