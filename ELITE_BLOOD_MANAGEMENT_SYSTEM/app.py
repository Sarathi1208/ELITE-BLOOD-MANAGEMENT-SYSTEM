import os, re, sqlite3, secrets
from datetime import datetime
from functools import wraps
from pathlib import Path
from flask import Flask, render_template, request, redirect, url_for, flash, session, abort, send_from_directory
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

BASE_DIR = Path(__file__).resolve().parent
app = Flask(__name__)
app.config.update(SECRET_KEY=os.getenv('SECRET_KEY', 'CHANGE-THIS-DEVELOPMENT-SECRET'),
                  DATABASE=str(BASE_DIR/'database'/'elite_blood.db'),
                  UPLOAD_FOLDER=str(BASE_DIR/'uploads'/'certificates'), MAX_CONTENT_LENGTH=5*1024*1024)
ALLOWED_EXTENSIONS = {'pdf','png','jpg','jpeg'}
BLOOD_GROUPS = ['A+','A-','B+','B-','AB+','AB-','O+','O-']


def db():
    con = sqlite3.connect(app.config['DATABASE'])
    con.row_factory = sqlite3.Row
    con.execute('PRAGMA foreign_keys = ON')
    return con


def init_db():
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs(BASE_DIR/'database', exist_ok=True)
    with db() as con:
        con.executescript('''
        CREATE TABLE IF NOT EXISTS users (
          id INTEGER PRIMARY KEY AUTOINCREMENT, full_name TEXT NOT NULL,
          email TEXT NOT NULL UNIQUE COLLATE NOCASE, password_hash TEXT NOT NULL,
          role TEXT NOT NULL CHECK(role IN ('admin','donor')), created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS donors (
          id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
          age INTEGER NOT NULL CHECK(age BETWEEN 18 AND 65), gender TEXT NOT NULL,
          blood_group TEXT NOT NULL, phone TEXT NOT NULL, city TEXT NOT NULL, address TEXT NOT NULL,
          certificate TEXT, available INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS inventory (
          id INTEGER PRIMARY KEY AUTOINCREMENT, blood_group TEXT NOT NULL UNIQUE,
          units INTEGER NOT NULL DEFAULT 0 CHECK(units >= 0), updated_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS blood_requests (
          id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
          patient_name TEXT NOT NULL, blood_group TEXT NOT NULL, units INTEGER NOT NULL CHECK(units > 0),
          hospital TEXT NOT NULL, city TEXT NOT NULL, contact TEXT NOT NULL, notes TEXT DEFAULT '',
          status TEXT NOT NULL DEFAULT 'Pending' CHECK(status IN ('Pending','Approved','Rejected')),
          created_at TEXT NOT NULL);
        ''')
        for group in BLOOD_GROUPS:
            con.execute('INSERT OR IGNORE INTO inventory(blood_group, units, updated_at) VALUES(?,0,?)', (group, now()))
        admin_email = os.getenv('ADMIN_EMAIL', 'admin@eliteblood.com').lower()
        admin_password = os.getenv('ADMIN_PASSWORD', 'Admin@123')
        exists = con.execute('SELECT id FROM users WHERE email=?', (admin_email,)).fetchone()
        if not exists:
            con.execute('INSERT INTO users(full_name,email,password_hash,role,created_at) VALUES(?,?,?,?,?)',
                        ('System Administrator', admin_email, generate_password_hash(admin_password), 'admin', now()))


def now(): return datetime.now().strftime('%Y-%m-%d %H:%M:%S')
def current_user():
    if 'user_id' not in session: return None
    with db() as con: return con.execute('SELECT id,full_name,email,role FROM users WHERE id=?',(session['user_id'],)).fetchone()
def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not current_user(): flash('Please log in to continue.', 'warning'); return redirect(url_for('login'))
        return fn(*args, **kwargs)
    return wrapper
def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        user=current_user()
        if not user: flash('Please log in first.','warning'); return redirect(url_for('login'))
        if user['role']!='admin': abort(403)
        return fn(*args, **kwargs)
    return wrapper
