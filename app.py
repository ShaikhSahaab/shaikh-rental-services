from flask import Flask, render_template, request, redirect, session, send_file
import sqlite3
from io import BytesIO
import json
import uuid
import os
from datetime import datetime, timedelta
from fpdf import FPDF
from flask import flash
from werkzeug.utils import secure_filename
from flask import Flask, render_template, request, redirect, session, flash
from werkzeug.security import generate_password_hash, check_password_hash






app = Flask(__name__)
app.secret_key = "secret123"

# Remember me: keep session for 7 days
app.permanent_session_lifetime = timedelta(days=7)

UPLOAD_FOLDER = "static/cars"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER




# ---------------- DATABASE ----------------

def db():
    return sqlite3.connect("database.db")

def init_db():
    con = db()
    cur = con.cursor()

    # USERS
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users(
            id INTEGER PRIMARY KEY,
            name TEXT,
            email TEXT,
            password TEXT
        )
    """)

    # ADMIN
    cur.execute("""
        CREATE TABLE IF NOT EXISTS admin(
            id INTEGER PRIMARY KEY,
            username TEXT,
            password TEXT
        )
    """)

    # CARS (FIXED: image column added)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS cars(
        id INTEGER PRIMARY KEY,
        name TEXT,
        price INTEGER,
        available INTEGER,
        image TEXT,
        discount INTEGER DEFAULT 0
    )
""")



    # BOOKINGS (FIXED: return_date included)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS bookings(
        id INTEGER PRIMARY KEY,
        user_id INTEGER,
        car_id INTEGER,
        days INTEGER,
        total INTEGER,
        date TEXT,
        return_date TEXT,
        status TEXT,
        paid INTEGER DEFAULT 0,
        payment_mode TEXT
    )
""")


    # DEFAULT ADMIN
    cur.execute("""
        INSERT OR IGNORE INTO admin(id,username,password)
        VALUES (1,'admin','admin123')
    """)

    # CARS DATA (CORRECT ORDER)
    cars = [
    (1, "Swift", 1200, 1, "swift.png"),
    (2, "Creta", 2200, 1, "creta.png"),
    (3, "Innova Crysta", 2400, 1, "innova.png"),
    (4, "Honda CB350", 1300, 1, "hondacb350.png"),
    (5, "Royal Enfield Classic", 1500, 1, "reclassic.png"),
    (6, "Royal Enfield Bullet", 1600, 1, "bullet.png"),
    (7, "Baleno", 1100, 1, "baleno.png"),
    (8, "Verna", 1800, 1, "verna.png"),
    (9, "City", 1900, 1, "city.png"),
    (10, "XUV700", 2800, 1, "XUV700.png"),
    (11, "Fortuner", 3800, 1, "fortuner.png"),
    (12, "Thar", 2600, 1, "thar.png"),
    (13, "Ertiga", 1700, 1, "ertiga.png"),
    (14, "Jupiter", 300, 1, "jupiter.png"),
    (15, "Activa", 350, 1, "activa.png"),
    (16, "KTM", 1000, 1, "ktm.png"),
    (17, "KTM Duke", 1200, 1, "duke_ktm.png"),
    (18, "Duke 125", 1100, 1, "duke125.png"),
    (19, "Bajaj Pulsar", 900, 1, "pulsar.png"),
    (20, "Qashqai", 2000, 1, "qashqai.png"),
]



    cur.executemany("""
        INSERT OR IGNORE INTO cars(id,name,price,available,image)
        VALUES (?,?,?,?,?)
    """, cars)

    try:cur.execute("ALTER TABLE bookings ADD COLUMN original_price INTEGER")
    except:pass

    try:cur.execute("ALTER TABLE bookings ADD COLUMN discount_amount INTEGER DEFAULT 0")
    except: pass

    try:cur.execute("ALTER TABLE bookings ADD COLUMN coupon_code TEXT")
    except:pass

    try:cur.execute("ALTER TABLE bookings ADD COLUMN paid INTEGER DEFAULT 0")
    except:pass


    con.commit()
    con.close()

# ---------------- USER LOGIN / REGISTER ----------------
@app.route("/login", methods=["GET", "POST"])
def login():
    # Already logged in
    if session.get("role") == "user":
        return redirect("/dashboard")
    if session.get("role") == "admin":
        return redirect("/admin")

    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        con = db()
        cur = con.cursor()
        cur.execute("""
            SELECT id, name, role
            FROM users
            WHERE email=? AND password=?
        """, (email, password))
        user = cur.fetchone()
        con.close()

        if user:
            session.clear()
            session["user_id"] = user[0]
            session["user_name"] = user[1]
            session["role"] = user[2]

            flash("Login successful", "success")

            if user[2] == "admin":
                return redirect("/admin")
            return redirect("/dashboard")

        flash("Invalid email or password", "danger")

    return render_template("login.html")






@app.route("/register", methods=["GET", "POST"])
def register():
    # Logged-in users shouldn’t register again
    if session.get("role"):
        return redirect("/")

    if request.method == "POST":
        name = request.form["name"]
        email = request.form["email"]
        password = request.form["password"]

        con = db()
        cur = con.cursor()

        # Prevent duplicate email
        cur.execute("SELECT id FROM users WHERE email=?", (email,))
        if cur.fetchone():
            con.close()
            flash("Email already registered", "warning")
            return redirect("/register")

        cur.execute("""
            INSERT INTO users (name, email, password, role)
            VALUES (?, ?, ?, 'user')
        """, (name, email, password))
        con.commit()
        con.close()

        flash("Registration successful. Please login.", "success")
        return redirect("/login")

    return render_template("register.html")


# ---------------- DASHBOARD ----------------
@app.route("/dashboard")
def dashboard():
    if session.get("role") != "user":
        flash("Please login first", "warning")
        return redirect("/")

    sort = request.args.get("sort")
    availability = request.args.get("availability")

    # ✅ FETCH CARS (WITH DISCOUNT)
    query = """
        SELECT id, name, price, available, image, discount
        FROM cars
    """
    conditions = []

    if availability == "available":
        conditions.append("available = 1")

    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    if sort == "price_low":
        query += " ORDER BY price ASC"
    elif sort == "price_high":
        query += " ORDER BY price DESC"

    con = db()
    cur = con.cursor()

    cur.execute(query)
    cars = cur.fetchall()

    # ✅ FETCH USER BOOKINGS
    cur.execute(
        """
        SELECT * FROM bookings
        WHERE user_id=? AND status IN ('Booked','Paid')
        """,
        (session["user_id"],)
    )
    bookings = cur.fetchall()

    con.close()

    return render_template(
        "dashboard.html",
        cars=cars,
        bookings=bookings,
        sort=sort,
        availability=availability
    )



# ---------------- BOOK CAR ----------------
@app.route("/book/<int:id>", methods=["GET", "POST"])
def book(id):
    if session.get("role") != "user":
        return redirect("/")

    con = db()
    cur = con.cursor()

    # Fetch car details safely
    cur.execute("""
        SELECT name, price, available, discount
        FROM cars
        WHERE id=?
    """, (id,))
    car = cur.fetchone()

    if not car:
        con.close()
        flash("Car not found", "danger")
        return redirect("/dashboard")

    car_name, price, available, discount = car
    discount = discount or 0

    if available == 0:
        con.close()
        flash("Car is not available", "warning")
        return redirect("/dashboard")

    if request.method == "POST":
        days = int(request.form.get("days", 1))
        pay_type = request.form.get("pay_type")

        # ✅ Price calculation
        discounted_price = price - (price * discount // 100)
        total = discounted_price * days

        # ✅ Status handling
        if pay_type == "pay_now":
            status = "Paid"
        elif pay_type == "pay_later":
            status = "Booked"
        else:
            con.close()
            flash("Invalid payment option", "danger")
            return redirect("/dashboard")

        # Insert booking
        cur.execute("""
            INSERT INTO bookings (user_id, car_id, days, total, date, status)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            session["user_id"],
            id,
            days,
            total,
            datetime.now(),
            status
        ))

        booking_id = cur.lastrowid

        # Mark car unavailable
        cur.execute("UPDATE cars SET available=0 WHERE id=?", (id,))
        

        con.commit()
        con.close()

        # Redirect correctly
        if pay_type == "pay_now":
            return redirect(f"/payment/{booking_id}")

        flash("Car booked successfully. Pay later from dashboard.", "success")
        return redirect("/dashboard")

    con.close()
    return render_template(
        "book.html",
        car_name=car_name,
        price=price,
        discount=discount
    )

