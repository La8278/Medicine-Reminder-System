from twilio.rest import Client
import logging
from flask_mail import Mail, Message
from flask_sqlalchemy import SQLAlchemy
from flask import Flask, render_template, request, redirect, url_for, session, flash
# --- Navigation Pages ---
# (Moved to after app and db initialization)
# -----------------------------
# Delete Medicine Route
# -----------------------------
# -----------------------------
# Delete Medicine Route
# -----------------------------
import calendar


# --- Flask App Initialization ---
app = Flask(__name__)
app.secret_key = "supersecretkey"
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///project.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# --- Flask-Mail Config ---
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'aminanazeer044@gmail.com'      # <-- your Gmail address
app.config['MAIL_PASSWORD'] = 'eqpx umvm ltcz fodx'           # <-- your new app password from Google
mail = Mail(app)

# --- Twilio Config ---
TWILIO_ACCOUNT_SID = 'ACf2d46974434d991ce223acdf73a11317'
TWILIO_AUTH_TOKEN = 'c4aadaa592de42ae81b809730e35057c'
TWILIO_PHONE_NUMBER = '+13254406112'
twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
# --- Logging for notifications ---
logger = logging.getLogger('medtrack.notifications')
logger.setLevel(logging.INFO)
handler = logging.FileHandler('notification_errors.log')
formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

def safe_send_email(subject, recipients, body, attempts=2, delay=2):
    """Send email with simple retry and logging. Returns True if sent."""
    for i in range(attempts):
        try:
            msg = Message(subject=subject, sender=app.config['MAIL_USERNAME'], recipients=recipients, body=body)
            mail.send(msg)
            logger.info(f"Email sent to {recipients}: {subject}")
            return True
        except Exception as e:
            logger.error(f"Email send failed (attempt {i+1}): {e}")
            time.sleep(delay * (i+1))
    return False

def safe_send_sms(to, body, attempts=2, delay=2):
    """Send SMS with retry and logging. Expects full phone string like '+91xxxxxxxxxx'. Returns True if sent."""
    for i in range(attempts):
        try:
            twilio_client.messages.create(body=body, from_=TWILIO_PHONE_NUMBER, to=to)
            logger.info(f"SMS sent to {to}: {body}")
            return True
        except Exception as e:
            logger.error(f"SMS send failed (attempt {i+1}) to {to}: {e}")
            time.sleep(delay * (i+1))
    return False
from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import func, inspect, text
from datetime import datetime, timedelta
import re, json
import threading
import time
from flask_mail import Mail, Message
from twilio.rest import Client


# --- Flask-Mail Config ---
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'aminanazeer044@gmail.com'      # <-- your Gmail address
app.config['MAIL_PASSWORD'] = 'eqpx umvm ltcz fodx'           # <-- your new app password from Google
mail = Mail(app)

# --- Twilio Config ---
TWILIO_ACCOUNT_SID = 'ACf2d46974434d991ce223acdf73a11317'
TWILIO_AUTH_TOKEN = 'c4aadaa592de42ae81b809730e35057c'
TWILIO_PHONE_NUMBER = '+13254406112'
twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

# -----------------------------
# Database Models
# -----------------------------
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    phone = db.Column(db.String(10), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)

