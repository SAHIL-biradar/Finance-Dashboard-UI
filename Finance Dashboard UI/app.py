from flask import Flask, render_template, request, redirect, url_for, session, send_file, flash
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
from io import StringIO
import csv
from datetime import datetime, date
from io import BytesIO  # Add this at the top with your other imports
from flask import Response
import os
if os.environ.get("RENDER"):
    DB = "/tmp/expense_web.db"
else:
    DB = os.environ.get("DATABASE_URL", "expense_web.db")

CATEGORIES = ["Food", "Rent", "Travel", "Shopping", "Salary", "Entertainment", "Bills", "Pocket Money","Other"]

app = Flask(__name__)
app.secret_key = "replace_this_with_a_random_secret"  # change for production





def get_conn():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL
    )
    """)
    c.execute("""
    CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        amount REAL NOT NULL,
        category TEXT NOT NULL,
        type TEXT NOT NULL,
        description TEXT,
        date TEXT NOT NULL,
        FOREIGN KEY(user_id) REFERENCES users(id)
    )
    """)
    conn.commit()
    conn.close()




# ---------- Auth ----------
@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"].strip()
        conn = get_conn()
        c = conn.cursor()
        c.execute("SELECT id, password_hash FROM users WHERE username = ?", (username,))
        row = c.fetchone()
        conn.close()
        if row and check_password_hash(row["password_hash"], password):
            session["user_id"] = row["id"]
            session["username"] = username
            return redirect(url_for("dashboard"))
        flash("Invalid username or password", "danger")
    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"].strip()
        if not username or not password:
            flash("Username and password required", "warning")
            return redirect(url_for("register"))
        hashed = generate_password_hash(password)
        try:
            conn = get_conn()
            c = conn.cursor()
            c.execute("INSERT INTO users (username, password_hash) VALUES (?, ?)", (username, hashed))
            conn.commit()
            conn.close()
            flash("Account created — please login", "success")
            return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            flash("Username already taken", "warning")
            return redirect(url_for("register"))
    return render_template("register.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


def login_required(func):
    from functools import wraps
    @wraps(func)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return func(*args, **kwargs)
    return wrapper


# ---------- Dashboard ----------
@app.route("/dashboard")
@login_required
def dashboard():
    uid = session["user_id"]
    # default: current month
    year = request.args.get("year", None)
    month = request.args.get("month", None)
    if not year or not month:
        today = date.today()
        year, month = today.year, today.month
    else:
        year, month = int(year), int(month)
    start = date(year, month, 1).isoformat()
    if month == 12:
        end = date(year+1, 1, 1).isoformat()
    else:
        end = date(year, month+1, 1).isoformat()

    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        SELECT sum(CASE WHEN type='Income' THEN amount ELSE 0 END) as income,
               sum(CASE WHEN type='Expense' THEN amount ELSE 0 END) as expense
        FROM transactions
        WHERE user_id = ? AND date >= ? AND date < ?
    """, (uid, start, end))
    row = c.fetchone()
    income = row["income"] or 0.0
    expense = row["expense"] or 0.0
    balance = income - expense

    # breakdown by category (expenses only)
    c.execute("""
        SELECT category, SUM(amount) as total FROM transactions
        WHERE user_id = ? AND type='Expense' AND date >= ? AND date < ?
        GROUP BY category
    """, (uid, start, end))
    cat_rows = c.fetchall()
    cat_labels = [r["category"] for r in cat_rows]
    cat_values = [r["total"] for r in cat_rows]

    # monthly trend (last 6 months)
    trend = []
    today = date.today()
    for i in range(5, -1, -1):
        m = today.month - i
        y = today.year
        while m <= 0:
            m += 12
            y -= 1
        s = date(y, m, 1).isoformat()
        if m == 12:
            e = date(y+1, 1, 1).isoformat()
        else:
            e = date(y, m+1, 1).isoformat()
        c.execute("""
            SELECT SUM(CASE WHEN type='Income' THEN amount ELSE 0 END) as inc,
                   SUM(CASE WHEN type='Expense' THEN amount ELSE 0 END) as exp
            FROM transactions
            WHERE user_id = ? AND date >= ? AND date < ?
        """, (uid, s, e))
        r = c.fetchone()
        trend.append({"label": f"{y}-{m:02d}", "income": r["inc"] or 0.0, "expense": r["exp"] or 0.0})
    conn.close()

    return render_template("dashboard.html",
                           income=income, expense=expense, balance=balance,
                           cat_labels=cat_labels, cat_values=cat_values,
                           trend=trend, year=year, month=month,
                           categories=CATEGORIES)