# ---------------- CANCEL CAR ----------------


@app.route("/cancel_booking/<int:booking_id>", methods=["POST"])
def cancel_booking(booking_id):
    if session.get("role") != "user":
        return {"success": False}, 403

    con = db()
    cur = con.cursor()

    cur.execute("""
        SELECT status, user_id, car_id
        FROM bookings
        WHERE id = ?
    """, (booking_id,))
    row = cur.fetchone()

    if not row:
        con.close()
        return {"success": False}

    status, user_id, car_id = row

    if user_id != session.get("user_id"):
        con.close()
        return {"success": False}

    status = (status or "").lower()

    # ❌ Do not allow cancel after return/refund
    if status not in ("booked", "paid"):
        con.close()
        return {"success": False}

    # 🔹 CASE 1: DELIVER / CANCEL (PAID)
    if status == "paid":
        cur.execute("""
            UPDATE bookings
            SET status = 'Refunding',
                refund_status = 'pending'
            WHERE id = ?
        """, (booking_id,))
        was_paid = True

    # 🔹 CASE 2: PAY / CANCEL (NOT PAID)
    else:
        cur.execute("""
            UPDATE bookings
            SET status = 'Cancelled',
                refund_status = NULL
            WHERE id = ?
        """, (booking_id,))
        was_paid = False

    # ✅ FREE THE CAR
    cur.execute("""
        UPDATE cars
        SET available = 1
        WHERE id = ?
    """, (car_id,))

    con.commit()
    con.close()

    return {
        "success": True,
        "was_paid": was_paid
    }







# ---------------- PAYMENT ----------------
@app.route("/payment/<int:booking_id>", methods=["GET", "POST"])
def payment_mode(booking_id):
    if session.get("role") != "user":
        return redirect("/")

    con = db()
    cur = con.cursor()

    # 🔹 Ensure booking exists + get total
    cur.execute("""
        SELECT id, total, paid
        FROM bookings
        WHERE id=?
    """, (booking_id,))
    booking = cur.fetchone()

    if not booking:
        con.close()
        flash("Invalid booking", "danger")
        return redirect("/dashboard")
    
        

    booking_id, total_amount, already_paid = booking

    return render_template(
        "payment.html",
        booking_id=booking_id,
        amount=booking[1]
      )

    

    if request.method == "POST":
        payment_mode = request.form.get("payment_mode")

        if not payment_mode:
            flash("Please select a payment mode", "warning")
            con.close()
    return redirect(f"/payment/{booking_id}")

        # 🚫 Prevent double payment
    if already_paid:
            con.close()
            flash("Payment already completed", "warning")
            return redirect("/dashboard")

        # ✅ Mark booking as paid
            cur.execute("""
            UPDATE bookings
            SET status='Paid',
                payment_mode=?,
                paid=1
            WHERE id=?
        """, (payment_mode, booking_id))

        # ✅ ADD REVENUE (INCOME)
            cur.execute("""
            INSERT INTO revenue (booking_id, amount, type, created_at)
            VALUES (?, ?, 'income', datetime('now'))
        """, (booking_id, total_amount))

            con.commit()
            con.close()

            return redirect(f"/generate_invoice/{booking_id}")

    con.close()
    return render_template("payment.html", booking_id=booking_id)




