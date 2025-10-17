from flask import Flask, render_template, redirect, request, url_for
from flask_sqlalchemy import SQLAlchemy
import os
from datetime import datetime
import calendar

app = Flask(__name__)
app.static_folder = 'static'

basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'database.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)


class Patient(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    age = db.Column(db.Integer)
    gender = db.Column(db.String(10))
    visit_date = db.Column(db.Date, default=datetime.utcnow)
    prescriptions = db.relationship('Prescription', backref='patient', lazy=True, cascade="all, delete-orphan")


class Prescription(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patient.id'), nullable=False)
    medication = db.Column(db.String(150), nullable=False)
    dosage = db.Column(db.String(50))
    instructions = db.Column(db.Text)


def init_db_with_mock_data():
    with app.app_context():
        db.create_all()

        if Patient.query.count() > 0:
            return

        MOCK_PATIENTS_DATA = [
            {'name': 'Patient 1', 'age': 37, 'gender': 'Female', 'visit_date': '2024-09-15'},
            {'name': 'Patient 2', 'age': 42, 'gender': 'Male', 'visit_date': '2024-09-10'},
            {'name': 'Patient 3', 'age': 25, 'gender': 'Male', 'visit_date': '2024-09-01'},
            {'name': 'Patient 4', 'age': 61, 'gender': 'Male', 'visit_date': '2024-08-28'},
            {'name': 'Patient 5', 'age': 55, 'gender': 'Female', 'visit_date': '2024-08-15'},
            {'name': 'Patient 6', 'age': 40, 'gender': 'Male', 'visit_date': '2024-07-20'},
            {'name': 'Patient 7', 'age': 30, 'gender': 'Female', 'visit_date': '2024-07-10'},
        ]

        for p_data in MOCK_PATIENTS_DATA:
            date_obj = datetime.strptime(p_data['visit_date'], '%Y-%m-%d').date()
            patient = Patient(name=p_data['name'], age=p_data['age'], gender=p_data['gender'], visit_date=date_obj)
            db.session.add(patient)
        db.session.commit()

        first_patient = Patient.query.filter_by(name='Patient 1').first()
        if first_patient:
            patient_id = first_patient.id
            MOCK_PRESCRIPTIONS_DATA = [
                {'medication': 'Amoxicillin 250mg capsule', 'dosage': '500 mg',
                 'instructions': 'every 8 hours or 875 mg every 12 hours.'},
                {'medication': 'Flunisolide Nasal Spray', 'dosage': '50-100 mcg',
                 'instructions': '1 or 2 sprays into each nostril once daily.'},
                {'medication': 'Triamcinolone Cream', 'dosage': 'Thin layer',
                 'instructions': 'Apply 2 to 4 times daily to affected areas.'},
            ]
            for rx_data in MOCK_PRESCRIPTIONS_DATA:
                prescription = Prescription(
                    patient_id=patient_id,
                    medication=rx_data['medication'],
                    dosage=rx_data['dosage'],
                    instructions=rx_data['instructions']
                )
                db.session.add(prescription)
        db.session.commit()


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


@app.route('/')
def index():
    first_patient = Patient.query.order_by(Patient.visit_date.desc()).first()

    today = datetime.now()
    cal_data = {
        'month_name': today.strftime('%B %Y'),
        'days': get_calendar_data(today.year, today.month)
    }

    if first_patient:
        return redirect(url_for('dashboard', patient_id=first_patient.id))
    return render_template('dashboard_view.html', patients=[], selected_patient=None, prescriptions=[],
                           telehealth_appointments=[], lab_orders=[], calendar_data=cal_data)


@app.route('/patient/<int:patient_id>')
def dashboard(patient_id):
    patients = Patient.query.order_by(Patient.visit_date.desc()).all()
    selected_patient = Patient.query.get_or_404(patient_id)
    prescriptions = selected_patient.prescriptions

    telehealth_appointments = []
    lab_orders = []

    today = datetime.now()
    cal_data = {
        'month_name': today.strftime('%B %Y'),
        'days': get_calendar_data(today.year, today.month)
    }

    return render_template('dashboard_view.html',
                           patients=patients,
                           selected_patient=selected_patient,
                           prescriptions=prescriptions,
                           telehealth_appointments=telehealth_appointments,
                           lab_orders=lab_orders,
                           calendar_data=cal_data)


@app.route('/add', methods=['GET', 'POST'])
def add_patient():
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
            print(f"Error adding patient: {e}")
            return redirect(url_for('add_patient'))

    return render_template('add_patient.html')


@app.route('/delete_patient/<int:patient_id>', methods=['POST'])
def delete_patient(patient_id):
    patient = Patient.query.get_or_404(patient_id)

    try:
        db.session.delete(patient)
        db.session.commit()

        return redirect(url_for('index'))

    except Exception as e:
        print(f"Error deleting patient: {e}")
        return redirect(url_for('dashboard', patient_id=patient_id))


@app.route('/add_prescription/<int:patient_id>', methods=['GET', 'POST'])
def add_prescription(patient_id):
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
            print(f"Error adding prescription: {e}")
            return render_template('add_prescription.html', patient=patient)

    return render_template('add_prescription.html', patient=patient)


@app.route('/edit_prescription/<int:rx_id>', methods=['GET', 'POST'])
def edit_prescription(rx_id):
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
            print(f"Error editing prescription: {e}")
            return render_template('edit_prescription.html', prescription=prescription, patient=patient)

    return render_template('edit_prescription.html', prescription=prescription, patient=patient)


@app.route('/delete_prescription/<int:rx_id>', methods=['POST'])
def delete_prescription(rx_id):
    prescription = Prescription.query.get_or_404(rx_id)
    patient_id = prescription.patient_id

    try:
        db.session.delete(prescription)
        db.session.commit()

        return redirect(url_for('dashboard', patient_id=patient_id))

    except Exception as e:
        print(f"Error deleting prescription: {e}")
        return redirect(url_for('dashboard', patient_id=patient_id))


if __name__ == '__main__':
    with app.app_context():
        init_db_with_mock_data()

    app.run(debug=True)