from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "supersecretkey"
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///finance.db'
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'


# Пользователи и роли
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), nullable=False, unique=True)
    password = db.Column(db.String(150), nullable=False)
    role = db.Column(db.String(50), nullable=False, default="client")


class FinanceManager(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    balance = db.Column(db.Float, default=0)
    reserve = db.Column(db.Float, default=0)  # НЗ
    incomes = db.relationship('Income', backref='manager', lazy=True)
    expenses = db.relationship('Expense', backref='manager', lazy=True)


class Income(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    source = db.Column(db.String(150), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    manager_id = db.Column(db.Integer, db.ForeignKey('finance_manager.id'), nullable=False)


class Expense(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    category = db.Column(db.String(150), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    manager_id = db.Column(db.Integer, db.ForeignKey('finance_manager.id'), nullable=False)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


@app.route("/")
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return render_template("index.html")


@app.route("/dashboard")
@login_required
def dashboard():
    return render_template("index3.html", user=current_user)


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        user = User.query.filter_by(username=username).first()

        if user and check_password_hash(user.password, password):
            login_user(user)
            flash("Вы успешно вошли в систему", "success")
            return redirect(url_for('dashboard'))
        else:
            flash("Неверные учетные данные", "danger")
    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        password_confirm = request.form.get("password_confirm")
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            flash("Имя пользователя уже существует. Пожалуйста, выберите другое.", "danger")
            return redirect(url_for('register'))
        if password != password_confirm:
            flash("Пароли не совпадают.", "danger")
            return redirect(url_for('register'))
        hashed_password = generate_password_hash(password)
        new_user = User(username=username, password=hashed_password)
        db.session.add(new_user)
        db.session.commit()
        flash("Учетная запись успешно создана! Вы можете войти.", "success")
        return redirect(url_for('login'))

    return render_template("register.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Вы вышли из системы", "success")
    return redirect(url_for('index'))


@app.route("/add_income", methods=["POST"])
@login_required
def add_income():
    source = request.form.get("source")
    try:
        amount = float(request.form.get("amount"))
    except ValueError:
        flash("Пожалуйста, введите корректную сумму дохода.", "danger")
        return redirect(url_for("dashboard"))

    manager = FinanceManager.query.filter_by(user_id=current_user.id).first()
    if not manager:
        manager = FinanceManager(user_id=current_user.id)
        db.session.add(manager)

    income = Income(source=source, amount=amount, manager=manager)
    manager.balance += amount
    db.session.add(income)
    db.session.commit()
    flash(f"Доход в размере {amount} добавлен из {source}!", "success")
    return redirect(url_for("dashboard"))


@app.route("/add_expense", methods=["POST"])
@login_required
def add_expense():
    category = request.form.get("category")
    try:
        amount = float(request.form.get("amount"))
    except ValueError:
        flash("Пожалуйста, введите корректную сумму расхода.", "danger")
        return redirect(url_for("dashboard"))

    manager = FinanceManager.query.filter_by(user_id=current_user.id).first()
    if not manager:
        flash("Менеджер не найден!", "danger")
        return redirect(url_for("dashboard"))
    if manager.balance - amount < manager.reserve:
        flash("Операция отклонена! Баланс ниже резервной суммы.", "danger")
        return redirect(url_for("dashboard"))

    expense = Expense(category=category, amount=amount, manager=manager)
    manager.balance -= amount
    db.session.add(expense)
    db.session.commit()
    flash(f"Расход в размере {amount} добавлен в категорию {category}!", "success")
    return redirect(url_for("dashboard"))


@app.route("/get_data")
@login_required
def get_data():
    manager = FinanceManager.query.filter_by(user_id=current_user.id).first()
    if not manager:
        flash("Менеджер не найден!", "danger")
        return redirect(url_for("dashboard"))

    incomes = {income.source: income.amount for income in manager.incomes}
    expenses = {expense.category: expense.amount for expense in manager.expenses}

    return jsonify({
        "incomes": incomes,
        "expenses": expenses,
        "total_income": sum(incomes.values()),
        "total_expense": sum(expenses.values()),
        "balance": manager.balance,
        "reserve": manager.reserve
    })


@app.route("/create_admin", methods=["GET", "POST"])
@login_required
def create_admin():
    if current_user.role != "admin":
        flash("Доступ запрещен!", "danger")
        return redirect(url_for('dashboard'))

    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        password_confirm = request.form.get("password_confirm")

        existing_admin = User.query.filter_by(role='admin').first()
        if existing_admin:
            flash("Администратор уже создан. Вы можете войти с этой учетной записью.", "danger")
            return redirect(url_for('login'))

        if password != password_confirm:
            flash("Пароли не совпадают.", "danger")
            return redirect(url_for('create_admin'))

        hashed_password = generate_password_hash(password)
        new_admin = User(username=username, password=hashed_password, role='admin')
        db.session.add(new_admin)
        db.session.commit()
        flash("Администратор успешно создан! Вы можете войти.", "success")
        return redirect(url_for('login'))

    return render_template("create_admin.html")


@app.route("/admin")
@login_required
def admin_dashboard():
    if current_user.role != "admin":
        flash("Доступ запрещен!", "danger")
        return redirect(url_for("dashboard"))

    users = User.query.all()
    return render_template("admin.html", users=users)


@app.route("/admin/delete/<int:user_id>")
@login_required
def delete_user(user_id):
    if current_user.role != "admin":
        flash("Доступ запрещен!", "danger")
        return redirect(url_for("dashboard"))

    user_to_delete = User.query.get(user_id)
    if user_to_delete:
        db.session.delete(user_to_delete)
        db.session.commit()
        flash("Пользователь успешно удален!", "success")
    else:
        flash("Пользователь не найден!", "danger")
    return redirect(url_for("admin_dashboard"))


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)