@app.route("/payment_success/<int:booking_id>")
def payment_success(booking_id):
    return render_template(
        "payment_success.html",
        booking_id=booking_id
    )


def add_payment_mode_column():
    con = db()
    cur = con.cursor()
    try:
        cur.execute("ALTER TABLE bookings ADD COLUMN payment_mode TEXT")
        con.commit()
    except:
        pass
    con.close()

    




# ---------------- PDF INVOICE ----------------
@app.route("/generate_invoice/<int:booking_id>")
def generate_invoice(booking_id):
    con = db()
    cur = con.cursor()

    cur.execute("""
        SELECT 
            bookings.id,
            users.name,
            cars.name,
            bookings.days,
            bookings.total,
            bookings.date,
            bookings.status,
            cars.price,
            cars.discount,
            bookings.payment_mode
        FROM bookings
        JOIN users ON bookings.user_id = users.id
        JOIN cars ON bookings.car_id = cars.id
        WHERE bookings.id = ?
          AND bookings.user_id = ?
    """, (booking_id, session["user_id"]))

    b = cur.fetchone()
    con.close()

    # ❗ VERY IMPORTANT CHECK
    if not b:
        flash("Invoice not found", "danger")
        return redirect("/invoice_history")

    # ✅ NOW b EXISTS — SAFE TO USE
    invoice_year = b[5][:4]
    invoice_number = f"INV-{invoice_year}-{b[0]:04d}"

    # -------- CALCULATIONS --------
    price = b[7]
    discount = b[8] or 0
    discounted_price = price - (price * discount // 100)
    saved = (price - discounted_price) * b[3]
    original_amount = price * b[3]

    # -------- PDF --------
    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)

    # HEADER
    pdf.set_font("Arial", "B", 18)
    pdf.cell(0, 10, "SHAIKH'S RENTAL SERVICES", ln=True, align="C")
    pdf.set_font("Arial", size=11)
    pdf.cell(0, 6, "Reliable | Affordable | Fast", ln=True, align="C")
    pdf.ln(10)

    # META
    pdf.set_font("Arial", size=11)
    pdf.cell(100, 8, f"Invoice No: {invoice_number}")
    pdf.cell(100, 8, f"Date: {b[5][:10]}", ln=True)
    pdf.ln(6)

    # CUSTOMER
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 8, "BILLED TO", ln=True)
    pdf.set_font("Arial", size=11)
    pdf.cell(0, 7, b[1], ln=True)
    pdf.cell(0, 7, f"Payment Mode: {b[9] or '-'}", ln=True)
    pdf.cell(0, 7, f"Status: {b[7].capitalize()}", ln=True)
    pdf.ln(6)

    # TABLE (SAFE WIDTHS)
    pdf.set_font("Arial", "B", 11)
    pdf.cell(90, 10, "Particulars", 1, 0, "C")
    pdf.cell(30, 10, "Rate", 1, 0, "C")
    pdf.cell(20, 10, "Days", 1, 0, "C")
    pdf.cell(40, 10, "Amount", 1, 1, "C")

    pdf.set_font("Arial", size=11)
    pdf.cell(90, 9, b[2], 1)
    pdf.cell(30, 9, str(price), 1, 0, "C")
    pdf.cell(20, 9, str(b[3]), 1, 0, "C")
    pdf.cell(40, 9, str(original_amount), 1, 1, "C")

    pdf.cell(140, 9, f"Discount ({discount}%)", 1)
    pdf.cell(40, 9, f"- {saved}", 1, 1, "C")

    pdf.set_font("Arial", "B", 12)
    pdf.cell(140, 10, "TOTAL AMOUNT PAID", 1)
    pdf.cell(40, 10, str(b[4]), 1, 1, "C")

    # FOOTER
    pdf.ln(8)
    pdf.set_font("Arial", size=10)
    pdf.multi_cell(
        0, 6,
        "This is a system-generated invoice.\n"
        "All payments once completed are non-refundable."
    )

    file_path = f"invoice_{b[0]}.pdf"
    pdf.output(file_path)

    return send_file(file_path, as_attachment=True)


# ---------------- INVOICE HISTORY ----------------