class Medicine(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    name = db.Column(db.String(100), nullable=False)
    med_type = db.Column(db.String(50), nullable=False)
    drops_type = db.Column(db.String(20))
    dosage = db.Column(db.String(50), nullable=False)
    unit = db.Column(db.String(10), nullable=False)
    count = db.Column(db.Integer, nullable=False)
    timing = db.Column(db.String(50), nullable=False)  # "HH:MM,HH:MM"
    before_after = db.Column(db.String(20), nullable=False)
    start_date = db.Column(db.String(20), nullable=False)
    end_date = db.Column(db.String(20), nullable=False)
    expiries = db.relationship("MedicineExpiry", backref="medicine")
    reminders = db.relationship("Reminder", backref="medicine")

class Reminder(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    medicine_id = db.Column(db.Integer, db.ForeignKey('medicine.id'))
    reminder_time = db.Column(db.String(50), nullable=False)
    frequency = db.Column(db.String(50), nullable=False)
    statuses = db.Column(db.Text, nullable=False, default='{}')  # JSON: {"HH:MM|YYYY-MM-DD":"Pending"}
    weekdays = db.Column(db.String(50))    # comma separated weekday ints (0=Mon .. 6=Sun)
    month_day = db.Column(db.Integer)      # day of month (1..31)
    created_weekday = db.Column(db.Integer) # weekday when created (0=Mon..6=Sun)

    @property
    def status_dict(self):
        try:
            return json.loads(self.statuses)
        except:
            return {}

class MedicineExpiry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    medicine_id = db.Column(db.Integer, db.ForeignKey('medicine.id'))
    batch_number = db.Column(db.String(50))
    mfg_date = db.Column(db.String(20))
    expiry_date = db.Column(db.String(20))  # YYYY-MM-DD
    expiring_alert_sent = db.Column(db.Boolean, default=False)  # <-- add this
    expired_alert_sent = db.Column(db.Boolean, default=False)   # <-- add this

class AlternativeMedicine(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    condition = db.Column(db.String(100), nullable=False)
    original_name = db.Column(db.String(100), nullable=False)
    alternative_name = db.Column(db.String(100), nullable=False)

# -----------------------------
# Validators
# -----------------------------
def valid_email(email):
    return re.match(r'^[\w\.-]+@gmail\.com$', email)

def valid_phone(phone):
    return re.match(r'^\d{10}$', phone)

def valid_password(password):
    return re.match(r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[\W_]).+$', password)

# -----------------------------
# Template Helpers
# -----------------------------
@app.context_processor
def inject_helpers():
    def get_medicine_status(medicine):
        now = datetime.now()
        if not medicine.expiries:
            return "Safe"
        earliest_expiry = min([datetime.strptime(e.expiry_date, "%Y-%m-%d") for e in medicine.expiries])
        days_left = (earliest_expiry - now).days
        if days_left < 0:
            return "Expired"
        elif days_left <= 7:
            return "Expiring Soon"
        else:
            return "Safe"
    return dict(datetime=datetime, timedelta=timedelta, get_medicine_status=get_medicine_status)

# -----------------------------
# Seed Alternative Medicines
# -----------------------------
def seed_alternatives():
    if AlternativeMedicine.query.count() == 0:
        data = [
            {"condition":"Fever","original_name":"Paracetamol","alternative_name":"Dolo-650"},
            {"condition":"Fever","original_name":"Paracetamol","alternative_name":"Crocin"},
            {"condition":"Cold","original_name":"Cetirizine","alternative_name":"Levocetirizine"},
            {"condition":"Headache","original_name":"Paracetamol","alternative_name":"Ibuprofen"},
            {"condition":"Diabetes","original_name":"Metformin","alternative_name":"Glimepiride"},
            {"condition":"Hypertension","original_name":"Amlodipine","alternative_name":"Losartan"},
            {"condition":"Heart Disease","original_name":"Aspirin","alternative_name":"Clopidogrel"},
            {"condition":"Heart Disease","original_name":"Atorvastatin","alternative_name":"Rosuvastatin"},
            {"condition":"Asthma","original_name":"Salbutamol","alternative_name":"Levosalbutamol"},
            {"condition":"Pain","original_name":"Diclofenac","alternative_name":"Naproxen"},
            {"condition":"Infection","original_name":"Amoxicillin","alternative_name":"Amoxicillin-Clavulanate"},
            {"condition":"Infection","original_name":"Azithromycin","alternative_name":"Clarithromycin"},
            {"condition":"Pain","original_name":"Ibuprofen","alternative_name":"Naproxen"},
            {"condition":"Allergy","original_name":"Loratadine","alternative_name":"Fexofenadine"},
            {"condition":"Allergy","original_name":"Cetirizine","alternative_name":"Loratadine"},
            {"condition":"Stomach Acid","original_name":"Omeprazole","alternative_name":"Pantoprazole"},
            {"condition":"Stomach Acid","original_name":"Ranitidine","alternative_name":"Famotidine"},
            {"condition":"Diabetes","original_name":"Glimepiride","alternative_name":"Gliclazide"},
            {"condition":"Cholesterol","original_name":"Atorvastatin","alternative_name":"Simvastatin"},
            {"condition":"Cough","original_name":"Dextromethorphan","alternative_name":"Benzonatate"},
            {"condition":"Cold","original_name":"Pseudoephedrine","alternative_name":"Phenylephrine"},
            {"condition":"Pain","original_name":"Tramadol","alternative_name":"Tapentadol"},
            {"condition":"Fever","original_name":"Paracetamol","alternative_name":"Calpol"},
            {"condition":"Vitamin","original_name":"Vitamin D","alternative_name":"Cholecalciferol"},
            {"condition":"Vitamin","original_name":"Vitamin B12","alternative_name":"Methylcobalamin"},
            {"condition":"Gout","original_name":"Allopurinol","alternative_name":"Febuxostat"},
            {"condition":"Urinary","original_name":"Nitrofurantoin","alternative_name":"Fosfomycin"},
            {"condition":"Antifungal","original_name":"Fluconazole","alternative_name":"Itraconazole"},
            {"condition":"Hypertension","original_name":"Losartan","alternative_name":"Valsartan"},
            {"condition":"Hypertension","original_name":"Amlodipine","alternative_name":"Felodipine"},
            {"condition":"Pain","original_name":"Diclofenac","alternative_name":"Meloxicam"},
            {"condition":"Infection","original_name":"Ciprofloxacin","alternative_name":"Levofloxacin"},
            {"condition":"Constipation","original_name":"Lactulose","alternative_name":"Polyethylene Glycol"},
            {"condition":"Cold","original_name":"Saline Nasal","alternative_name":"Phenylephrine Nasal"},
            {"condition":"Nausea","original_name":"Ondansetron","alternative_name":"Domperidone"},
            {"condition":"Pain","original_name":"Aspirin","alternative_name":"Acetaminophen"},
        ]
        for item in data:
            db.session.add(AlternativeMedicine(**item))
        db.session.commit()

@app.route('/delete_reminder/<int:reminder_id>', methods=['POST'])
def delete_reminder(reminder_id):
    if "user_id" not in session:
        return redirect(url_for('login'))
    reminder = Reminder.query.get(reminder_id)
    if reminder and reminder.user_id == session['user_id']:
        db.session.delete(reminder)
        db.session.commit()
        flash("Reminder deleted!", "success")
    else:
        flash("Reminder not found or permission denied.", "danger")
    return redirect(url_for('dashboard'))
@app.route('/delete_medicine/<int:medicine_id>', methods=['POST'])
def delete_medicine(medicine_id):
    if "user_id" not in session:
        return redirect(url_for('login'))
    medicine = Medicine.query.get(medicine_id)
    if medicine and medicine.user_id == session['user_id']:
        # Delete related reminders and expiries first
        Reminder.query.filter_by(medicine_id=medicine.id).delete()
        MedicineExpiry.query.filter_by(medicine_id=medicine.id).delete()
        db.session.delete(medicine)
        db.session.commit()
        flash("Medicine deleted!", "success")
    else:
        flash("Medicine not found or permission denied.", "danger")
    return redirect(url_for('dashboard'))
# -----------------------------
# Routes
# -----------------------------
@app.route('/')
def home():
    return render_template('index.html')

@app.route('/register', methods=['GET','POST'])
def register():
    if request.method=='POST':
        username = request.form['username']
        email = request.form['email']
        phone = request.form['phone']
        password = request.form['password']
        if not valid_email(email) or not valid_phone(phone) or not valid_password(password):
            flash("Invalid input", "danger")
            return redirect(url_for('register'))
        if User.query.filter_by(email=email).first() or User.query.filter_by(username=username).first() or User.query.filter_by(phone=phone).first():
            flash("User exists", "danger")
            return redirect(url_for('register'))
        hashed = generate_password_hash(password)
        db.session.add(User(username=username,email=email,phone=phone,password=hashed))
        db.session.commit()
        # --- Send Email ---
        try:
            safe_send_email(subject="Welcome to MedTrack!", recipients=[email], body=f"Hello {username}, thank you for registering with MedTrack!")
        except Exception as e:
            logger.error(f"Unexpected error in safe_send_email: {e}")
        # --- Send SMS ---
        try:
            safe_send_sms(to=f"+91{phone}", body=f"Hello {username}, thank you for registering with MedTrack!")
        except Exception as e:
            logger.error(f"Unexpected error in safe_send_sms: {e}")
        flash("Registered!", "success")
        return redirect(url_for('login'))
    return render_template("register.html")

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method=='POST':
        email = request.form['email']
        password = request.form['password']
        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password,password):
            session['user_id'] = user.id
            session['username'] = user.username
            flash("Login successful!", "success")
            return redirect(url_for('dashboard'))
        flash("Invalid credentials", "danger")
    return render_template("login.html")

@app.route('/logout')
def logout():
    session.clear()
    flash("Logged out", "info")
    return redirect(url_for('home'))

@app.route('/dashboard')
def dashboard():
    if "user_id" not in session:
        return redirect(url_for('login'))
    user = db.session.get(User, session['user_id'])  # updated for SQLAlchemy 2.x
    medicines = Medicine.query.filter_by(user_id=user.id).all()
    reminders = Reminder.query.filter_by(user_id=user.id).all()
    expired_meds = MedicineExpiry.query.join(Medicine).filter(Medicine.user_id==user.id).all()
    # --- compute today's schedule ---
    now = datetime.now()
    today_str = now.strftime("%Y-%m-%d")
    weekday = now.weekday()  # 0=Mon .. 6=Sun

    # 1) Today's reminders first (so we can detect 'Taken' statuses)
    todays_reminders = []
    taken_pairs = set()  # (medicine_id, time) pairs that are marked Taken for today
    for rem in reminders:
        applies = False
        freq = (rem.frequency or '').lower()
        if 'daily' in freq or 'once' in freq:
            applies = True
        elif 'weekly' in freq:
            if rem.weekdays:
                try:
                    wd_list = [int(x) for x in rem.weekdays.split(',') if x!='']
                    if weekday in wd_list:
                        applies = True
                except:
                    applies = False
        elif 'monthly' in freq:
            if rem.month_day and int(rem.month_day) == now.day:
                applies = True

        if applies:
            status_dict = rem.status_dict
            todays_statuses = {}
            for k, v in status_dict.items():
                if '|' in k:
                    time_part, date_part = k.split('|', 1)
                    if date_part == today_str:
                        todays_statuses[time_part] = v
                else:
                    todays_statuses[k] = v

            # record taken pairs
            for time_k, stat in todays_statuses.items():
                try:
                    if str(stat).lower() == 'taken':
                        taken_pairs.add((rem.medicine_id, time_k))
                except:
                    pass

            todays_reminders.append({
                'reminder': rem,
                'time': rem.reminder_time,
                'statuses': todays_statuses
            })

    # 2) Today's medicine events (based on medicines' timing and active date range)
    todays_medicines = []
    for med in medicines:
        try:
            start = datetime.strptime(med.start_date, "%Y-%m-%d").date()
            end = datetime.strptime(med.end_date, "%Y-%m-%d").date()
        except Exception:
            start = None
            end = None

        if (start and now.date() < start) or (end and now.date() > end):
            continue

        times = [t.strip() for t in med.timing.split(',') if t.strip()]
        for t in times:
            taken = (med.id, t) in taken_pairs
            todays_medicines.append({
                'medicine': med,
                'time': t,
                'before_after': med.before_after,
                'dosage': med.dosage,
                'taken': taken
            })

    # 3) Enrich expiry entries with days left and human status
    expired_meds_info = []
    for exp in expired_meds:
        try:
            expiry_dt = datetime.strptime(exp.expiry_date, "%Y-%m-%d")
            days_left = (expiry_dt - now).days
        except Exception:
            days_left = None
        if days_left is None:
            status = 'Unknown'
        elif days_left < 0:
            status = 'Expired'
        elif days_left <= 7:
            status = 'Expiring Soon'
        else:
            status = 'Safe'
        expired_meds_info.append({'expiry': exp, 'days_left': days_left, 'status': status})

    # ---- Compute today's reminder stats (taken / not_taken / pending / missed)
    stats = {'taken': 0, 'not_taken': 0, 'pending': 0, 'missed': 0, 'total': 0}
    processed_pairs = set()  # avoid double counting (medicine_id, time)
    now_time = datetime.now().time()

    # Helper to parse time strings 'HH:MM'
    def _parse_time(tstr):
        try:
            return datetime.strptime(tstr.strip(), "%H:%M").time()
        except Exception:
            return None

    # Process todays_reminders first
    for r in todays_reminders:
        rem = r.get('reminder')
        time_raw = r.get('time') or ''
        time_key = time_raw.split('|')[0] if '|' in time_raw else time_raw
        pair = (getattr(rem, 'medicine_id', None), time_key)
        if pair in processed_pairs:
            continue
        processed_pairs.add(pair)
        stats['total'] += 1
        status = None
        try:
            statuses = r.get('statuses') or {}
            status = statuses.get(time_key)
        except Exception:
            status = None

        if status:
            s = str(status).strip().lower()
            if s == 'taken':
                stats['taken'] += 1
                continue
            if s in ('not taken', 'not-taken', 'not'):
                stats['not_taken'] += 1
                continue

        # no explicit status -> missed or pending by comparing time
        sched = _parse_time(time_key)
        if sched and sched <= now_time:
            stats['missed'] += 1
        else:
            stats['pending'] += 1

    # Process todays_medicines (add any that weren't present in reminders)
    for item in todays_medicines:
        med = item.get('medicine')
        time_key = item.get('time')
        pair = (getattr(med, 'id', None), time_key)
        if pair in processed_pairs:
            continue
        processed_pairs.add(pair)
        stats['total'] += 1
        if item.get('taken'):
            stats['taken'] += 1
            continue
        sched = _parse_time(time_key)
        if sched and sched <= now_time:
            stats['missed'] += 1
        else:
            stats['pending'] += 1

    return render_template("dashboard.html", user=user, medicines=medicines, reminders=reminders, expired_meds=expired_meds, todays_medicines=todays_medicines, todays_reminders=todays_reminders, expired_meds_info=expired_meds_info, today_stats=stats)

@app.route('/add_medicine', methods=['GET','POST'])
def add_medicine():
    if "user_id" not in session:
        return redirect(url_for('login'))
    if request.method=='POST':
        # Check for potential duplicate/similar medicine entries
        name = request.form['name'].strip()
        start_date = request.form['start_date']
        end_date = request.form['end_date']
        duplicate_found = False
        existing = Medicine.query.filter_by(user_id=session['user_id'], name=name).all()
        for ex in existing:
            try:
                ex_s = datetime.strptime(ex.start_date, "%Y-%m-%d").date()
                ex_e = datetime.strptime(ex.end_date, "%Y-%m-%d").date()
                ns = datetime.strptime(start_date, "%Y-%m-%d").date()
                ne = datetime.strptime(end_date, "%Y-%m-%d").date()
                # overlapping ranges -> duplicate
                if not (ne < ex_s or ns > ex_e):
                    duplicate_found = True
                    break
            except Exception:
                # if parsing fails, but name matches, consider duplicate
                duplicate_found = True
                break

        if duplicate_found:
            flash("Warning: a similar medicine entry already exists for these dates.", "warning")

        med = Medicine(
            user_id=session['user_id'],
            name=name,
            med_type=request.form['med_type'],
            drops_type=request.form.get('drops_type'),
            dosage=request.form['dosage'],
            unit=request.form['unit'],
            count=int(request.form['count']),
            timing=",".join(request.form.getlist('timing')),
            before_after=request.form['before_after'],
            start_date=start_date,
            end_date=end_date
        )
        db.session.add(med)
        db.session.commit()
        flash("Medicine added!", "success")
        return redirect(url_for('dashboard'))
    return render_template("add_medicine.html")

@app.route('/reminder', methods=['GET','POST'])
def reminder_route():
    if "user_id" not in session:
        return redirect(url_for('login'))
    medicines = Medicine.query.filter_by(user_id=session['user_id']).all()
    if request.method=='POST':
        medicine_id = int(request.form['medicine_id'])
        reminder_time = request.form['reminder_time']  # expected "HH:MM"
        frequency = request.form['frequency']
        # optional fields from UI (may be empty)
        weekdays = request.form.get('weekdays')  # e.g. "0,2,4"
        month_day = request.form.get('month_day')
        try:
            month_day_val = int(month_day) if month_day else None
        except:
            month_day_val = None
        created_wd = datetime.now().weekday()  # 0=Mon..6=Sun
        # store empty statuses; send_alerts will initialize per-day keys
        rem = Reminder(
            user_id=session['user_id'],
            medicine_id=medicine_id,
            reminder_time=reminder_time,
            frequency=frequency,
            statuses=json.dumps({}), 
            weekdays=weekdays,
            month_day=month_day_val,
            created_weekday=created_wd
        )
        db.session.add(rem)
        db.session.commit()
        flash("Reminder set!", "success")
        return redirect(url_for('dashboard'))
    reminders = Reminder.query.filter_by(user_id=session['user_id']).all()
    return render_template("reminder.html", medicines=medicines, reminders=reminders)

@app.route('/update_status/<int:reminder_id>/<time>/<status>', methods=['POST'])
def update_status(reminder_id, time, status):
    if "user_id" not in session:
        return redirect(url_for('login'))
    reminder = Reminder.query.get(reminder_id)
    if reminder and reminder.user_id==session['user_id']:
        stat_dict = reminder.status_dict

        # Always use only HH:MM as key
        time_key = time.split('|')[0] if '|' in time else time

        # Also set a date-scoped key so today's view (which may use HH:MM|YYYY-MM-DD)
        # reflects the change immediately. Use today's date.
        try:
            today_iso = datetime.now().date().isoformat()
            date_key = f"{time_key}|{today_iso}"
        except Exception:
            date_key = None

        # Write status to both plain and date-scoped keys
        stat_dict[time_key] = status
        if date_key:
            stat_dict[date_key] = status

        # If user marked Not Taken, schedule a one-time resend later today
        try:
            s = str(status).strip().lower()
        except Exception:
            s = ''

        if s in ('not taken', 'not-taken', 'not'):
            # minutes after which to resend (assumption: 15 minutes)
            RESEND_MINUTES = 15
            try:
                now_dt = datetime.now()
                followup_dt = now_dt + timedelta(minutes=RESEND_MINUTES)
                # only schedule if still the same day
                if followup_dt.date() == now_dt.date():
                    followup_time = followup_dt.strftime("%H:%M")
                    followup_key = f"{followup_time}|{followup_dt.date().isoformat()}"
                    # Marker to avoid scheduling multiple followups for the same reminder/day
                    marker_key = f"_resend_scheduled|{today_iso}"
                    # If we haven't already scheduled this followup, add it as Pending
                    if marker_key not in stat_dict and followup_key not in stat_dict:
                        stat_dict[followup_key] = "Pending"
                        stat_dict[marker_key] = followup_time
            except Exception:
                # If anything goes wrong, don't block the status update
                pass

        reminder.statuses = json.dumps(stat_dict)
        db.session.commit()
        flash(f"Status for time {time_key} updated to {status}", "success")
    return redirect(url_for('dashboard'))

@app.route('/expiry', methods=['GET','POST'])
def expiry():
    if "user_id" not in session:
        return redirect(url_for('login'))
    medicines = Medicine.query.filter_by(user_id=session['user_id']).all()
    if request.method=='POST':
        exp = MedicineExpiry(
            medicine_id=int(request.form['medicine_id']),
            batch_number=request.form['batch_number'],
            mfg_date=request.form['mfg_date'],
            expiry_date=request.form['expiry_date']
        )
        db.session.add(exp)
        db.session.commit()
        flash("Expiry info added!", "success")
        return redirect(url_for('dashboard'))
    expiries = MedicineExpiry.query.join(Medicine).filter(Medicine.user_id==session['user_id']).all()
    return render_template("expiry.html", medicines=medicines, expiries=expiries)

@app.route('/alternative', methods=['GET','POST'])
def alternative():
    grouped_results = []
    if request.method == 'POST':
        name = request.form['medicine_name'].strip().lower()
        # Try to find as original name
        orig = AlternativeMedicine.query.filter(func.lower(AlternativeMedicine.original_name) == name).first()
        if orig:
            original_name = orig.original_name
        else:
            # Try to find as alternative name
            alt = AlternativeMedicine.query.filter(func.lower(AlternativeMedicine.alternative_name) == name).first()
            if alt:
                original_name = alt.original_name
            else:
                original_name = None

        if original_name:
            results = AlternativeMedicine.query.filter(AlternativeMedicine.original_name == original_name).all()
            temp = {"conditions": set(), "alternatives": set()}
            for r in results:
                temp["conditions"].add(r.condition)
                temp["alternatives"].add(r.alternative_name)
            grouped_results.append({
                "original_name": original_name,
                "conditions": ", ".join(sorted(temp["conditions"])),
                "alternatives": sorted(temp["alternatives"])
            })
    return render_template("alternative.html", results=grouped_results)

@app.route('/test_email')
def test_email():
    try:
        ok = safe_send_email(subject="Test Email", recipients=[app.config['MAIL_USERNAME']], body="This is a test email from Flask-Mail.")
        return "Test email sent! Check your inbox." if ok else "Test email failed (see notification_errors.log)."
    except Exception as e:
        logger.error(f"test_email unexpected error: {e}")
        return f"Error: {e}"

# -----------------------------
# Alert System
# -----------------------------
def send_alerts():
    with app.app_context():
        while True:
            now = datetime.now()
            today_date = now.date()
            users = User.query.all()
            for user in users:
                # --- Medicine Expiry Alerts ---
                for med in Medicine.query.filter_by(user_id=user.id).all():
                    for exp in med.expiries:
                        try:
                            expiry_date = datetime.strptime(exp.expiry_date, "%Y-%m-%d")
                            days_left = (expiry_date - now).days
                            # Expiring soon (within 7 days, not expired, and not already alerted)
                            if 0 <= days_left <= 7 and not exp.expiring_alert_sent:
                                subject = f"Medicine Expiring Soon: {med.name}"
                                body = f"Dear {user.username}, your medicine '{med.name}' is expiring on {exp.expiry_date}."
                                email_ok = safe_send_email(subject=subject, recipients=[user.email], body=body)
                                sms_ok = safe_send_sms(to=f"+91{user.phone}", body=body)
                                if not email_ok:
                                    logger.warning(f"Expiry soon email not sent to {user.email} for {med.name}")
                                if not sms_ok:
                                    logger.warning(f"Expiry soon SMS not sent to {user.phone} for {med.name}")
                                exp.expiring_alert_sent = True
                                db.session.commit()
                            # Expired (not already alerted)
                            elif days_left < 0 and not exp.expired_alert_sent:
                                subject = f"Medicine Expired: {med.name}"
                                body = f"Dear {user.username}, your medicine '{med.name}' expired on {exp.expiry_date}."
                                email_ok = safe_send_email(subject=subject, recipients=[user.email], body=body)
                                sms_ok = safe_send_sms(to=f"+91{user.phone}", body=body)
                                if not email_ok:
                                    logger.warning(f"Expired email not sent to {user.email} for {med.name}")
                                if not sms_ok:
                                    logger.warning(f"Expired SMS not sent to {user.phone} for {med.name}")
                                exp.expired_alert_sent = True
                                db.session.commit()
                        except Exception as e:
                            print("Expiry check failed:", e)

                # --- Medicine Time Reminders ---
                for rem in Reminder.query.filter_by(user_id=user.id).all():
                    med = db.session.get(Medicine, rem.medicine_id)
                    # scheduled time string expected "HH:MM"
                    try:
                        # reminder_time may contain extra suffix (e.g. "HH:MM|YYYY-MM-DD")
                        raw_time = (rem.reminder_time or "").split("|")[0].strip()
                        time_str = raw_time
                        scheduled_time_obj = datetime.strptime(time_str, "%H:%M").time()
                    except Exception as e:
                        # invalid time format, skip
                        continue

                    # Decide if this reminder should run today based on frequency
                    should_run_today = False
                    freq = (rem.frequency or "").lower()
                    if 'daily' in freq or 'once' in freq:
                        should_run_today = True
                    elif 'weekly' in freq:
                        # check weekdays list if provided, else fallback to created_weekday
                        if rem.weekdays:
                            try:
                                wk = [int(x) for x in rem.weekdays.split(',') if x!='']
                                if now.weekday() in wk:
                                    should_run_today = True
                            except:
                                should_run_today = (now.weekday() == (rem.created_weekday or now.weekday()))
                        else:
                            should_run_today = (now.weekday() == (rem.created_weekday or now.weekday()))
                    elif 'monthly' in freq:
                        # use provided month_day else use created day
                        target_day = rem.month_day if rem.month_day else today_date.day
                        # if target_day > last day of month -> use last day
                        last_day = calendar.monthrange(today_date.year, today_date.month)[1]
                        scheduled_day = target_day if target_day <= last_day else last_day
                        if today_date.day == scheduled_day:
                            should_run_today = True

                    if not should_run_today:
                        continue

                    # Build a per-day status key so recurring reminders are tracked per date
                    today_key = f"{time_str}|{today_date.isoformat()}"
                    status_dict = rem.status_dict
                    # initialize if missing
                    if today_key not in status_dict:
                        status_dict[today_key] = "Pending"
                        rem.statuses = json.dumps(status_dict)
                        db.session.commit()

                    if status_dict.get(today_key) == "Pending":
                        # scheduled datetime for today
                        scheduled_dt = datetime.combine(today_date, scheduled_time_obj)
                        # If reminder time is within the next 5 minutes (or just passed within 5 minutes)
                        delta_sec = (scheduled_dt - now).total_seconds()
                        if 0 <= delta_sec <= 300:
                            subject = f"Time to take your medicine: {med.name}"
                            body = f"Dear {user.username}, it's time to take your medicine '{med.name}' ({med.dosage} {med.unit})."
                            email_ok = safe_send_email(subject=subject, recipients=[user.email], body=body)
                            sms_ok = safe_send_sms(to=f"+91{user.phone}", body=body)
                            if not email_ok:
                                logger.warning(f"Reminder email not sent to {user.email} for {med.name}")
                            if not sms_ok:
                                logger.warning(f"Reminder SMS not sent to {user.phone} for {med.name}")
                            # Mark as sent for today
                            status_dict[today_key] = "Sent"
                            rem.statuses = json.dumps(status_dict)
                            db.session.commit()
            time.sleep(60)  # Check every minute

# -----------------------------
# Initialize DB & Seed
# -----------------------------
with app.app_context():
    db.create_all()

    # Ensure Reminder table has new columns added to the model (safe for sqlite)
    def ensure_reminder_columns():
        inspector = inspect(db.engine)
        tables = inspector.get_table_names()
        if 'reminder' not in tables:
            return
        existing = [c['name'] for c in inspector.get_columns('reminder')]
        with db.engine.connect() as conn:
            # Add each column only if missing
            if 'weekdays' not in existing:
                conn.execute(text("ALTER TABLE reminder ADD COLUMN weekdays VARCHAR(50)"))
            if 'month_day' not in existing:
                conn.execute(text("ALTER TABLE reminder ADD COLUMN month_day INTEGER"))
            if 'created_weekday' not in existing:
                conn.execute(text("ALTER TABLE reminder ADD COLUMN created_weekday INTEGER"))
            if 'statuses' not in existing:
                # fallback: add statuses column (if you previously used a different column)
                conn.execute(text("ALTER TABLE reminder ADD COLUMN statuses TEXT DEFAULT '{}'"))
            # commit for sqlite
            conn.commit()

    ensure_reminder_columns()
    seed_alternatives()

# -----------------------------
# Start Alert System Thread (move here!)
# -----------------------------
threading.Thread(target=send_alerts, daemon=True).start()


# -----------------------------
# Run App
# -----------------------------
if __name__=="__main__":
    app.run(debug=True)


