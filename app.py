from flask import Flask, render_template, redirect, request
from flask_scss import Scss
from flask_sqlalchemy import SQLAlchemy
app = Flask(__name__)
Scss(app)

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'

db = SQLAlchemy(app)

class MyTask(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    task = db.Column(db.String(200), nullable=False)
    complete = db.Column(db.Integer, nullable=False, default=0)
    created = db.Column(db.DateTime, nullable=False, default=db.func.current_timestamp())

    def __repr__(self) -> str:
        return f"Task {self.id}"

with app.app_context():
    db.create_all()
@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        task = request.form['task']
        new_task = MyTask(task=task)
        try:
            db.session.add(new_task)
            db.session.commit()
            return redirect('/')
        except Exception as e:
            print(f"Error: {e}")
            return f"Error: {e}"
    else:
        tasks = MyTask.query.order_by(MyTask.created).all()
        return render_template('index.html', tasks=tasks)

@app.route('/delete/<int:id>')
def delete(id):
    task_to_delete = MyTask.query.get_or_404(id)
    try:
        db.session.delete(task_to_delete)
        db.session.commit()
        return redirect('/')
    except Exception as e:
        print(f"Error: {e}")
        return f"Error: {e}"

@app.route('/update/<int:id>', methods=['GET', 'POST'])
def update(id):
    task = MyTask.query.get_or_404(id)
    if request.method == 'POST':
        task.task = request.form['task']
        try:
            db.session.commit()
            return redirect('/')
        except Exception as e:
            print(f"Error: {e}")
            return f"Error: {e}"
    else:
        return  render_template('update.html', task=task)

if __name__ == '__main__':
    app.run(debug=True)