@app.route("/invoice_history", methods=["GET", "POST"])
def invoice_history():
    if session.get("role") != "user":
        return redirect("/")

    con = db()
    cur = con.cursor()
    invoices = []
    start = end = None

    if request.method == "POST":
        start = request.form.get("start")
        end = request.form.get("end")
        action = request.form.get("action")

        start_dt = start + " 00:00:00"
        end_dt = end + " 23:59:59"

        # FETCH INVOICES
        cur.execute("""
            SELECT
                b.id,               -- 0 Invoice ID
                c.name,             -- 1 Car name
                b.days,             -- 2 Days
                c.price,            -- 3 Original price per day
                c.discount,         -- 4 Discount %
                b.total,            -- 5 Amount paid
                b.payment_mode,     -- 6 Payment mode
                b.status,           -- 7 Status (Paid / Delivered / Completed)
                b.date              -- 8 Date
            FROM bookings b
            JOIN cars c ON b.car_id = c.id
            WHERE b.user_id = ?
              AND b.date BETWEEN ? AND ?
            ORDER BY b.date ASC
        """, (session["user_id"], start_dt, end_dt))

        invoices = cur.fetchall()

        # ================= DOWNLOAD PDF =================
        if action == "download":
            if not invoices:
                flash("No invoices found for selected period", "warning")
                con.close()
                return redirect("/invoice_history")

            pdf = FPDF()
            pdf.add_page()
            pdf.set_auto_page_break(auto=True, margin=15)

            # HEADER
            pdf.set_font("Arial", "B", 18)
            pdf.cell(0, 10, "CAR RENTAL SERVICES", ln=True, align="C")
            pdf.set_font("Arial", size=11)
            pdf.cell(0, 6, "Invoice History Report", ln=True, align="C")
            pdf.ln(8)

            # META
            pdf.set_font("Arial", size=11)
            pdf.cell(0, 8, f"Customer: {session.get('user_name')}", ln=True)
            pdf.cell(0, 8, f"Period: {start} to {end}", ln=True)
            pdf.ln(6)

            # TABLE HEADER
            pdf.set_font("Arial", "B", 9)
            pdf.cell(10, 8, "ID", 1, 0, "C")
            pdf.cell(25, 8, "Car", 1, 0, "C")
            pdf.cell(10, 8, "Days", 1, 0, "C")
            pdf.cell(20, 8, "Price", 1, 0, "C")
            pdf.cell(15, 8, "Disc%", 1, 0, "C")
            pdf.cell(20, 8, "Saved", 1, 0, "C")
            pdf.cell(22, 8, "Paid", 1, 0, "C")
            pdf.cell(25, 8, "Mode", 1, 0, "C")
            pdf.cell(20, 8, "Status", 1, 0, "C")
            pdf.cell(25, 8, "Date", 1, 1, "C")

            # TABLE BODY
            pdf.set_font("Arial", size=9)
            total_paid = 0

            for inv in invoices:
                price = inv[3]
                discount = inv[4] or 0
                discounted_price = price - (price * discount // 100)
                saved = (price - discounted_price) * inv[2]

                pdf.cell(10, 8, str(inv[0]), 1, 0, "C")
                pdf.cell(25, 8, inv[1][:12], 1, 0, "C")
                pdf.cell(10, 8, str(inv[2]), 1, 0, "C")
                pdf.cell(20, 8, f"Rs {price}", 1, 0, "C")
                pdf.cell(15, 8, f"{discount}%", 1, 0, "C")
                pdf.cell(20, 8, f"Rs {saved}", 1, 0, "C")
                pdf.cell(22, 8, f"Rs {inv[5]}", 1, 0, "C")
                pdf.cell(25, 8, inv[6] or "-", 1, 0, "C")
                pdf.cell(20, 8, inv[7].capitalize(), 1, 0, "C")
                pdf.cell(25, 8, inv[8][:10], 1, 1, "C")

                total_paid += inv[5]

            # TOTAL
            pdf.ln(4)
            pdf.set_font("Arial", "B", 11)
            pdf.cell(157, 10, "TOTAL AMOUNT PAID", 1)
            pdf.cell(33, 10, f"Rs {total_paid}", 1, ln=True)

            # FOOTER
            pdf.ln(8)
            pdf.set_font("Arial", size=10)
            pdf.multi_cell(
                0, 6,
                "This is a system-generated invoice history report.\n"
                "All payments are final and non-refundable."
            )

            file_path = "invoice_history_report.pdf"
            pdf.output(file_path)
            con.close()
            return send_file(file_path, as_attachment=True)

    con.close()
    return render_template(
        "invoice_history.html",
        invoices=invoices,
        start=start,
        end=end
    )


    # ----------INDIVISUAL DOWNLOAD INVOICE----------

@app.route("/invoice/<int:invoice_id>/download")
def download_single_invoice(invoice_id):
    if session.get("role") != "user":
        return redirect("/")

    con = db()
    cur = con.cursor()

    cur.execute("""
        SELECT 
            bookings.id,
            users.name,
            cars.name,
            bookings.days,
            bookings.total,
            bookings.date,
            bookings.status,
            cars.price,
            cars.discount,
            bookings.payment_mode
        FROM bookings
        JOIN users ON bookings.user_id = users.id
        JOIN cars ON bookings.car_id = cars.id
        WHERE bookings.id = ?
          AND bookings.user_id = ?
    """, (invoice_id, session["user_id"]))

    b = cur.fetchone()
    con.close()

    # status will now be REFUNDED automatically


    # ❗ VERY IMPORTANT CHECK
    if not b:
        flash("Invoice not found", "danger")
        return redirect("/invoice_history")

    # ✅ NOW b EXISTS — SAFE TO USE
    invoice_year = b[5][:4]
    invoice_number = f"INV-{invoice_year}-{b[0]:04d}"

    # -------- CALCULATIONS --------
    price = b[7]
    discount = b[8] or 0
    discounted_price = price - (price * discount // 100)
    saved = (price - discounted_price) * b[3]
    original_amount = price * b[3]

    # -------- PDF --------
    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)

    # HEADER
    pdf.set_font("Arial", "B", 18)
    pdf.cell(0, 10, "SHAIKH'S RENTAL SERVICES", ln=True, align="C")
    pdf.set_font("Arial", size=11)
    pdf.cell(0, 6, "Reliable | Affordable | Fast", ln=True, align="C")
    pdf.ln(10)

    # META
    pdf.set_font("Arial", size=11)
    pdf.cell(100, 8, f"Invoice No: {invoice_number}")
    pdf.cell(100, 8, f"Date: {b[5][:10]}", ln=True)
    pdf.ln(6)

    # CUSTOMER
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 8, "BILLED TO", ln=True)
    pdf.set_font("Arial", size=11)
    pdf.cell(0, 7, b[1], ln=True)
    pdf.cell(0, 7, f"Payment Mode: {b[9] or '-'}", ln=True)
    pdf.cell(0, 7, f"Status: {b[6].capitalize()}", ln=True)
    pdf.ln(6)

    # TABLE (SAFE WIDTHS)
    pdf.set_font("Arial", "B", 11)
    pdf.cell(90, 10, "Particulars", 1, 0, "C")
    pdf.cell(30, 10, "Rate", 1, 0, "C")
    pdf.cell(20, 10, "Days", 1, 0, "C")
    pdf.cell(40, 10, "Amount", 1, 1, "C")

    pdf.set_font("Arial", size=11)
    pdf.cell(90, 9, b[2], 1)
    pdf.cell(30, 9, str(price), 1, 0, "C")
    pdf.cell(20, 9, str(b[3]), 1, 0, "C")
    pdf.cell(40, 9, str(original_amount), 1, 1, "C")

    pdf.cell(140, 9, f"Discount ({discount}%)", 1)
    pdf.cell(40, 9, f"- {saved}", 1, 1, "C")

    pdf.set_font("Arial", "B", 12)
    pdf.cell(140, 10, "TOTAL AMOUNT PAID", 1)
    pdf.cell(40, 10, str(b[4]), 1, 1, "C")

    # FOOTER
    pdf.ln(8)
    pdf.set_font("Arial", size=10)
    pdf.multi_cell(
        0, 6,
        "This is a system-generated invoice.\n"
        "All payments once completed are non-refundable."
    )

    file_path = f"invoice_{b[0]}.pdf"
    pdf.output(file_path)

    return send_file(file_path, as_attachment=True)





