from flask import Flask, render_template, redirect, request, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin, LoginManager, login_user, logout_user, current_user, login_required
from werkzeug.security import generate_password_hash, check_password_hash
import os
from datetime import datetime
import calendar

app = Flask(__name__)
app.static_folder = 'static'

basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'database.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'your_super_secret_key'
db = SQLAlchemy(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))
    role = db.Column(db.String(20), default='doctor')
    avatar_base64 = db.Column(db.Text, default='')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Patient(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    age = db.Column(db.Integer)
    gender = db.Column(db.String(10))
    visit_date = db.Column(db.Date, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    user = db.relationship('User', backref='patient', uselist=False)
    prescriptions = db.relationship('Prescription', backref='patient', lazy=True, cascade="all, delete-orphan")
    appointments = db.relationship('TelehealthAppointment', backref='patient', lazy=True, cascade="all, delete-orphan")
    lab_orders = db.relationship('LabOrder', backref='patient', lazy=True, cascade="all, delete-orphan")


class Prescription(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patient.id'), nullable=False)
    medication = db.Column(db.String(150), nullable=False)
    dosage = db.Column(db.String(50))
    instructions = db.Column(db.Text)


class TelehealthAppointment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patient.id'), nullable=False)
    appointment_time = db.Column(db.String(100), nullable=False)
    provider_detail = db.Column(db.String(150))
    status = db.Column(db.String(50))


class LabOrder(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patient.id'), nullable=False)
    order_type = db.Column(db.String(150), nullable=False)
    ordered_by = db.Column(db.String(100))
    status = db.Column(db.String(50))


def get_calendar_data(year, month):
    cal = calendar.Calendar(firstweekday=6)
    month_data = cal.monthdays2calendar(year, month)

    current_date = datetime.now().date()
    calendar_days = []

    for week in month_data:
        for day_num, weekday in week:
            if day_num == 0:
                calendar_days.append({'day': '', 'class': 'empty', 'is_today': False})
            else:
                date_obj = datetime(year, month, day_num).date()
                is_today = date_obj == current_date
                calendar_days.append({'day': day_num, 'class': '', 'is_today': is_today})

    return calendar_days


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        user = User.query.filter_by(username=username).first()

        if user is None or not user.check_password(password):
            flash('Invalid username or password', 'error')
            return redirect(url_for('login'))

        remember = request.form.get('remember') == 'on'

        login_user(user, remember=remember)
        return redirect(url_for('index'))

    return render_template('login.html')


@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    if request.method == 'POST':
        role = request.form.get('role')
        username = request.form.get('username')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        avatar_base64 = ''

        if password != confirm_password:
            flash('Passwords must match', 'error')
            return redirect(url_for('signup'))

        user_exists = User.query.filter_by(username=username).first()
        if user_exists:
            flash('Username already exists', 'error')
            return redirect(url_for('signup'))

        if not role:
            flash('Please select a role.', 'error')
            return redirect(url_for('signup'))

        new_user = User(username=username, avatar_base64=avatar_base64, role=role)
        new_user.set_password(password)

        db.session.add(new_user)
        db.session.commit()

        flash('Account created successfully! Please log in.', 'success')
        return redirect(url_for('login'))

    return render_template('signup.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))


@app.route('/')
@login_required
def index():
    if current_user.role == 'patient':
        return redirect(url_for('patient_dashboard'))

    first_patient = Patient.query.order_by(Patient.visit_date.desc()).first()

    today = datetime.now()
    cal_data = {
        'month_name': today.strftime('%B %Y'),
        'days': get_calendar_data(today.year, today.month)
    }

    if first_patient:
        return redirect(url_for('dashboard', patient_id=first_patient.id))

    return render_template('dashboard_view.html',
                           patients=[],
                           selected_patient=None,
                           prescriptions=[],
                           appointments=[],
                           lab_orders=[],
                           all_pending_labs=[],
                           calendar_data=cal_data)


@app.route('/patient_dashboard')
@login_required
def patient_dashboard():
    if current_user.role != 'patient':
        flash('Access denied', 'error')
        return redirect(url_for('index'))

    patient_record = Patient.query.filter_by(user_id=current_user.id).first()

    if not patient_record:
        flash('No patient record linked to your account.', 'error')
        return render_template('patient_dashboard.html', patient=None, prescriptions=[], lab_orders=[])

    prescriptions = patient_record.prescriptions
    lab_orders = patient_record.lab_orders

    return render_template('patient_dashboard.html',
                           patient=patient_record,
                           prescriptions=prescriptions,
                           lab_orders=lab_orders)


@app.route('/patient/<int:patient_id>')
@login_required
def dashboard(patient_id):
    if current_user.role != 'doctor':
        flash('Access denied', 'error')
        return redirect(url_for('index'))

    patients = Patient.query.order_by(Patient.visit_date.desc()).all()
    selected_patient = Patient.query.get_or_404(patient_id)
    prescriptions = selected_patient.prescriptions
    appointments = selected_patient.appointments
    lab_orders = selected_patient.lab_orders

    all_pending_labs = LabOrder.query.filter_by(status='Needs Submission').all()

    today = datetime.now()
    cal_data = {
        'month_name': today.strftime('%B %Y'),
        'days': get_calendar_data(today.year, today.month)
    }

    return render_template('dashboard_view.html',
                           patients=patients,
                           selected_patient=selected_patient,
                           prescriptions=prescriptions,
                           appointments=appointments,
                           lab_orders=lab_orders,
                           all_pending_labs=all_pending_labs,
                           calendar_data=cal_data)


@app.route('/add', methods=['GET', 'POST'])
@login_required
def add_patient():
    if current_user.role != 'doctor':
        flash('Access denied', 'error')
        return redirect(url_for('index'))

    if request.method == 'POST':
        try:
            name = request.form['name']
            age = int(request.form['age'])
            gender = request.form['gender']
            visit_date_str = request.form['visit_date']
            visit_date = datetime.strptime(visit_date_str, '%Y-%m-%d').date()

            new_patient = Patient(name=name, age=age, gender=gender, visit_date=visit_date)
            db.session.add(new_patient)
            db.session.commit()

            return redirect(url_for('dashboard', patient_id=new_patient.id))

        except Exception as e:
            flash(f"Error adding patient: {e}", 'error')
            return redirect(url_for('add_patient'))

    return render_template('add_patient.html', datetime=datetime)


@app.route('/delete_patient/<int:patient_id>', methods=['POST'])
@login_required
def delete_patient(patient_id):
    if current_user.role != 'doctor':
        flash('Access denied', 'error')
        return redirect(url_for('index'))

    patient = Patient.query.get_or_404(patient_id)

    try:
        db.session.delete(patient)
        db.session.commit()

        return redirect(url_for('index'))

    except Exception as e:
        flash(f"Error deleting patient: {e}", 'error')
        return redirect(url_for('dashboard', patient_id=patient_id))


@app.route('/add_prescription/<int:patient_id>', methods=['GET', 'POST'])
@login_required
def add_prescription(patient_id):
    if current_user.role != 'doctor':
        flash('Access denied', 'error')
        return redirect(url_for('index'))

    patient = Patient.query.get_or_404(patient_id)

    if request.method == 'POST':
        try:
            medication = request.form['medication']
            dosage = request.form['dosage']
            instructions = request.form['instructions']

            new_prescription = Prescription(
                patient_id=patient_id,
                medication=medication,
                dosage=dosage,
                instructions=instructions
            )
            db.session.add(new_prescription)
            db.session.commit()

            return redirect(url_for('dashboard', patient_id=patient_id))

        except Exception as e:
            flash(f"Error adding prescription: {e}", 'error')
            return render_template('add_prescription.html', patient=patient)

    return render_template('add_prescription.html', patient=patient)


@app.route('/edit_prescription/<int:rx_id>', methods=['GET', 'POST'])
@login_required
def edit_prescription(rx_id):
    if current_user.role != 'doctor':
        flash('Access denied', 'error')
        return redirect(url_for('index'))

    prescription = Prescription.query.get_or_404(rx_id)
    patient = prescription.patient

    if request.method == 'POST':
        try:
            prescription.medication = request.form['medication']
            prescription.dosage = request.form['dosage']
            prescription.instructions = request.form['instructions']

            db.session.commit()

            return redirect(url_for('dashboard', patient_id=patient.id))

        except Exception as e:
            flash(f"Error editing prescription: {e}", 'error')
            return render_template('edit_prescription.html', prescription=prescription, patient=patient)

    return render_template('edit_prescription.html', prescription=prescription, patient=patient)


@app.route('/delete_prescription/<int:rx_id>', methods=['POST'])
@login_required
def delete_prescription(rx_id):
    if current_user.role != 'doctor':
        flash('Access denied', 'error')
        return redirect(url_for('index'))

    prescription = Prescription.query.get_or_404(rx_id)
    patient_id = prescription.patient_id

    try:
        db.session.delete(prescription)
        db.session.commit()

        return redirect(url_for('dashboard', patient_id=patient_id))

    except Exception as e:
        flash(f"Error deleting prescription: {e}", 'error')
        return redirect(url_for('dashboard', patient_id=patient_id))


if __name__ == '__main__':
    app.run(debug=True)