def valid_email(value): return bool(re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', value or ''))
def valid_phone(value): return bool(re.fullmatch(r'[0-9+() -]{7,20}', value or ''))
def allowed_file(filename): return '.' in filename and filename.rsplit('.',1)[1].lower() in ALLOWED_EXTENSIONS

@app.context_processor
def inject_globals(): return {'current_user': current_user(), 'blood_groups': BLOOD_GROUPS}

@app.route('/')
def index():
    with db() as con:
        donors=con.execute('SELECT COUNT(*) n FROM donors WHERE available=1').fetchone()['n']
        units=con.execute('SELECT COALESCE(SUM(units),0) n FROM inventory').fetchone()['n']
    return render_template('index.html', available_donors=donors, total_units=units)

@app.route('/register', methods=['GET','POST'])
def register():
    if request.method=='POST':
        name=request.form.get('full_name','').strip(); email=request.form.get('email','').strip().lower(); password=request.form.get('password',''); confirm=request.form.get('confirm_password','')
        if len(name)<2 or not valid_email(email) or len(password)<8 or password!=confirm:
            flash('Check your name, email and password. Password must be at least 8 characters and both passwords must match.','danger')
        else:
            try:
                with db() as con:
                    cur=con.execute('INSERT INTO users(full_name,email,password_hash,role,created_at) VALUES(?,?,?,?,?)',(name,email,generate_password_hash(password),'donor',now()))
                    uid=cur.lastrowid
                session.clear(); session['user_id']=uid
                flash('Account created successfully. Complete your donor profile to appear in donor search.','success')
                return redirect(url_for('donor_form'))
            except sqlite3.IntegrityError: flash('An account with this email already exists.','danger')
    return render_template('register.html')

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method=='POST':
        email=request.form.get('email','').strip().lower(); password=request.form.get('password','')
        with db() as con: user=con.execute('SELECT * FROM users WHERE email=?',(email,)).fetchone()
        if user and check_password_hash(user['password_hash'],password):
            session.clear(); session['user_id']=user['id']; flash('Welcome back!','success')
            return redirect(url_for('admin_dashboard' if user['role']=='admin' else 'dashboard'))
        flash('Invalid email or password.','danger')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout(): session.clear(); flash('You have been logged out.','success'); return redirect(url_for('index'))

@app.route('/dashboard')
@login_required
def dashboard():
    user=current_user()
    with db() as con:
        donor=con.execute('SELECT * FROM donors WHERE user_id=?',(user['id'],)).fetchone()
        requests=con.execute('SELECT * FROM blood_requests WHERE user_id=? ORDER BY id DESC LIMIT 5',(user['id'],)).fetchall()
        stock=con.execute('SELECT * FROM inventory ORDER BY blood_group').fetchall()
    return render_template('dashboard.html', donor=donor, requests=requests, stock=stock)

@app.route('/donor/profile', methods=['GET','POST'])
@login_required
def donor_form():
    user=current_user()
    if user['role']!='donor': abort(403)
    with db() as con: existing=con.execute('SELECT * FROM donors WHERE user_id=?',(user['id'],)).fetchone()
    if request.method=='POST':
        try:
            age=int(request.form.get('age','0'))
        except ValueError: age=0
        gender=request.form.get('gender',''); group=request.form.get('blood_group',''); phone=request.form.get('phone','').strip(); city=request.form.get('city','').strip(); address=request.form.get('address','').strip()
        available=1 if request.form.get('available')=='on' else 0
        file=request.files.get('certificate'); certificate=existing['certificate'] if existing else None
        errors=[]
        if not 18<=age<=65: errors.append('Donor age must be between 18 and 65.')
        if gender not in ['Male','Female','Other']: errors.append('Select a valid gender.')
        if group not in BLOOD_GROUPS: errors.append('Select a valid blood group.')
        if not valid_phone(phone): errors.append('Enter a valid contact number.')
        if not city or not address: errors.append('City and address are required.')
        if file and file.filename:
            if not allowed_file(file.filename): errors.append('Certificate must be PDF, PNG, JPG or JPEG.')
            else:
                filename=secure_filename(file.filename)
                unique=f"{user['id']}_{secrets.token_hex(8)}_{filename}"
                file.save(os.path.join(app.config['UPLOAD_FOLDER'],unique)); certificate=unique
        if errors:
            for e in errors: flash(e,'danger')
        else:
            with db() as con:
                values=(age,gender,group,phone,city,address,certificate,available)
                if existing:
                    con.execute('UPDATE donors SET age=?,gender=?,blood_group=?,phone=?,city=?,address=?,certificate=?,available=?,created_at=? WHERE user_id=?',(*values,now(),user['id']))
                else:
                    con.execute('INSERT INTO donors(user_id,age,gender,blood_group,phone,city,address,certificate,available,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)',(user['id'],*values,now()))
            flash('Donor profile saved successfully.','success'); return redirect(url_for('dashboard'))
    return render_template('donor_form.html', donor=existing)

@app.route('/donors')
def donors():
    group=request.args.get('blood_group',''); city=request.args.get('city','').strip()
    query='SELECT d.*,u.full_name FROM donors d JOIN users u ON u.id=d.user_id WHERE d.available=1'; params=[]
    if group in BLOOD_GROUPS: query+=' AND d.blood_group=?'; params.append(group)
    if city: query+=' AND d.city LIKE ?'; params.append('%'+city+'%')
    query+=' ORDER BY d.created_at DESC'
    with db() as con:
        rows=con.execute(query,params).fetchall(); count=len(rows)
    return render_template('donors.html', donors=rows, count=count, selected_group=group, selected_city=city)

@app.route('/inventory')
def inventory():
    with db() as con: rows=con.execute('SELECT * FROM inventory ORDER BY blood_group').fetchall()
    return render_template('inventory.html', inventory=rows)

@app.route('/request/new', methods=['GET','POST'])
@login_required
def request_form():
    if request.method=='POST':
        patient=request.form.get('patient_name','').strip(); group=request.form.get('blood_group',''); hospital=request.form.get('hospital','').strip(); city=request.form.get('city','').strip(); contact=request.form.get('contact','').strip(); notes=request.form.get('notes','').strip()
        try: units=int(request.form.get('units','0'))
        except ValueError: units=0
        if not patient or group not in BLOOD_GROUPS or not 1<=units<=100 or not hospital or not city or not valid_phone(contact):
            flash('Please complete all required fields with valid values. Units must be between 1 and 100.','danger')
        else:
            with db() as con:
                con.execute('INSERT INTO blood_requests(user_id,patient_name,blood_group,units,hospital,city,contact,notes,status,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)',(current_user()['id'],patient,group,units,hospital,city,contact,notes,'Pending',now()))
            flash('Blood request submitted. The administrator will review it.','success'); return redirect(url_for('dashboard'))
    return render_template('request_form.html')

@app.route('/requests')
@login_required
def my_requests():
    with db() as con: rows=con.execute('SELECT * FROM blood_requests WHERE user_id=? ORDER BY id DESC',(current_user()['id'],)).fetchall()
    return render_template('requests.html', requests=rows)

@app.route('/admin')
@admin_required
def admin_dashboard():
    with db() as con:
        stats={'donors':con.execute('SELECT COUNT(*) n FROM donors').fetchone()['n'], 'available':con.execute('SELECT COUNT(*) n FROM donors WHERE available=1').fetchone()['n'], 'requests':con.execute('SELECT COUNT(*) n FROM blood_requests').fetchone()['n'], 'units':con.execute('SELECT COALESCE(SUM(units),0) n FROM inventory').fetchone()['n']}
        stock=con.execute('SELECT * FROM inventory ORDER BY blood_group').fetchall()
        recent_donors=con.execute('SELECT d.*,u.full_name FROM donors d JOIN users u ON u.id=d.user_id ORDER BY d.id DESC LIMIT 5').fetchall()
        recent_requests=con.execute('SELECT * FROM blood_requests ORDER BY id DESC LIMIT 5').fetchall()
    return render_template('admin_dashboard.html', stats=stats, inventory=stock, recent_donors=recent_donors, recent_requests=recent_requests)

@app.route('/admin/donors')
@admin_required
def manage_donors():
    search=request.args.get('q','').strip()
    sql='SELECT d.*,u.full_name,u.email FROM donors d JOIN users u ON u.id=d.user_id'; params=[]
    if search: sql+=' WHERE u.full_name LIKE ? OR d.city LIKE ? OR d.blood_group LIKE ?'; params=[f'%{search}%']*3
    sql+=' ORDER BY d.id DESC'
    with db() as con: rows=con.execute(sql,params).fetchall()
    return render_template('manage_donors.html', donors=rows, q=search)

@app.route('/admin/donors/<int:donor_id>/availability', methods=['POST'])
@admin_required
def toggle_donor(donor_id):
    with db() as con:
        row=con.execute('SELECT available FROM donors WHERE id=?',(donor_id,)).fetchone()
        if not row: abort(404)
        con.execute('UPDATE donors SET available=? WHERE id=?',(0 if row['available'] else 1,donor_id))
    flash('Donor availability updated.','success'); return redirect(url_for('manage_donors'))

@app.route('/admin/requests')
@admin_required
def manage_requests():
    with db() as con: rows=con.execute('SELECT * FROM blood_requests ORDER BY id DESC').fetchall()
    return render_template('manage_requests.html', requests=rows)

@app.route('/admin/requests/<int:request_id>/status', methods=['POST'])
@admin_required
def update_request(request_id):
    status=request.form.get('status')
    if status not in ['Approved','Rejected','Pending']: abort(400)
    with db() as con:
        row=con.execute('SELECT * FROM blood_requests WHERE id=?',(request_id,)).fetchone()
        if not row: abort(404)
        if status=='Approved' and row['status']!='Approved':
            stock=con.execute('SELECT units FROM inventory WHERE blood_group=?',(row['blood_group'],)).fetchone()
            if stock['units']<row['units']:
                flash('Cannot approve: insufficient inventory for this blood group.','danger'); return redirect(url_for('manage_requests'))
            con.execute('UPDATE inventory SET units=units-?,updated_at=? WHERE blood_group=?',(row['units'],now(),row['blood_group']))
        elif row['status']=='Approved' and status!='Approved':
            con.execute('UPDATE inventory SET units=units+?,updated_at=? WHERE blood_group=?',(row['units'],now(),row['blood_group']))
        con.execute('UPDATE blood_requests SET status=? WHERE id=?',(status,request_id))
    flash(f'Request #{request_id} marked {status.lower()}.','success'); return redirect(url_for('manage_requests'))

@app.route('/admin/inventory', methods=['GET','POST'])
@admin_required
def manage_inventory():
    if request.method=='POST':
        group=request.form.get('blood_group','')
        try: units=int(request.form.get('units','-1'))
        except ValueError: units=-1
        if group not in BLOOD_GROUPS or not 0<=units<=100000: flash('Enter a valid blood group and non-negative unit count.','danger')
        else:
            with db() as con: con.execute('UPDATE inventory SET units=?,updated_at=? WHERE blood_group=?',(units,now(),group))
            flash('Blood stock updated.','success')
        return redirect(url_for('manage_inventory'))
    with db() as con: rows=con.execute('SELECT * FROM inventory ORDER BY blood_group').fetchall()
    return render_template('inventory.html', inventory=rows, admin_mode=True)

@app.route('/certificate/<path:filename>')
@admin_required
def certificate(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename, as_attachment=True)

@app.errorhandler(403)
def forbidden(e): return render_template('error.html', code=403, message='You do not have permission to view this page.'),403
@app.errorhandler(404)
def not_found(e): return render_template('error.html', code=404, message='The page you requested could not be found.'),404
@app.errorhandler(413)
def too_large(e): flash('File too large. Maximum upload size is 5 MB.','danger'); return redirect(request.referrer or url_for('donor_form'))

with app.app_context(): init_db()

if __name__=='__main__': app.run(debug=os.getenv('FLASK_DEBUG','false').lower()=='true')