# ---------------- DELIVER/RETURN CAR ----------------
@app.route("/delivered/<int:booking_id>", methods=["POST"])
def delivered(booking_id):
    if session.get("role") != "user":
        return {"success": False}, 403

    con = db()
    cur = con.cursor()

    # Get car_id safely
    cur.execute("""
        SELECT car_id, status
        FROM bookings
        WHERE id = ? AND user_id = ?
    """, (booking_id, session["user_id"]))

    row = cur.fetchone()

    if not row:
        con.close()
        return {"success": False}

    car_id, status = row

    # Allow return only if Paid (in use)
    if status != "Paid":
        con.close()
        return {"success": False}

    # Update booking
    cur.execute("""
        UPDATE bookings
        SET status = 'Returned',
            return_date = ?
        WHERE id = ?
    """, (datetime.now(), booking_id))

    # Make car available again
    cur.execute("""
        UPDATE cars
        SET available = 1
        WHERE id = ?
    """, (car_id,))

    con.commit()
    con.close()

    return {"success": True}



# ---------------- ADMIN ----------------
@app.route("/admin")
def admin():
    if session.get("role") != "admin":
        flash("Unauthorized access", "danger")
        return redirect("/admin_login")

    con = db()
    cur = con.cursor()

    # STATS
    cur.execute("SELECT COUNT(*) FROM users")
    total_users = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM cars")
    total_cars = cur.fetchone()[0]

    cur.execute("""
        SELECT COUNT(*) FROM bookings
        WHERE status IN ('Booked','Paid')

    """)
    active_bookings = cur.fetchone()[0]

    # ✅ Revenue never reduces
    cur.execute("""
        SELECT IFNULL(SUM(amount), 0)
        FROM revenue
    """)
    total_revenue = cur.fetchone()[0]

    # RECENT BOOKINGS
    cur.execute("""
        SELECT 
            bookings.id,
            users.name,
            cars.name,
            bookings.days,
            bookings.total,
            bookings.status,
            bookings.date
        FROM bookings
        JOIN users ON bookings.user_id = users.id
        JOIN cars ON bookings.car_id = cars.id
        ORDER BY bookings.date DESC
        LIMIT 10
    """)
    recent_bookings = cur.fetchall()

    # CAR MANAGEMENT
    cur.execute("""
        SELECT id, name, price, available, image, discount
        FROM cars
        ORDER BY id ASC
    """)
    cars = cur.fetchall()

    con.close()

    return render_template(
        "admin.html",
        total_users=total_users,
        total_cars=total_cars,
        active_bookings=active_bookings,
        total_revenue=total_revenue,
        recent_bookings=recent_bookings,
        cars=cars
    )


@app.route("/admin_login", methods=["GET","POST"])
def admin_login():
    if session.get("role") == "admin":
        return redirect("/admin")

    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        con = db()
        cur = con.cursor()
        cur.execute(
            "SELECT id FROM admin WHERE username=? AND password=?",
            (username, password)
        )
        admin = cur.fetchone()
        con.close()

        if admin:
            session.clear()
            session["role"] = "admin"
            session["admin_id"] = admin[0]
            flash("Admin login successful", "success")
            return redirect("/admin")

        flash("Invalid admin credentials", "danger")

    return render_template("admin_login.html")




 # ================= REFUND/APPROVAL =================

@app.route("/admin/refunds")
def admin_refunds():
    if session.get("role") != "admin":
        return redirect("/admin_login")

    con = db()
    cur = con.cursor()

    cur.execute("""
        SELECT
            b.id,
            u.name,
            b.total,
            b.status
        FROM bookings b
        JOIN users u ON b.user_id = u.id
        WHERE b.status = 'Refunding'
          AND b.refund_status = 'pending'
          AND LOWER(COALESCE(b.payment_status, '')) IN ('paid','success','completed')
        ORDER BY b.id ASC
    """)

    refunds = cur.fetchall()
    con.close()

    return render_template("admin_refunds.html", refunds=refunds)