# ---------- Add transaction ----------
@app.route("/add", methods=["GET", "POST"])
@login_required
def add():
    if request.method == "POST":
        uid = session["user_id"]
        ttype = request.form.get("type")
        amount = request.form.get("amount")
        category = request.form.get("category")
        date_s = request.form.get("date")
        description = request.form.get("description")
        # basic validation
        try:
            amount = float(amount)
        except Exception:
            flash("Invalid amount", "warning")
            return redirect(url_for("add"))
        try:
            datetime.strptime(date_s, "%Y-%m-%d")
        except Exception:
            flash("Date must be YYYY-MM-DD", "warning")
            return redirect(url_for("add"))
        conn = get_conn()
        c = conn.cursor()
        c.execute("""
            INSERT INTO transactions (user_id, amount, category, type, description, date)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (uid, amount, category, ttype, description, date_s))
        conn.commit()
        conn.close()
        flash("Transaction added", "success")
        return redirect(url_for("dashboard"))
    
    # GET request → show the add form with current date
    return render_template("add.html", categories=CATEGORIES, today=date.today())


# ---------- History & Export ----------
@app.route("/history")
@login_required
def history():
    uid = session["user_id"]
    start = request.args.get("from", None)
    end = request.args.get("to", None)
    if start and end:
        # validate YYYY-MM-DD
        try:
            datetime.strptime(start, "%Y-%m-%d")
            datetime.strptime(end, "%Y-%m-%d")
        except Exception:
            flash("Dates must be YYYY-MM-DD", "warning")
            return redirect(url_for("history"))
    conn = get_conn()
    c = conn.cursor()
    if start and end:
        c.execute("SELECT * FROM transactions WHERE user_id = ? AND date >= ? AND date <= ? ORDER BY date DESC", (uid, start, end))
    else:
        c.execute("SELECT * FROM transactions WHERE user_id = ? ORDER BY date DESC", (uid,))
    rows = c.fetchall()
    conn.close()
    return render_template("history.html", rows=rows)






@app.route("/export")
@login_required
def export():
    uid = session["user_id"]
    year = request.args.get("year", None)
    month = request.args.get("month", None)
    
    conn = get_conn()
    c = conn.cursor()
    
    if year and month:
        y, m = int(year), int(month)
        start = date(y, m, 1).isoformat()
        end = date(y, m+1, 1).isoformat() if m < 12 else date(y+1, 1, 1).isoformat()
        c.execute("""
            SELECT date, type, amount, category, description 
            FROM transactions 
            WHERE user_id=? AND date>=? AND date<? 
            ORDER BY date DESC
        """, (uid, start, end))
        filename = f"transactions_{y}_{m:02d}.csv"
    else:
        c.execute("""
            SELECT date, type, amount, category, description 
            FROM transactions 
            WHERE user_id=? 
            ORDER BY date DESC
        """, (uid,))
        filename = "transactions_all.csv"

    rows = c.fetchall()
    conn.close()

    # Create CSV in memory
    from io import StringIO
    import csv
    csv_buffer = StringIO()
    writer = csv.writer(csv_buffer)
    writer.writerow(["date", "type", "amount", "category", "description"])
    for r in rows:
        writer.writerow([r["date"], r["type"], r["amount"], r["category"], r["description"]])
    
    csv_buffer.seek(0)
    
    # Return as downloadable CSV
    return Response(
        csv_buffer.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment;filename={filename}"}
    )



if __name__ == "__main__":
    with app.app_context():
        init_db()  # create tables when app starts
    app.run(debug=True)