@app.route("/admin/refund/<int:booking_id>")
def process_refund(booking_id):
    if session.get("role") != "admin":
        return redirect("/admin_login")

    con = db()
    cur = con.cursor()

    cur.execute("""
        SELECT user_id, total, refund_status
        FROM bookings
        WHERE id = ?
    """, (booking_id,))
    booking = cur.fetchone()

    if not booking:
        con.close()
        flash("Invalid booking", "danger")
        return redirect("/admin/refunds")

    user_id, total, refund_status = booking

    if refund_status != "pending":
        con.close()
        flash("Refund already processed", "warning")
        return redirect("/admin/refunds")

    cancellation_fee = 30
    refund_amount = max(total - cancellation_fee, 0)

    # Insert refund record
    cur.execute("""
        INSERT INTO refunds (
            booking_id, user_id, amount,
            refund_date, refund_mode, status
        )
        VALUES (?, ?, ?, datetime('now'), ?, ?)
    """, (
        booking_id,
        user_id,
        refund_amount,
        "Original Payment Method",
        "success"
    ))

    # ✅ VERY IMPORTANT: update BOTH columns
    cur.execute("""
        UPDATE bookings
        SET refund_status = 'refunded',
            status = 'Refunded'
        WHERE id = ?
    """, (booking_id,))

    # Keep cancellation fee as revenue
    cur.execute("""
        UPDATE revenue
        SET amount = ?
        WHERE booking_id = ?
    """, (30, booking_id))

    con.commit()
    con.close()

    flash(f"Refund completed. ₹{refund_amount} refunded (₹30 cancellation fee applied)", "success")
    return redirect("/admin/refunds")









@app.route("/admin/refund_action/<int:booking_id>/<action>")
def refund_action(booking_id, action):
    if session.get("role") != "admin":
        return redirect("/admin_login")

    con = db()
    cur = con.cursor()

    if action == "approve":
        cur.execute("""
            UPDATE bookings
            SET refund_status = 'completed'
            WHERE id = ?
        """, (booking_id,))
    else:
        cur.execute("""
            UPDATE bookings
            SET refund_status = 'rejected'
            WHERE id = ?
        """, (booking_id,))

    con.commit()
    con.close()

    flash("Refund action updated", "success")
    return redirect("/admin/refunds")








@app.route("/__cleanup_refunds")
def cleanup_refunds():
    con = db()
    cur = con.cursor()

    cur.execute("""
        UPDATE bookings
        SET status = 'Cancelled',
            refund_status = NULL
        WHERE LOWER(COALESCE(payment_status, '')) NOT IN ('paid','success','completed')
    """)

    con.commit()
    con.close()
    return "Cleanup done"



    # ================= RECENT BOOKINGS =================
    cur.execute("""
            SELECT 
            bookings.id,
            users.name,
            cars.name,
            bookings.days,
            bookings.total,
            bookings.status,
            bookings.date
        FROM bookings
        JOIN users ON bookings.user_id = users.id
        JOIN cars ON bookings.car_id = cars.id
        ORDER BY bookings.date DESC
        LIMIT 10
    """)
    recent_bookings = cur.fetchall()

    # ================= CAR MANAGEMENT =================
    # NOTE: discount column does NOT exist yet
    # We return 0 as discount placeholder
    cur.execute("""
        SELECT 
            id,
            name,
            price,
      available,
            image,
            0 as discount
        FROM cars
        ORDER BY id DESC
    """)
    cars = cur.fetchall()

    con.close()

    return render_template(
        "admin.html",
        total_users=total_users,
        total_cars=total_cars,
        active_bookings=active_bookings,
        total_revenue=total_revenue,
        recent_bookings=recent_bookings,
        cars=cars
    )


@app.route("/admin_add_car", methods=["GET", "POST"])
def admin_add_car():
    if session.get("role") != "admin":
        return redirect("/")

    if request.method == "POST":
        name = request.form["name"]
        price = request.form["price"]
        image = request.files["image"]

        filename = "default.png"
        if image and image.filename:
            filename = secure_filename(image.filename)
            image.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))

        con = db()
        cur = con.cursor()
        cur.execute(
            "INSERT INTO cars(name,price,available,image) VALUES (?,?,1,?)",
            (name, price, filename)
        )
        con.commit()
        con.close()

        return redirect("/admin")

    return render_template("admin_add_car.html")




@app.route("/admin/invoices", methods=["GET", "POST"])
def admin_invoices():
    if session.get("role") != "admin":
        return redirect("/admin_login")

    # -------- GET --------
    if request.method == "GET":
        return render_template("admin_invoice_range.html")

    # -------- POST --------
    start = request.form["start"] + " 00:00:00"
    end = request.form["end"] + " 23:59:59"
    user_query = request.form.get("user", "").strip()

    con = db()
    cur = con.cursor()

    sql = """
        SELECT
            b.id,           -- 0 Booking ID
            u.id,           -- 1 User ID
            u.name,         -- 2 User Name
            b.days,         -- 3 Days
            b.total,        -- 4 Amount Paid
            b.payment_mode, -- 5 Payment Mode
            b.status,       -- 6 Status
            b.date          -- 7 Date
        FROM bookings b
        JOIN users u ON b.user_id = u.id
        WHERE LOWER(b.status) != 'booked'
          AND b.date BETWEEN ? AND ?
    """
    params = [start, end]

    if user_query:
        if user_query.isdigit():
            sql += " AND u.id = ?"
            params.append(int(user_query))
        else:
            sql += " AND u.name LIKE ?"
            params.append(f"%{user_query}%")

    sql += " ORDER BY b.date ASC"

    cur.execute(sql, params)
    rows = cur.fetchall()
    con.close()

    if not rows:
        return "<h3 style='text-align:center'>No invoices found</h3>"

    # -------- PDF (PORTRAIT) --------
    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)

    # ---------- HEADER WITH LOGO ----------
    # logo_path = "static/logo/company_logo.png"
    # pdf.image(logo_path, x=10, y=8, w=25)

    pdf.set_xy(0, 10)
    pdf.set_font("Arial", "B", 18)
    pdf.cell(0, 10, "SHAIKH'S RENTAL SERVICES", ln=True, align="C")

    pdf.set_font("Arial", size=11)
    pdf.cell(0, 6, "Admin Invoice Summary Report", ln=True, align="C")
    pdf.ln(10)

    # ---------- META ----------
    pdf.set_font("Arial", size=10)
    pdf.cell(0, 6, f"Report Period: {start[:10]} to {end[:10]}", ln=True)
    if user_query:
        pdf.cell(0, 6, f"Filtered User: {user_query}", ln=True)

    pdf.ln(3)
    pdf.set_font("Arial", "I", 9)
    pdf.cell(0, 6, "ADMIN COPY", ln=True, align="R")
    pdf.ln(4)

    # ---------- TABLE HEADER (PORTRAIT WIDTHS) ----------
    pdf.set_font("Arial", "B", 9)
    pdf.cell(10, 8, "ID", 1, 0, "C")
    pdf.cell(15, 8, "User", 1, 0, "C")
    pdf.cell(35, 8, "Customer Name", 1, 0, "C")
    pdf.cell(10, 8, "Days", 1, 0, "C")
    pdf.cell(22, 8, "Amount", 1, 0, "C")
    pdf.cell(22, 8, "Cancel Fee", 1, 0, "C")   # ✅ NEW
    pdf.cell(30, 8, "Payment Mode", 1, 0, "C")
    pdf.cell(20, 8, "Status", 1, 0, "C")
    pdf.cell(25, 8, "Date", 1, 1, "C")

    # ---------- TABLE BODY ----------
    pdf.set_font("Arial", size=9)
    total_sum = 0
    total_cancel_fee = 0

    for r in rows:
        status = (r[6] or "").strip().lower()
        cancel_fee = 30 if status == "refunded" else 0

        pdf.cell(10, 8, str(r[0]), 1, 0, "C")
        pdf.cell(15, 8, str(r[1]), 1, 0, "C")
        pdf.cell(35, 8, r[2][:18], 1, 0, "C")
        pdf.cell(10, 8, str(r[3]), 1, 0, "C")
        pdf.cell(22, 8, f"Rs {r[4]}", 1, 0, "C")
        pdf.cell(22, 8, f"Rs {cancel_fee}", 1, 0, "C")  # ✅ NEW
        pdf.cell(30, 8, r[5] or "-", 1, 0, "C")
        pdf.cell(20, 8, r[6].capitalize(), 1, 0, "C")
        pdf.cell(25, 8, r[7][:10], 1, 1, "C")

        total_sum += r[4]
        total_cancel_fee += cancel_fee

    # ---------- TOTAL ----------
    pdf.ln(4)
    pdf.set_font("Arial", "B", 11)
    pdf.cell(110, 10, "TOTAL AMOUNT RECEIVED", 1)
    pdf.cell(55, 10, f"Rs {total_sum}", 1, ln=True)

    pdf.cell(110, 10, "TOTAL CANCELLATION FEES", 1)
    pdf.cell(55, 10, f"Rs {total_cancel_fee}", 1, ln=True)

    # ---------- FOOTER ----------
    pdf.ln(8)
    pdf.set_font("Arial", size=9)
    pdf.multi_cell(
        0, 6,
        "This is a system-generated administrative invoice summary.\n"
        "All figures are based on recorded and completed transactions."
    )

    file_path = "admin_invoice_report.pdf"
    pdf.output(file_path)

    return send_file(file_path, as_attachment=True)





# ---------------- LOGOUT ----------------

@app.route("/logout_admin")
def logout_admin():
    if session.get("role") == "admin":
        session.clear()
        flash("Have a nice day Sir 🫶", "info")
    return redirect("/")


@app.route("/logout_user")
def logout_user():
    if session.get("role") == "user":
        session.clear()
        flash("See you soon ✨", "info")
    return redirect("/")





@app.route("/about")
def about():
    return render_template("about.html")

@app.route("/privacy")
def privacy():
    return render_template("privacy.html")

@app.route("/rules")
def rules():
    return render_template("rules.html")

@app.route("/complaints")
def complaints():
    return render_template("complaints.html")

@app.route("/reviews")
def reviews():
    return render_template("reviews.html")


@app.route("/terms")
def terms():
    return render_template("terms.html")


@app.route("/index")
def home_page():
    return render_template("index.html")


@app.route("/")
def home():
    if session.get("role") == "user":
        return redirect("/dashboard")
    if session.get("role") == "admin":
        return redirect("/admin")
    return render_template("index.html")

@app.route("/offline")
def offline():
    return render_template("offline.html")





# Add profile_pic column if it doesn't exist
def add_profile_pic_column():
    con = db()
    cur = con.cursor()
    try:
        cur.execute("ALTER TABLE users ADD COLUMN profile_pic TEXT")
        con.commit()
        print("✅ profile_pic column added successfully")
    except sqlite3.OperationalError:
        print("⚠️ profile_pic column already exists")
    finally:
        con.close()

add_profile_pic_column()  # Run it once


# ---------------- PROFILE ----------------
UPLOAD_FOLDER = os.path.join("static", "uploads")
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif"}

# Ensure upload folder exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route("/profile", methods=["GET", "POST"])
def profile():
    if "user_id" not in session:
        return redirect("/")

    con = db()
    cur = con.cursor()

    # Get current user info
    cur.execute("SELECT name, password, profile_pic FROM users WHERE id=?", (session["user_id"],))
    user = cur.fetchone()
    current_name = user[0]
    current_profile_pic = user[2] if len(user) > 2 else None

    if request.method == "POST":

        # ------------------- Update username -------------------
        new_name = request.form.get("username")
        if new_name and new_name != current_name:
            cur.execute("UPDATE users SET name=? WHERE id=?", (new_name, session["user_id"]))
            session["user_name"] = new_name  # update session

        # ------------------- Update profile picture -------------------
        pfp = request.files.get("pfp")
        if pfp and pfp.filename != "" and allowed_file(pfp.filename):
            filename = secure_filename(pfp.filename)
            save_path = os.path.join(UPLOAD_FOLDER, filename)
            pfp.save(save_path)

            # Save filename in DB
            cur.execute("UPDATE users SET profile_pic=? WHERE id=?", (filename, session["user_id"]))
            session["profile_pic"] = filename

        # ------------------- Update password -------------------
        current_pw = request.form.get("current_password")
        new_pw = request.form.get("new_password")
        confirm_pw = request.form.get("confirm_password")

        if new_pw:
            if new_pw != confirm_pw:
                flash("New passwords do not match", "danger")
                return redirect("/profile")

            # Check current password
            if not check_password_hash(user[1], current_pw):
                flash("Current password is incorrect", "danger")
                return redirect("/profile")

            hashed_pw = generate_password_hash(new_pw)
            cur.execute("UPDATE users SET password=? WHERE id=?", (hashed_pw, session["user_id"]))

        con.commit()
        con.close()
        flash("Profile updated successfully", "success")
        return redirect("/profile")

    con.close()
    return render_template("profile.html", username=current_name, profile_pic=current_profile_pic)




# ---------------- RESET ----------------

@app.route("/admin_reset", methods=["GET", "POST"])
def admin_reset():
    if session.get("role") != "admin":
        flash("Unauthorized access", "danger")
        return redirect("/")

    if request.method == "POST":
        con = db()
        cur = con.cursor()

        try:
            # ✅ Delete ALL bookings (paid stays counted only in revenue history if you track externally)
            cur.execute("DELETE FROM bookings")

            # ✅ Reset all cars to available
            cur.execute("UPDATE cars SET available = 1")

            con.commit()
            flash("✅ System reset successful!", "success")

        except Exception as e:
            con.rollback()
            flash(f"❌ Reset failed: {str(e)}", "danger")

        finally:
            con.close()

        return redirect("/admin")

    return render_template("admin_reset.html")



# ---------------- CAR EDITING/DELETEING ----------------

@app.route("/admin/edit_car/<int:car_id>", methods=["GET", "POST"])
def admin_edit_car(car_id):
    if session.get("role") != "admin":
        return redirect("/admin_login")

    con = db()
    cur = con.cursor()

    # 🔹 UPDATE CAR
    if request.method == "POST":
        name = request.form["name"]
        price = request.form["price"]

        cur.execute("""
            UPDATE cars
            SET name = ?, price = ?
            WHERE id = ?
        """, (name, price, car_id))

        con.commit()
        con.close()

        flash("Car updated successfully", "success")
        return redirect("/admin/cars")

    # 🔹 LOAD CAR FOR EDIT FORM (GET)
    cur.execute("SELECT * FROM cars WHERE id = ?", (car_id,))
    car = cur.fetchone()
    con.close()

    if not car:
        flash("Car not found", "danger")
        return redirect("/admin/cars")

    return render_template("admin_edit_car.html", car=car)






@app.route("/admin/update_price/<int:car_id>", methods=["POST"])
def update_price(car_id):
    new_price = request.form["price"]

    con = db()
    cur = con.cursor()
    cur.execute("""
        UPDATE cars SET price = ?
        WHERE id = ?
    """, (new_price, car_id))
    con.commit()
    con.close()


@app.route("/car/management")
def admin_cars():
    if session.get("role") != "admin":
        return redirect("/admin_login")

    con = db()
    cur = con.cursor()

    cur.execute("""
        SELECT id, name, price, available, image, discount
        FROM cars
        ORDER BY id ASC
    """)
    cars = cur.fetchall()
    con.close()

    return render_template("car_management.html", cars=cars)


# ---------------- DISCOUNT ----------------

@app.route("/admin/discount/<int:car_id>", methods=["POST"])
def admin_set_discount(car_id):
    if session.get("role") != "admin":
        return redirect("/admin_login")

    discount = int(request.form["discount"])

    if discount < 0 or discount > 90:
        flash("Discount must be between 0 and 90%", "warning")
        return redirect("/admin")

    con = db()
    cur = con.cursor()
    cur.execute("""
        UPDATE cars
        SET discount=?
        WHERE id=?
    """, (discount, car_id))
    con.commit()
    con.close()

    flash("Discount updated", "success")
    return redirect("/admin")


@app.route("/admin/delete_car/<int:car_id>")
def admin_delete_car(car_id):
    if session.get("role") != "admin":
        return redirect("/admin_login")

    con = db()
    cur = con.cursor()

    # ❌ Prevent delete if booked
    cur.execute("""
        SELECT COUNT(*)
        FROM bookings
        WHERE car_id=? AND status IN ('Booked','Paid')
    """, (car_id,))
    active = cur.fetchone()[0]

    if active > 0:
        con.close()
        flash("Car cannot be deleted while booked", "warning")
        return redirect("/admin")

    cur.execute("DELETE FROM cars WHERE id=?", (car_id,))
    con.commit()
    con.close()

    flash("Car deleted successfully", "success")
    return redirect("/admin")



# ---------------- TEMP ----------------


# ---------------- RUN ----------------
if __name__ == "__main__":
    init_db()
    app.run(debug=True)