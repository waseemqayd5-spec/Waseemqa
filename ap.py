"""
نظام سوبر ماركت متكامل - جميع الوظائف في ملف واحد
يدعم SQLite (تطوير) و PostgreSQL (إنتاج)
"""

# =============================== الاستيرادات ===============================
from flask import Flask, request, jsonify, render_template_string, session, redirect, url_for
import os
import datetime
import psycopg2
from psycopg2.extras import RealDictCursor
import sqlite3
import hashlib
import secrets
from functools import wraps

# =============================== التهيئة ===============================
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', secrets.token_hex(32))

DATABASE_URL = os.environ.get('DATABASE_URL', None)


def get_db_connection():
    """اتصال بقاعدة البيانات حسب البيئة"""
    if DATABASE_URL:
        conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
    else:
        if not os.path.exists('data'):
            os.makedirs('data')
        conn = sqlite3.connect('data/supermarket.db')
        conn.row_factory = sqlite3.Row
    return conn


def execute_query(query, params=None, fetch_one=False, fetch_all=False, commit=False):
    """تنفيذ استعلام مع التعامل مع الفروقات بين SQLite و PostgreSQL"""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        if params is None:
            params = ()
        cur.execute(query, params)
        if commit:
            conn.commit()
        if fetch_one:
            return cur.fetchone()
        elif fetch_all:
            return cur.fetchall()
        else:
            return None
    finally:
        cur.close()
        conn.close()


# =============================== دالة مساعدة لتشفير كلمة المرور ===============================
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()


def verify_password(password, hashed):
    return hash_password(password) == hashed


# =============================== دالة التحقق من تسجيل الدخول ===============================
def login_required(role=None):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                return redirect(url_for('login_page'))
            if role:
                if session.get('role') != role:
                    return "غير مصرح: هذه الصفحة تتطلب صلاحية " + role, 403
            return f(*args, **kwargs)
        return decorated_function
    return decorator


# =============================== إنشاء الجداول والبيانات الافتراضية ===============================
def init_db():
    """إنشاء جميع الجداول وإضافة بيانات افتراضية"""
    conn = get_db_connection()
    cur = conn.cursor()

    if DATABASE_URL:
        # PostgreSQL
        # جدول المستخدمين
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                username VARCHAR(50) UNIQUE NOT NULL,
                password_hash VARCHAR(200) NOT NULL,
                full_name VARCHAR(100),
                role VARCHAR(20) DEFAULT 'cashier',
                is_active INTEGER DEFAULT 1,
                last_login TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # جدول العملاء
        cur.execute("""
            CREATE TABLE IF NOT EXISTS customers (
                id SERIAL PRIMARY KEY,
                phone VARCHAR(20) UNIQUE,
                name VARCHAR(100),
                loyalty_points INTEGER DEFAULT 0,
                total_spent REAL DEFAULT 0,
                visits INTEGER DEFAULT 0,
                last_visit VARCHAR(10),
                customer_tier VARCHAR(20) DEFAULT 'عادي',
                is_active INTEGER DEFAULT 1
            )
        """)

        # جدول المنتجات
        cur.execute("""
            CREATE TABLE IF NOT EXISTS products (
                id SERIAL PRIMARY KEY,
                barcode VARCHAR(50) UNIQUE,
                name VARCHAR(200) NOT NULL,
                category VARCHAR(50),
                price REAL NOT NULL,
                cost_price REAL,
                quantity INTEGER DEFAULT 0,
                min_quantity INTEGER DEFAULT 10,
                unit VARCHAR(20) DEFAULT 'قطعة',
                supplier VARCHAR(100),
                expiry_date VARCHAR(10),
                added_date VARCHAR(10),
                last_updated VARCHAR(10),
                is_active INTEGER DEFAULT 1
            )
        """)

        # جدول سجل المخزون
        cur.execute("""
            CREATE TABLE IF NOT EXISTS inventory_logs (
                id SERIAL PRIMARY KEY,
                product_id INTEGER,
                product_name TEXT,
                change_type TEXT,
                quantity_change INTEGER,
                old_quantity INTEGER,
                new_quantity INTEGER,
                notes TEXT,
                user TEXT,
                timestamp TEXT,
                FOREIGN KEY (product_id) REFERENCES products (id)
            )
        """)

        # جدول المبيعات
        cur.execute("""
            CREATE TABLE IF NOT EXISTS sales (
                id SERIAL PRIMARY KEY,
                invoice_number VARCHAR(20) UNIQUE NOT NULL,
                customer_id INTEGER REFERENCES customers(id) ON DELETE SET NULL,
                user_id INTEGER REFERENCES users(id),
                sale_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                subtotal REAL NOT NULL,
                discount REAL DEFAULT 0,
                tax REAL DEFAULT 0,
                total REAL NOT NULL,
                payment_method VARCHAR(20),
                paid_amount REAL,
                change_amount REAL,
                notes TEXT,
                status VARCHAR(20) DEFAULT 'completed'
            )
        """)

        # جدول تفاصيل المبيعات
        cur.execute("""
            CREATE TABLE IF NOT EXISTS sale_items (
                id SERIAL PRIMARY KEY,
                sale_id INTEGER REFERENCES sales(id) ON DELETE CASCADE,
                product_id INTEGER REFERENCES products(id),
                quantity INTEGER NOT NULL,
                unit_price REAL NOT NULL,
                total_price REAL NOT NULL
            )
        """)

        # جدول المشتريات
        cur.execute("""
            CREATE TABLE IF NOT EXISTS purchases (
                id SERIAL PRIMARY KEY,
                invoice_number VARCHAR(20) UNIQUE NOT NULL,
                supplier VARCHAR(100),
                user_id INTEGER REFERENCES users(id),
                purchase_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                subtotal REAL NOT NULL,
                discount REAL DEFAULT 0,
                total REAL NOT NULL,
                payment_status VARCHAR(20) DEFAULT 'pending',
                notes TEXT
            )
        """)

        # جدول تفاصيل المشتريات
        cur.execute("""
            CREATE TABLE IF NOT EXISTS purchase_items (
                id SERIAL PRIMARY KEY,
                purchase_id INTEGER REFERENCES purchases(id) ON DELETE CASCADE,
                product_id INTEGER REFERENCES products(id),
                quantity INTEGER NOT NULL,
                unit_cost REAL NOT NULL,
                total_cost REAL NOT NULL,
                expiry_date DATE
            )
        """)

        # جدول المصروفات
        cur.execute("""
            CREATE TABLE IF NOT EXISTS expenses (
                id SERIAL PRIMARY KEY,
                expense_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                category VARCHAR(50),
                amount REAL NOT NULL,
                description TEXT,
                user_id INTEGER REFERENCES users(id),
                receipt_image TEXT
            )
        """)

        # جدول الإعدادات
        cur.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key VARCHAR(50) PRIMARY KEY,
                value TEXT,
                description TEXT
            )
        """)

        # جدول العروض
        cur.execute("""
            CREATE TABLE IF NOT EXISTS offers (
                id SERIAL PRIMARY KEY,
                title VARCHAR(100),
                description TEXT,
                code VARCHAR(50) UNIQUE,
                discount_type VARCHAR(20), -- percentage, fixed
                discount_value REAL,
                min_purchase REAL DEFAULT 0,
                start_date DATE,
                end_date DATE,
                is_active INTEGER DEFAULT 1
            )
        """)

        # إضافة مستخدم افتراضي إذا لم يكن موجوداً
        cur.execute("SELECT COUNT(*) FROM users")
        if cur.fetchone()[0] == 0:
            admin_pass = hash_password('admin123')
            cur.execute("""
                INSERT INTO users (username, password_hash, full_name, role)
                VALUES (%s, %s, %s, %s)
            """, ('admin', admin_pass, 'مدير النظام', 'admin'))

        # إضافة عملاء افتراضيين
        cur.execute("SELECT COUNT(*) FROM customers")
        if cur.fetchone()[0] == 0:
            cur.execute("""
                INSERT INTO customers (phone, name, loyalty_points, total_spent, visits, last_visit)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, ('0500000000', 'عميل تجريبي', 50, 200.0, 5, datetime.date.today().isoformat()))

        # إضافة منتجات افتراضية
        cur.execute("SELECT COUNT(*) FROM products")
        if cur.fetchone()[0] == 0:
            today = datetime.date.today()
            future_date = today + datetime.timedelta(days=180)
            default_products = [
                ("8801234567890", "أرز بسمتي", "مواد غذائية", 25.0, 18.0, 50, 10, "كيلو", "مورد الأرز", future_date.isoformat()),
                ("8809876543210", "سكر", "مواد غذائية", 15.0, 11.0, 100, 20, "كيلو", "مورد السكر", future_date.isoformat()),
                ("8801122334455", "زيت دوار الشمس", "مواد غذائية", 35.0, 28.0, 30, 10, "لتر", "مورد الزيوت", future_date.isoformat()),
                ("8805566778899", "حليب طازج", "مبردات", 8.0, 6.0, 40, 15, "لتر", "شركة الألبان", (today + datetime.timedelta(days=14)).isoformat()),
                ("8809988776655", "شاي", "مواد غذائية", 20.0, 15.0, 60, 15, "علبة", "مورد الشاي", future_date.isoformat()),
            ]
            for prod in default_products:
                cur.execute("""
                    INSERT INTO products (barcode, name, category, price, cost_price, quantity, min_quantity,
                                          unit, supplier, expiry_date, added_date, last_updated)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (*prod, today.isoformat(), today.isoformat()))

        # إضافة عروض افتراضية
        cur.execute("SELECT COUNT(*) FROM offers")
        if cur.fetchone()[0] == 0:
            cur.execute("""
                INSERT INTO offers (title, description, code, discount_type, discount_value)
                VALUES (%s, %s, %s, %s, %s)
            """, ('خصم 10%', 'خصم 10% على جميع المنتجات', 'DISCOUNT10', 'percentage', 10))

    else:
        # SQLite (نفس الهيكل مع ? بدلاً من %s)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                full_name TEXT,
                role TEXT DEFAULT 'cashier',
                is_active INTEGER DEFAULT 1,
                last_login TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS customers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                phone TEXT UNIQUE,
                name TEXT,
                loyalty_points INTEGER DEFAULT 0,
                total_spent REAL DEFAULT 0,
                visits INTEGER DEFAULT 0,
                last_visit TEXT,
                customer_tier TEXT DEFAULT 'عادي',
                is_active INTEGER DEFAULT 1
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                barcode TEXT UNIQUE,
                name TEXT NOT NULL,
                category TEXT,
                price REAL NOT NULL,
                cost_price REAL,
                quantity INTEGER DEFAULT 0,
                min_quantity INTEGER DEFAULT 10,
                unit TEXT DEFAULT 'قطعة',
                supplier TEXT,
                expiry_date TEXT,
                added_date TEXT,
                last_updated TEXT,
                is_active INTEGER DEFAULT 1
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS inventory_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id INTEGER,
                product_name TEXT,
                change_type TEXT,
                quantity_change INTEGER,
                old_quantity INTEGER,
                new_quantity INTEGER,
                notes TEXT,
                user TEXT,
                timestamp TEXT,
                FOREIGN KEY (product_id) REFERENCES products (id)
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS sales (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                invoice_number TEXT UNIQUE NOT NULL,
                customer_id INTEGER,
                user_id INTEGER,
                sale_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                subtotal REAL NOT NULL,
                discount REAL DEFAULT 0,
                tax REAL DEFAULT 0,
                total REAL NOT NULL,
                payment_method TEXT,
                paid_amount REAL,
                change_amount REAL,
                notes TEXT,
                status TEXT DEFAULT 'completed',
                FOREIGN KEY (customer_id) REFERENCES customers(id),
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS sale_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sale_id INTEGER NOT NULL,
                product_id INTEGER NOT NULL,
                quantity INTEGER NOT NULL,
                unit_price REAL NOT NULL,
                total_price REAL NOT NULL,
                FOREIGN KEY (sale_id) REFERENCES sales(id) ON DELETE CASCADE,
                FOREIGN KEY (product_id) REFERENCES products(id)
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS purchases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                invoice_number TEXT UNIQUE NOT NULL,
                supplier TEXT,
                user_id INTEGER,
                purchase_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                subtotal REAL NOT NULL,
                discount REAL DEFAULT 0,
                total REAL NOT NULL,
                payment_status TEXT DEFAULT 'pending',
                notes TEXT,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS purchase_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                purchase_id INTEGER NOT NULL,
                product_id INTEGER NOT NULL,
                quantity INTEGER NOT NULL,
                unit_cost REAL NOT NULL,
                total_cost REAL NOT NULL,
                expiry_date DATE,
                FOREIGN KEY (purchase_id) REFERENCES purchases(id) ON DELETE CASCADE,
                FOREIGN KEY (product_id) REFERENCES products(id)
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS expenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                expense_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                category TEXT,
                amount REAL NOT NULL,
                description TEXT,
                user_id INTEGER,
                receipt_image TEXT,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT,
                description TEXT
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS offers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT,
                description TEXT,
                code TEXT UNIQUE,
                discount_type TEXT,
                discount_value REAL,
                min_purchase REAL DEFAULT 0,
                start_date DATE,
                end_date DATE,
                is_active INTEGER DEFAULT 1
            )
        """)

        cur.execute("SELECT COUNT(*) FROM users")
        if cur.fetchone()[0] == 0:
            admin_pass = hash_password('admin123')
            cur.execute("""
                INSERT INTO users (username, password_hash, full_name, role)
                VALUES (?, ?, ?, ?)
            """, ('admin', admin_pass, 'مدير النظام', 'admin'))

        cur.execute("SELECT COUNT(*) FROM customers")
        if cur.fetchone()[0] == 0:
            cur.execute("""
                INSERT INTO customers (phone, name, loyalty_points, total_spent, visits, last_visit)
                VALUES (?, ?, ?, ?, ?, ?)
            """, ('0500000000', 'عميل تجريبي', 50, 200.0, 5, datetime.date.today().isoformat()))

        cur.execute("SELECT COUNT(*) FROM products")
        if cur.fetchone()[0] == 0:
            today = datetime.date.today()
            future_date = today + datetime.timedelta(days=180)
            default_products = [
                ("8801234567890", "أرز بسمتي", "مواد غذائية", 25.0, 18.0, 50, 10, "كيلو", "مورد الأرز", future_date.isoformat()),
                ("8809876543210", "سكر", "مواد غذائية", 15.0, 11.0, 100, 20, "كيلو", "مورد السكر", future_date.isoformat()),
                ("8801122334455", "زيت دوار الشمس", "مواد غذائية", 35.0, 28.0, 30, 10, "لتر", "مورد الزيوت", future_date.isoformat()),
                ("8805566778899", "حليب طازج", "مبردات", 8.0, 6.0, 40, 15, "لتر", "شركة الألبان", (today + datetime.timedelta(days=14)).isoformat()),
                ("8809988776655", "شاي", "مواد غذائية", 20.0, 15.0, 60, 15, "علبة", "مورد الشاي", future_date.isoformat()),
            ]
            for prod in default_products:
                cur.execute("""
                    INSERT INTO products (barcode, name, category, price, cost_price, quantity, min_quantity,
                                          unit, supplier, expiry_date, added_date, last_updated)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (*prod, today.isoformat(), today.isoformat()))

        cur.execute("SELECT COUNT(*) FROM offers")
        if cur.fetchone()[0] == 0:
            cur.execute("""
                INSERT INTO offers (title, description, code, discount_type, discount_value)
                VALUES (?, ?, ?, ?, ?)
            """, ('خصم 10%', 'خصم 10% على جميع المنتجات', 'DISCOUNT10', 'percentage', 10))

    conn.commit()
    conn.close()


# تهيئة قاعدة البيانات
init_db()


# =============================== صفحات تسجيل الدخول ===============================
@app.route('/login', methods=['GET', 'POST'])
def login_page():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        conn = get_db_connection()
        cur = conn.cursor()
        if DATABASE_URL:
            cur.execute("SELECT id, username, password_hash, role FROM users WHERE username = %s AND is_active = 1", (username,))
        else:
            cur.execute("SELECT id, username, password_hash, role FROM users WHERE username = ? AND is_active = 1", (username,))
        user = cur.fetchone()
        cur.close()
        conn.close()
        if user and verify_password(password, user[2]):
            session['user_id'] = user[0]
            session['username'] = user[1]
            session['role'] = user[3]
            return redirect(url_for('admin_dashboard'))
        else:
            return '''
            <!DOCTYPE html>
            <html dir="rtl">
            <head><meta charset="UTF-8"><title>تسجيل دخول</title>
            <style>body{background:#f5f5f5;display:flex;justify-content:center;align-items:center;height:100vh;font-family:Arial;}.box{background:white;padding:40px;border-radius:10px;box-shadow:0 5px 15px rgba(0,0,0,0.1);width:300px;}input{width:100%;padding:12px;margin:10px 0;border:2px solid #ddd;border-radius:8px;}button{width:100%;padding:12px;background:#3498db;color:white;border:none;border-radius:8px;cursor:pointer;}</style>
            </head>
            <body>
                <div class="box">
                    <h2 style="text-align:center;">🔐 تسجيل الدخول</h2>
                    <p style="color:red;">اسم مستخدم أو كلمة مرور خاطئة</p>
                    <form method="post">
                        <input type="text" name="username" placeholder="اسم المستخدم" required>
                        <input type="password" name="password" placeholder="كلمة المرور" required>
                        <button type="submit">دخول</button>
                    </form>
                </div>
            </body>
            </html>
            '''
    return '''
    <!DOCTYPE html>
    <html dir="rtl">
    <head><meta charset="UTF-8"><title>تسجيل دخول</title>
    <style>body{background:#f5f5f5;display:flex;justify-content:center;align-items:center;height:100vh;font-family:Arial;}.box{background:white;padding:40px;border-radius:10px;box-shadow:0 5px 15px rgba(0,0,0,0.1);width:300px;}input{width:100%;padding:12px;margin:10px 0;border:2px solid #ddd;border-radius:8px;}button{width:100%;padding:12px;background:#3498db;color:white;border:none;border-radius:8px;cursor:pointer;}</style>
    </head>
    <body>
        <div class="box">
            <h2 style="text-align:center;">🔐 تسجيل الدخول</h2>
            <form method="post">
                <input type="text" name="username" placeholder="اسم المستخدم" required>
                <input type="password" name="password" placeholder="كلمة المرور" required>
                <button type="submit">دخول</button>
            </form>
        </div>
    </body>
    </html>
    '''


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login_page'))


# =============================== الصفحة الرئيسية للعملاء (بدون تسجيل دخول) ===============================
@app.route('/')
def home():
    return render_template_string('''
    <!DOCTYPE html>
    <html dir="rtl" lang="ar">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>نظام نقاط العملاء - سوبر ماركت اولاد قايد محمد</title>
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; font-family: 'Segoe UI', Tahoma, Arial, sans-serif; }
            body { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); min-height: 100vh; padding: 20px; }
            .container { max-width: 1400px; margin: 0 auto; display: grid; grid-template-columns: 1fr 350px; gap: 20px; }
            @media (max-width: 768px) { .container { grid-template-columns: 1fr; } }
            .main-content { background: rgba(255,255,255,0.1); border-radius: 20px; padding: 20px; backdrop-filter: blur(10px); }
            .cart-sidebar { background: white; border-radius: 20px; padding: 20px; box-shadow: 0 10px 30px rgba(0,0,0,0.2); height: fit-content; position: sticky; top: 20px; }
            h1 { color: white; text-align: center; margin-bottom: 20px; font-size: 2em; text-shadow: 2px 2px 4px rgba(0,0,0,0.3); }
            .nav { display: flex; gap: 10px; margin-bottom: 25px; flex-wrap: wrap; }
            .nav button { flex: 1; padding: 15px; background: rgba(255,255,255,0.2); color: white; border: none; border-radius: 12px; cursor: pointer; font-size: 18px; font-weight: bold; transition: 0.3s; min-width: 120px; }
            .nav button.active { background: #4CAF50; box-shadow: 0 5px 15px rgba(76,175,80,0.4); }
            .nav button:hover { transform: translateY(-2px); }
            .section { display: none; }
            .section.active { display: block; }
            .filters { display: flex; gap: 15px; margin-bottom: 25px; flex-wrap: wrap; }
            .filters select, .filters input { flex: 1; padding: 15px; border: none; border-radius: 12px; font-size: 16px; background: white; box-shadow: 0 3px 10px rgba(0,0,0,0.1); }
            .products-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 20px; }
            .product-card { background: white; border-radius: 15px; padding: 20px; text-align: center; box-shadow: 0 5px 15px rgba(0,0,0,0.1); transition: 0.3s; }
            .product-card:hover { transform: translateY(-5px); box-shadow: 0 10px 25px rgba(0,0,0,0.2); }
            .product-icon { font-size: 50px; margin-bottom: 10px; }
            .product-name { font-weight: bold; font-size: 18px; color: #333; margin-bottom: 5px; }
            .product-price { color: #e74c3c; font-size: 22px; font-weight: bold; margin: 10px 0; }
            .product-stock { color: #27ae60; font-size: 14px; margin-bottom: 15px; }
            .add-to-cart-btn { background: #3498db; color: white; border: none; padding: 12px; border-radius: 8px; width: 100%; font-size: 16px; cursor: pointer; transition: 0.3s; display: flex; align-items: center; justify-content: center; gap: 5px; }
            .add-to-cart-btn:hover { background: #2980b9; }
            .cart-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; padding-bottom: 15px; border-bottom: 2px solid #eee; }
            .cart-header h3 { color: #2c3e50; }
            .cart-items { max-height: 400px; overflow-y: auto; margin-bottom: 20px; }
            .cart-item { display: flex; justify-content: space-between; align-items: center; padding: 10px; background: #f8f9fa; border-radius: 8px; margin-bottom: 10px; }
            .cart-item-info { flex: 1; }
            .cart-item-name { font-weight: bold; color: #2c3e50; }
            .cart-item-price { color: #e74c3c; font-size: 14px; }
            .cart-item-actions { display: flex; gap: 5px; }
            .cart-item-actions button { background: none; border: none; cursor: pointer; font-size: 18px; padding: 5px; }
            .cart-total { background: #2c3e50; color: white; padding: 15px; border-radius: 10px; text-align: center; font-size: 20px; font-weight: bold; margin-top: 20px; }
            .whatsapp-btn { background: #25D366; color: white; border: none; padding: 15px; border-radius: 10px; width: 100%; font-size: 18px; font-weight: bold; cursor: pointer; margin-top: 15px; display: flex; align-items: center; justify-content: center; gap: 10px; transition: 0.3s; }
            .whatsapp-btn:hover { background: #128C7E; }
            .clear-cart-btn { background: #e74c3c; color: white; border: none; padding: 10px; border-radius: 5px; cursor: pointer; font-size: 14px; }
            .offer-card { background: white; border-radius: 15px; padding: 20px; margin-bottom: 15px; text-align: center; }
            .offer-code { background: #f1c40f; color: #2c3e50; padding: 5px 10px; border-radius: 5px; display: inline-block; margin-top: 10px; font-weight: bold; }
        </style>
    </head>
    <body>
        <h1>🛒 سوبر ماركت اولاد قايد محمد</h1>
        <p style="color:white; text-align:center;">إعداد وتصميم  《 م/وسيم الحميدي 》</p>
        <div class="container">
            <!-- القسم الرئيسي -->
            <div class="main-content">
                <div class="nav">
                    <button class="active" onclick="showSection('points')">⭐ نقاطي</button>
                    <button onclick="showSection('products')">📦 المنتجات</button>
                    <button onclick="showSection('offers')">🎁 العروض</button>
                </div>

                <!-- قسم النقاط -->
                <div id="points-section" class="section active">
                    <div style="background: white; border-radius: 15px; padding: 25px;">
                        <input type="tel" id="phone" placeholder="📱 أدخل رقم الهاتف" style="width:100%; padding:15px; border:2px solid #ddd; border-radius:10px; margin-bottom:15px;">
                        <button onclick="checkPoints()" style="background:#4CAF50; color:white; border:none; padding:15px; width:100%; border-radius:10px; font-size:18px;">🔍 استعلام عن النقاط</button>
                        <div id="points-result" style="margin-top:20px;"></div>
                    </div>
                </div>

                <!-- قسم المنتجات -->
                <div id="products-section" class="section">
                    <div class="filters">
                        <select id="category-filter" onchange="loadProducts()">
                            <option value="">جميع الفئات</option>
                            <option value="مواد غذائية">مواد غذائية</option>
                            <option value="مبردات">مبردات</option>
                            <option value="معلبات">معلبات</option>
                            <option value="منظفات">منظفات</option>
                        </select>
                        <input type="text" id="search-product" placeholder="🔍 ابحث عن منتج..." onkeyup="loadProducts()">
                    </div>
                    <div id="products-result" class="products-grid"></div>
                </div>

                <!-- قسم العروض -->
                <div id="offers-section" class="section">
                    <div id="offers-result"></div>
                </div>
            </div>

            <!-- سلة التسوق -->
            <div class="cart-sidebar">
                <div class="cart-header">
                    <h3>🛒 سلة المشتريات</h3>
                    <button class="clear-cart-btn" onclick="clearCart()">تفريغ السلة</button>
                </div>
                <div id="cart-items" class="cart-items">
                    <p style="text-align:center; color:#7f8c8d;">السلة فارغة</p>
                </div>
                <div id="cart-total" class="cart-total">الإجمالي: 0 ريال</div>
                <button class="whatsapp-btn" onclick="sendWhatsApp()">
                    <img src="https://img.icons8.com/color/24/000000/whatsapp--v1.png" style="vertical-align:middle;"> إرسال الطلب عبر واتساب
                </button>
            </div>
        </div>

        <script>
            // متغيرات السلة
            let cart = [];

            // تبديل الأقسام
            function showSection(sectionId) {
                document.querySelectorAll('.nav button').forEach(btn => btn.classList.remove('active'));
                event.target.classList.add('active');
                document.querySelectorAll('.section').forEach(sec => sec.classList.remove('active'));
                document.getElementById(sectionId + '-section').classList.add('active');
                if (sectionId === 'products') loadProducts();
                if (sectionId === 'offers') loadOffers();
            }

            // دالة عرض النقاط
            function checkPoints() {
                const phone = document.getElementById('phone').value;
                const resultDiv = document.getElementById('points-result');
                if (!phone) {
                    resultDiv.innerHTML = '<div style="background:#ffebee; color:#c62828; padding:15px; border-radius:10px;">⚠ يرجى إدخال رقم الهاتف</div>';
                    return;
                }
                resultDiv.innerHTML = '<p>جاري البحث...</p>';
                fetch('/check_points', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({phone: phone})
                })
                .then(r => r.json())
                .then(data => {
                    if (data.success) {
                        const c = data.customer;
                        resultDiv.innerHTML = `
                            <div style="background:#e8f5e9; color:#2e7d32; padding:20px; border-radius:10px;">
                                <h3>👤 ${c.name}</h3>
                                <h1 style="font-size:48px;">${c.points} ⭐</h1>
                                <p>💰 الإنفاق: ${c.total_spent} ريال</p>
                                <p>🛒 الزيارات: ${c.visits}</p>
                                <p>📅 آخر زيارة: ${c.last_visit}</p>
                                <p>🏆 المستوى: ${c.tier}</p>
                            </div>
                        `;
                    } else {
                        resultDiv.innerHTML = `<div style="background:#ffebee; color:#c62828; padding:15px; border-radius:10px;">❌ ${data.message}</div>`;
                    }
                });
            }

            // تحميل المنتجات مع أزرار الإضافة
            function loadProducts() {
                const category = document.getElementById('category-filter').value;
                const search = document.getElementById('search-product').value;
                const resultDiv = document.getElementById('products-result');
                resultDiv.innerHTML = '<p style="color:white;">جاري تحميل المنتجات...</p>';
                fetch(`/products?category=${encodeURIComponent(category)}&search=${encodeURIComponent(search)}`)
                    .then(r => r.json())
                    .then(data => {
                        if (data.success) {
                            let html = '';
                            data.products.forEach(product => {
                                html += `
                                    <div class="product-card">
                                        <div class="product-icon">📦</div>
                                        <div class="product-name">${product.name}</div>
                                        <div class="product-price">${product.price} ريال</div>
                                        <div class="product-stock">${product.quantity} ${product.unit}</div>
                                        <button class="add-to-cart-btn" onclick="addToCart(${product.id}, '${product.name}', ${product.price})">
                                            ➕ أضف إلى السلة
                                        </button>
                                    </div>
                                `;
                            });
                            resultDiv.innerHTML = html || '<p style="color:white;">لا توجد منتجات</p>';
                        } else {
                            resultDiv.innerHTML = `<p style="color:white;">❌ ${data.message}</p>`;
                        }
                    });
            }

            // تحميل العروض
            function loadOffers() {
                fetch('/offers')
                    .then(r => r.json())
                    .then(data => {
                        let html = '';
                        data.offers.forEach(offer => {
                            html += `
                                <div class="offer-card">
                                    <h3>${offer.title}</h3>
                                    <p>${offer.description}</p>
                                    <div class="offer-code">🏷️ كود: ${offer.code}</div>
                                </div>
                            `;
                        });
                        document.getElementById('offers-result').innerHTML = html;
                    });
            }

            // دوال السلة
            function addToCart(id, name, price) {
                const existing = cart.find(item => item.id === id);
                if (existing) {
                    existing.quantity++;
                } else {
                    cart.push({ id, name, price, quantity: 1 });
                }
                updateCartDisplay();
                saveCart();
            }

            function removeFromCart(id) {
                cart = cart.filter(item => item.id !== id);
                updateCartDisplay();
                saveCart();
            }

            function updateCartDisplay() {
                const cartDiv = document.getElementById('cart-items');
                const totalDiv = document.getElementById('cart-total');
                if (cart.length === 0) {
                    cartDiv.innerHTML = '<p style="text-align:center; color:#7f8c8d;">السلة فارغة</p>';
                    totalDiv.innerText = 'الإجمالي: 0 ريال';
                    return;
                }
                let html = '';
                let total = 0;
                cart.forEach(item => {
                    const itemTotal = item.price * item.quantity;
                    total += itemTotal;
                    html += `
                        <div class="cart-item">
                            <div class="cart-item-info">
                                <div class="cart-item-name">${item.name}</div>
                                <div class="cart-item-price">${item.price} ريال × ${item.quantity} = ${itemTotal} ريال</div>
                            </div>
                            <div class="cart-item-actions">
                                <button onclick="removeFromCart(${item.id})">🗑️</button>
                            </div>
                        </div>
                    `;
                });
                cartDiv.innerHTML = html;
                totalDiv.innerText = `الإجمالي: ${total} ريال`;
            }

            function clearCart() {
                cart = [];
                updateCartDisplay();
                saveCart();
            }

            function saveCart() {
                localStorage.setItem('cart', JSON.stringify(cart));
            }

            function loadCart() {
                const saved = localStorage.getItem('cart');
                if (saved) {
                    cart = JSON.parse(saved);
                    updateCartDisplay();
                }
            }

            function sendWhatsApp() {
                if (cart.length === 0) {
                    alert('السلة فارغة، أضف منتجات أولاً');
                    return;
                }
                let message = '*طلب جديد من سوبر ماركت اولاد قايد محمد*%0A';
                let total = 0;
                cart.forEach(item => {
                    const itemTotal = item.price * item.quantity;
                    message += `- ${item.name} (${item.price} ريال) × ${item.quantity} = ${itemTotal} ريال%0A`;
                    total += itemTotal;
                });
                message += `%0A*الإجمالي: ${total} ريال*`;
                window.open(`https://wa.me/967770295876?text=${message}`, '_blank');
            }

            // التحميل الأولي
            window.onload = function() {
                loadCart();
                loadProducts();
                loadOffers();
            };
        </script>
    </body>
    </html>
    ''')


# =============================== واجهات API للعملاء ===============================
@app.route('/check_points', methods=['POST'])
def check_points():
    try:
        phone = request.json.get('phone')
        if not phone:
            return jsonify({"success": False, "message": "رقم الهاتف مطلوب"})
        conn = get_db_connection()
        cur = conn.cursor()
        if DATABASE_URL:
            cur.execute("""
                SELECT name, loyalty_points, total_spent, visits, last_visit, customer_tier
                FROM customers WHERE phone = %s AND is_active = 1
            """, (phone,))
        else:
            cur.execute("""
                SELECT name, loyalty_points, total_spent, visits, last_visit, customer_tier
                FROM customers WHERE phone = ? AND is_active = 1
            """, (phone,))
        customer = cur.fetchone()
        cur.close()
        conn.close()
        if customer:
            return jsonify({
                "success": True,
                "customer": {
                    "name": customer[0],
                    "points": customer[1],
                    "total_spent": customer[2],
                    "visits": customer[3],
                    "last_visit": customer[4],
                    "tier": customer[5]
                }
            })
        else:
            return jsonify({"success": False, "message": "رقم الهاتف غير مسجل"})
    except Exception as e:
        return jsonify({"success": False, "message": f"خطأ: {str(e)}"})


@app.route('/products')
def get_products():
    try:
        category = request.args.get('category', '')
        search = request.args.get('search', '')
        conn = get_db_connection()
        cur = conn.cursor()
        if DATABASE_URL:
            query = "SELECT id, name, price, quantity, unit, category FROM products WHERE is_active = 1"
            params = []
            if category:
                query += " AND category = %s"
                params.append(category)
            if search:
                query += " AND (name ILIKE %s OR barcode ILIKE %s)"
                params.append(f'%{search}%')
                params.append(f'%{search}%')
            query += " ORDER BY name"
            cur.execute(query, params)
        else:
            query = "SELECT id, name, price, quantity, unit, category FROM products WHERE is_active = 1"
            params = []
            if category:
                query += " AND category = ?"
                params.append(category)
            if search:
                query += " AND (name LIKE ? OR barcode LIKE ?)"
                params.append(f'%{search}%')
                params.append(f'%{search}%')
            query += " ORDER BY name"
            cur.execute(query, params)
        products = cur.fetchall()
        cur.close()
        conn.close()
        products_list = []
        for product in products:
            products_list.append({
                "id": product[0],
                "name": product[1],
                "price": product[2],
                "quantity": product[3],
                "unit": product[4],
                "category": product[5]
            })
        return jsonify({"success": True, "count": len(products_list), "products": products_list})
    except Exception as e:
        return jsonify({"success": False, "message": f"خطأ: {str(e)}"})


@app.route('/offers')
def get_offers():
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        today = datetime.date.today().isoformat()
        if DATABASE_URL:
            cur.execute("""
                SELECT title, description, code FROM offers
                WHERE is_active = 1 AND (start_date IS NULL OR start_date <= %s)
                AND (end_date IS NULL OR end_date >= %s)
            """, (today, today))
        else:
            cur.execute("""
                SELECT title, description, code FROM offers
                WHERE is_active = 1 AND (start_date IS NULL OR start_date <= ?)
                AND (end_date IS NULL OR end_date >= ?)
            """, (today, today))
        rows = cur.fetchall()
        cur.close()
        conn.close()
        offers = [{"title": r[0], "description": r[1], "code": r[2]} for r in rows]
        return jsonify({"success": True, "offers": offers})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})


# =============================== واجهات الإدارة (محمية) ===============================
@app.route('/admin')
@login_required()
def admin_dashboard():
    return render_template_string('''
    <!DOCTYPE html>
    <html dir="rtl" lang="ar">
    <head>
        <meta charset="UTF-8">
        <title>لوحة التحكم الرئيسية</title>
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body { background: #f5f5f5; padding: 20px; font-family: Arial; }
            .header { background: #2c3e50; color: white; padding: 20px; border-radius: 10px; margin-bottom: 20px; text-align: center; }
            .dashboard-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; }
            .dashboard-card { background: white; padding: 30px; border-radius: 15px; box-shadow: 0 5px 15px rgba(0,0,0,0.1); text-align: center; cursor: pointer; transition: transform 0.3s; }
            .dashboard-card:hover { transform: translateY(-5px); }
            .card-icon { font-size: 48px; margin-bottom: 15px; }
            h2 { color: #2c3e50; margin-bottom: 10px; }
            .card-description { color: #7f8c8d; }
            .pos { border-top: 4px solid #27ae60; }
            .products { border-top: 4px solid #3498db; }
            .customers { border-top: 4px solid #2ecc71; }
            .sales { border-top: 4px solid #e67e22; }
            .purchases { border-top: 4px solid #9b59b6; }
            .expenses { border-top: 4px solid #e74c3c; }
            .reports { border-top: 4px solid #f1c40f; }
            .users { border-top: 4px solid #1abc9c; }
            .logout { background: #e74c3c; color: white; border: none; padding: 10px 20px; border-radius: 5px; cursor: pointer; margin-top: 20px; }
        </style>
    </head>
    <body>
        <div class="header">
            <h1>🎛️ لوحة تحكم الإدارة - سوبر ماركت اولاد قايد محمد</h1>
            <p>مرحباً، {{ session.username }} ({{ session.role }})</p>
            <button class="logout" onclick="location.href='/logout'">تسجيل الخروج</button>
        </div>

        <div class="dashboard-grid">
            <div class="dashboard-card pos" onclick="location.href='/pos'">
                <div class="card-icon">🛒</div>
                <h2>نقطة البيع (POS)</h2>
                <p class="card-description">إتمام عمليات البيع بسرعة</p>
            </div>
            <div class="dashboard-card products" onclick="location.href='/admin/products'">
                <div class="card-icon">📦</div>
                <h2>إدارة البضائع</h2>
                <p class="card-description">المنتجات، المخزون، التنبيهات</p>
            </div>
            <div class="dashboard-card customers" onclick="location.href='/admin/customers'">
                <div class="card-icon">👥</div>
                <h2>العملاء</h2>
                <p class="card-description">عرض وإدارة العملاء والنقاط</p>
            </div>
            <div class="dashboard-card sales" onclick="location.href='/admin/sales'">
                <div class="card-icon">💰</div>
                <h2>المبيعات</h2>
                <p class="card-description">الفواتير وتفاصيل المبيعات</p>
            </div>
            <div class="dashboard-card purchases" onclick="location.href='/admin/purchases'">
                <div class="card-icon">📥</div>
                <h2>المشتريات</h2>
                <p class="card-description">تسجيل فواتير الشراء</p>
            </div>
            <div class="dashboard-card expenses" onclick="location.href='/admin/expenses'">
                <div class="card-icon">📉</div>
                <h2>المصروفات</h2>
                <p class="card-description">تسجيل المصروفات اليومية</p>
            </div>
            <div class="dashboard-card reports" onclick="location.href='/admin/reports'">
                <div class="card-icon">📊</div>
                <h2>التقارير</h2>
                <p class="card-description">تقارير المبيعات والأرباح</p>
            </div>
            <div class="dashboard-card users" onclick="location.href='/admin/users'">
                <div class="card-icon">🔐</div>
                <h2>المستخدمين</h2>
                <p class="card-description">إدارة صلاحيات المستخدمين</p>
            </div>
        </div>
    </body>
    </html>
    ''')


# =============================== نقطة البيع (POS) ===============================
@app.route('/pos')
@login_required(role='admin')  # أو cashier حسب الصلاحية
def pos_page():
    return render_template_string('''
    <!DOCTYPE html>
    <html dir="rtl" lang="ar">
    <head>
        <meta charset="UTF-8">
        <title>نقطة البيع - POS</title>
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; font-family: Arial; }
            body { background: #f5f5f5; padding: 20px; }
            .container { display: grid; grid-template-columns: 1.5fr 1fr; gap: 20px; }
            .products-section { background: white; border-radius: 15px; padding: 20px; box-shadow: 0 5px 15px rgba(0,0,0,0.1); }
            .cart-section { background: white; border-radius: 15px; padding: 20px; box-shadow: 0 5px 15px rgba(0,0,0,0.1); position: sticky; top: 20px; }
            .search-box { margin-bottom: 20px; display: flex; gap: 10px; }
            .search-box input, .search-box select { flex: 1; padding: 12px; border: 2px solid #ddd; border-radius: 8px; font-size: 16px; }
            .products-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 15px; max-height: 70vh; overflow-y: auto; }
            .product-card { background: #f9f9f9; padding: 15px; border-radius: 10px; text-align: center; cursor: pointer; transition: 0.2s; border: 2px solid transparent; }
            .product-card:hover { border-color: #3498db; transform: scale(1.02); }
            .product-name { font-weight: bold; margin: 5px 0; }
            .product-price { color: #e74c3c; font-size: 18px; font-weight: bold; }
            .product-stock { color: #27ae60; font-size: 12px; }
            .cart-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
            .cart-items { max-height: 400px; overflow-y: auto; margin-bottom: 20px; }
            .cart-item { display: flex; justify-content: space-between; align-items: center; padding: 10px; background: #f8f9fa; border-radius: 8px; margin-bottom: 10px; }
            .cart-item-info { flex: 1; }
            .cart-item-actions button { background: none; border: none; cursor: pointer; font-size: 16px; margin: 0 5px; }
            .cart-total { font-size: 24px; font-weight: bold; text-align: left; margin: 20px 0; color: #2c3e50; }
            .customer-info { margin: 20px 0; }
            .customer-info input { width: 100%; padding: 12px; border: 2px solid #ddd; border-radius: 8px; }
            .payment-section { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
            .payment-section select, .payment-section input { padding: 12px; border: 2px solid #ddd; border-radius: 8px; }
            .checkout-btn { background: #27ae60; color: white; border: none; padding: 15px; width: 100%; border-radius: 8px; font-size: 18px; font-weight: bold; cursor: pointer; margin-top: 20px; }
            .checkout-btn:hover { background: #2ecc71; }
            .back-btn { background: #3498db; color: white; border: none; padding: 10px; border-radius: 5px; cursor: pointer; margin-bottom: 20px; }
        </style>
    </head>
    <body>
        <button class="back-btn" onclick="location.href='/admin'">← العودة للوحة التحكم</button>
        <div class="container">
            <div class="products-section">
                <h2>📦 المنتجات</h2>
                <div class="search-box">
                    <input type="text" id="search" placeholder="🔍 بحث بالاسم أو الباركود" onkeyup="loadProducts()">
                    <select id="category" onchange="loadProducts()">
                        <option value="">كل الفئات</option>
                    </select>
                </div>
                <div id="products-grid" class="products-grid"></div>
            </div>

            <div class="cart-section">
                <div class="cart-header">
                    <h2>🛒 السلة</h2>
                    <button onclick="clearCart()" style="background:#e74c3c; color:white; border:none; padding:8px 12px; border-radius:5px;">تفريغ</button>
                </div>
                <div id="cart-items" class="cart-items"></div>
                <div class="cart-total" id="cart-total">الإجمالي: 0 ريال</div>

                <div class="customer-info">
                    <input type="tel" id="customer-phone" placeholder="📱 رقم العميل (اختياري)">
                    <small>سيتم إضافة نقاط للعميل</small>
                </div>

                <div class="payment-section">
                    <select id="payment-method">
                        <option value="cash">نقدي</option>
                        <option value="card">بطاقة</option>
                        <option value="credit">آجل</option>
                    </select>
                    <input type="number" id="paid-amount" placeholder="المدفوع" step="0.01" min="0">
                </div>

                <button class="checkout-btn" onclick="checkout()">💳 إتمام البيع</button>
                <div id="result" style="margin-top:15px;"></div>
            </div>
        </div>

        <script>
            let cart = [];

            function loadProducts() {
                const search = document.getElementById('search').value;
                const category = document.getElementById('category').value;
                fetch(`/products?search=${encodeURIComponent(search)}&category=${encodeURIComponent(category)}`)
                    .then(r => r.json())
                    .then(data => {
                        if (data.success) {
                            let html = '';
                            data.products.forEach(p => {
                                html += `
                                    <div class="product-card" onclick="addToCart(${p.id}, '${p.name}', ${p.price}, ${p.quantity})">
                                        <div class="product-name">${p.name}</div>
                                        <div class="product-price">${p.price} ريال</div>
                                        <div class="product-stock">${p.quantity} ${p.unit}</div>
                                    </div>
                                `;
                            });
                            document.getElementById('products-grid').innerHTML = html || '<p>لا توجد منتجات</p>';
                        }
                    });
            }

            function loadCategories() {
                fetch('/admin/products/categories')
                    .then(r => r.json())
                    .then(data => {
                        if (data.success) {
                            const select = document.getElementById('category');
                            data.categories.forEach(cat => {
                                const option = document.createElement('option');
                                option.value = cat;
                                option.textContent = cat;
                                select.appendChild(option);
                            });
                        }
                    });
            }

            function addToCart(id, name, price, stock) {
                const existing = cart.find(item => item.id === id);
                if (existing) {
                    if (existing.quantity + 1 > stock) {
                        alert('الكمية المطلوبة أكبر من المتاح');
                        return;
                    }
                    existing.quantity++;
                } else {
                    if (stock < 1) {
                        alert('المنتج غير متوفر');
                        return;
                    }
                    cart.push({ id, name, price, quantity: 1 });
                }
                updateCart();
            }

            function removeFromCart(id) {
                cart = cart.filter(item => item.id !== id);
                updateCart();
            }

            function updateQuantity(id, change) {
                const item = cart.find(i => i.id === id);
                if (item) {
                    const newQty = item.quantity + change;
                    if (newQty <= 0) {
                        removeFromCart(id);
                    } else {
                        item.quantity = newQty;
                    }
                    updateCart();
                }
            }

            function updateCart() {
                const cartDiv = document.getElementById('cart-items');
                const totalDiv = document.getElementById('cart-total');
                if (cart.length === 0) {
                    cartDiv.innerHTML = '<p style="text-align:center;">السلة فارغة</p>';
                    totalDiv.innerText = 'الإجمالي: 0 ريال';
                    return;
                }
                let html = '';
                let total = 0;
                cart.forEach(item => {
                    const itemTotal = item.price * item.quantity;
                    total += itemTotal;
                    html += `
                        <div class="cart-item">
                            <div class="cart-item-info">
                                <div>${item.name}</div>
                                <div>${item.price} ريال × ${item.quantity} = ${itemTotal} ريال</div>
                            </div>
                            <div class="cart-item-actions">
                                <button onclick="updateQuantity(${item.id}, -1)">−</button>
                                <button onclick="updateQuantity(${item.id}, 1)">+</button>
                                <button onclick="removeFromCart(${item.id})">🗑️</button>
                            </div>
                        </div>
                    `;
                });
                cartDiv.innerHTML = html;
                totalDiv.innerText = `الإجمالي: ${total} ريال`;
            }

            function clearCart() {
                cart = [];
                updateCart();
            }

            function checkout() {
                if (cart.length === 0) {
                    alert('السلة فارغة');
                    return;
                }
                const phone = document.getElementById('customer-phone').value;
                const method = document.getElementById('payment-method').value;
                const paid = parseFloat(document.getElementById('paid-amount').value) || 0;
                const total = cart.reduce((sum, i) => sum + i.price * i.quantity, 0);

                if (method === 'cash' && paid < total) {
                    alert('المبلغ المدفوع أقل من الإجمالي');
                    return;
                }

                fetch('/api/sell', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        cart: cart,
                        phone: phone,
                        payment_method: method,
                        paid: paid
                    })
                })
                .then(r => r.json())
                .then(data => {
                    if (data.success) {
                        document.getElementById('result').innerHTML = `<div style="background:#d4edda; color:#155724; padding:15px; border-radius:8px;">✅ تمت العملية بنجاح - رقم الفاتورة: ${data.invoice}</div>`;
                        clearCart();
                    } else {
                        alert('خطأ: ' + data.message);
                    }
                });
            }

            window.onload = function() {
                loadProducts();
                loadCategories();
            };
        </script>
    </body>
    </html>
    ''')


# =============================== API إتمام البيع ===============================
@app.route('/api/sell', methods=['POST'])
@login_required()
def complete_sale():
    try:
        data = request.json
        cart = data['cart']
        phone = data.get('phone', '')
        payment_method = data['payment_method']
        paid = float(data.get('paid', 0))

        conn = get_db_connection()
        cur = conn.cursor()

        # حساب الإجمالي
        subtotal = sum(item['price'] * item['quantity'] for item in cart)
        total = subtotal  # يمكن إضافة ضريبة أو خصم لاحقاً

        # إنشاء رقم فاتورة فريد
        invoice = datetime.datetime.now().strftime('%Y%m%d%H%M%S') + str(secrets.randbelow(1000))

        # الحصول على user_id من الجلسة
        user_id = session['user_id']

        # البحث عن العميل إذا تم إدخال رقمه
        customer_id = None
        if phone:
            if DATABASE_URL:
                cur.execute("SELECT id FROM customers WHERE phone = %s AND is_active = 1", (phone,))
            else:
                cur.execute("SELECT id FROM customers WHERE phone = ? AND is_active = 1", (phone,))
            cust = cur.fetchone()
            if cust:
                customer_id = cust[0]

        # إدراج الفاتورة
        if DATABASE_URL:
            cur.execute("""
                INSERT INTO sales (invoice_number, customer_id, user_id, subtotal, total, payment_method, paid_amount, change_amount)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING id
            """, (invoice, customer_id, user_id, subtotal, total, payment_method, paid, paid - total))
            sale_id = cur.fetchone()[0]
        else:
            cur.execute("""
                INSERT INTO sales (invoice_number, customer_id, user_id, subtotal, total, payment_method, paid_amount, change_amount)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (invoice, customer_id, user_id, subtotal, total, payment_method, paid, paid - total))
            sale_id = cur.lastrowid

        # إدراج تفاصيل الفاتورة وتحديث المخزون
        for item in cart:
            if DATABASE_URL:
                cur.execute("""
                    INSERT INTO sale_items (sale_id, product_id, quantity, unit_price, total_price)
                    VALUES (%s, %s, %s, %s, %s)
                """, (sale_id, item['id'], item['quantity'], item['price'], item['price'] * item['quantity']))
                # تحديث المخزون
                cur.execute("""
                    UPDATE products SET quantity = quantity - %s, last_updated = %s
                    WHERE id = %s AND quantity >= %s
                """, (item['quantity'], datetime.date.today().isoformat(), item['id'], item['quantity']))
            else:
                cur.execute("""
                    INSERT INTO sale_items (sale_id, product_id, quantity, unit_price, total_price)
                    VALUES (?, ?, ?, ?, ?)
                """, (sale_id, item['id'], item['quantity'], item['price'], item['price'] * item['quantity']))
                cur.execute("""
                    UPDATE products SET quantity = quantity - ?, last_updated = ?
                    WHERE id = ? AND quantity >= ?
                """, (item['quantity'], datetime.date.today().isoformat(), item['id'], item['quantity']))

            # تسجيل حركة مخزون
            if DATABASE_URL:
                cur.execute("""
                    INSERT INTO inventory_logs (product_id, product_name, change_type, quantity_change, old_quantity, new_quantity, notes, user, timestamp)
                    SELECT %s, name, 'بيع', -%s, quantity + %s, quantity, 'بيع فاتورة ' || %s, %s, %s
                    FROM products WHERE id = %s
                """, (item['id'], item['quantity'], item['quantity'], invoice, session['username'], datetime.datetime.now().isoformat(), item['id']))
            else:
                cur.execute("""
                    INSERT INTO inventory_logs (product_id, product_name, change_type, quantity_change, old_quantity, new_quantity, notes, user, timestamp)
                    SELECT ?, name, 'بيع', ?, quantity + ?, quantity, 'بيع فاتورة ' || ?, ?, ?
                    FROM products WHERE id = ?
                """, (item['id'], -item['quantity'], item['quantity'], invoice, session['username'], datetime.datetime.now().isoformat(), item['id']))

        # تحديث بيانات العميل إذا وجد
        if customer_id:
            if DATABASE_URL:
                cur.execute("""
                    UPDATE customers SET
                        total_spent = total_spent + %s,
                        loyalty_points = loyalty_points + %s,
                        visits = visits + 1,
                        last_visit = %s
                    WHERE id = %s
                """, (total, int(total), datetime.date.today().isoformat(), customer_id))
            else:
                cur.execute("""
                    UPDATE customers SET
                        total_spent = total_spent + ?,
                        loyalty_points = loyalty_points + ?,
                        visits = visits + 1,
                        last_visit = ?
                    WHERE id = ?
                """, (total, int(total), datetime.date.today().isoformat(), customer_id))

        conn.commit()
        cur.close()
        conn.close()
        return jsonify({"success": True, "invoice": invoice, "total": total})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})


# =============================== باقي مسارات الإدارة (ملفات منفصلة سيتم إضافتها) ===============================
# هنا يمكن إضافة المسارات الأخرى مثل /admin/products (موجود بالفعل من الكود السابق)
# سنقوم بإعادة استخدام الكود القديم مع بعض التعديلات لإضافة الصلاحيات

# إعادة استخدام مسار /admin/products الموجود مع إضافة login_required
@app.route('/admin/products')
@login_required()
def admin_products():
    # استخدم نفس الكود الموجود (مع تعديلات بسيطة لتتناسب مع الجلسة)
    # سأقوم بنسخ الكود القديم مع تغيير المسار
    return render_template_string('''
    <!DOCTYPE html>
    <html dir="rtl" lang="ar">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>إدارة البضائع</title>
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; font-family: 'Segoe UI', Arial; }
            body { background: #f5f5f5; padding: 20px; }
            .header { background: linear-gradient(135deg, #2c3e50 0%, #4a6491 100%); color: white; padding: 25px; border-radius: 15px; margin-bottom: 25px; box-shadow: 0 5px 15px rgba(0,0,0,0.2); }
            .tabs { display: flex; background: white; border-radius: 10px; overflow: hidden; margin-bottom: 20px; box-shadow: 0 3px 10px rgba(0,0,0,0.1); }
            .tab { flex: 1; padding: 15px; text-align: center; cursor: pointer; border-bottom: 3px solid transparent; }
            .tab.active { background: #3498db; color: white; border-bottom: 3px solid #2980b9; }
            .content { display: none; background: white; padding: 25px; border-radius: 15px; box-shadow: 0 5px 15px rgba(0,0,0,0.1); }
            .content.active { display: block; }
            .form-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 20px; margin-bottom: 30px; }
            .form-group { margin-bottom: 20px; }
            label { display: block; margin-bottom: 8px; color: #2c3e50; font-weight: 600; }
            input, select, textarea { width: 100%; padding: 12px; border: 2px solid #ddd; border-radius: 8px; font-size: 16px; transition: border 0.3s; }
            input:focus, select:focus, textarea:focus { border-color: #3498db; outline: none; }
            button { background: linear-gradient(135deg, #4CAF50 0%, #45a049 100%); color: white; border: none; padding: 14px 28px; border-radius: 8px; font-size: 16px; cursor: pointer; transition: transform 0.2s, box-shadow 0.2s; }
            button:hover { transform: translateY(-2px); box-shadow: 0 5px 15px rgba(0,0,0,0.2); }
            button.secondary { background: linear-gradient(135deg, #3498db 0%, #2980b9 100%); }
            button.danger { background: linear-gradient(135deg, #e74c3c 0%, #c0392b 100%); }
            .stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin: 25px 0; }
            .stat-card { background: white; padding: 20px; border-radius: 12px; box-shadow: 0 3px 10px rgba(0,0,0,0.1); text-align: center; border-top: 4px solid #3498db; }
            .stat-number { font-size: 32px; font-weight: bold; color: #2c3e50; margin: 10px 0; }
            table { width: 100%; border-collapse: collapse; background: white; border-radius: 10px; overflow: hidden; box-shadow: 0 3px 10px rgba(0,0,0,0.1); }
            th { background: #3498db; color: white; padding: 18px; text-align: right; font-weight: 600; }
            td { padding: 16px; border-bottom: 1px solid #eee; }
            tr:hover { background: #f8f9fa; }
            .low-stock { background: #fff3cd; border-left: 4px solid #ffc107; }
            .out-of-stock { background: #f8d7da; border-left: 4px solid #dc3545; }
            .search-box { margin: 20px 0; padding: 15px; background: white; border-radius: 10px; box-shadow: 0 3px 10px rgba(0,0,0,0.1); }
            .alert { padding: 15px; border-radius: 8px; margin: 15px 0; }
            .alert-success { background: #d4edda; color: #155724; border: 1px solid #c3e6cb; }
            .alert-error { background: #f8d7da; color: #721c24; border: 1px solid #f5c6cb; }
            .modal { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.5); z-index: 1000; }
            .modal-content { background: white; width: 90%; max-width: 500px; margin: 50px auto; padding: 30px; border-radius: 15px; }
        </style>
    </head>
    <body>
        <div class="header">
            <h1>📦 إدارة البضائع والمخزون</h1>
            <p>سوبر ماركت اولاد قايد محمد - نظام إدارة كامل</p>
            <button onclick="location.href='/admin'" style="background:#e74c3c; padding:8px 15px; margin-top:10px;">العودة للوحة التحكم</button>
        </div>

        <div class="tabs">
            <div class="tab active" onclick="showTab('dashboard')">📊 لوحة التحكم</div>
            <div class="tab" onclick="showTab('products')">🛍️ البضائع</div>
            <div class="tab" onclick="showTab('add')">➕ إضافة منتج</div>
            <div class="tab" onclick="showTab('inventory')">📦 حركات المخزون</div>
        </div>

        <!-- لوحة التحكم -->
        <div id="dashboard" class="content active">
            <h2>📊 إحصائيات المخزون</h2>
            <div id="stats" class="stats-grid"></div>
            <h2 style="margin-top: 30px;">📈 المنتجات المنخفضة في المخزون</h2>
            <div id="low-stock-alert"></div>
        </div>

        <!-- قائمة البضائع -->
        <div id="products" class="content">
            <div class="search-box">
                <input type="text" id="search" placeholder="🔍 ابحث بالاسم أو الباركود..." onkeyup="loadProducts()" style="width: 300px; display: inline-block; margin-right: 10px;">
                <select id="filter-category" onchange="loadProducts()" style="width: 200px; display: inline-block;">
                    <option value="">جميع الفئات</option>
                </select>
            </div>
            <div id="products-list"></div>
        </div>

        <!-- إضافة منتج -->
        <div id="add" class="content">
            <h2>➕ إضافة منتج جديد</h2>
            <form id="add-product-form" onsubmit="return addProduct(event)">
                <div class="form-grid">
                    <div class="form-group">
                        <label>الباركود *</label>
                        <input type="text" id="barcode" required placeholder="1234567890123">
                    </div>
                    <div class="form-group">
                        <label>اسم المنتج *</label>
                        <input type="text" id="name" required placeholder="أرز بسمتي">
                    </div>
                    <div class="form-group">
                        <label>الفئة</label>
                        <select id="category">
                            <option value="مواد غذائية">مواد غذائية</option>
                            <option value="مبردات">مبردات</option>
                            <option value="معلبات">معلبات</option>
                            <option value="منظفات">منظفات</option>
                            <option value="مشروبات">مشروبات</option>
                            <option value="حلويات">حلويات</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label>سعر البيع (ريال) *</label>
                        <input type="number" id="price" step="0.01" required min="0">
                    </div>
                    <div class="form-group">
                        <label>سعر التكلفة (ريال)</label>
                        <input type="number" id="cost_price" step="0.01" min="0">
                    </div>
                    <div class="form-group">
                        <label>الكمية *</label>
                        <input type="number" id="quantity" required min="0">
                    </div>
                    <div class="form-group">
                        <label>الحد الأدنى للكمية</label>
                        <input type="number" id="min_quantity" value="10" min="0">
                    </div>
                    <div class="form-group">
                        <label>الوحدة</label>
                        <select id="unit">
                            <option value="قطعة">قطعة</option>
                            <option value="كيلو">كيلو</option>
                            <option value="لتر">لتر</option>
                            <option value="علبة">علبة</option>
                            <option value="كرتون">كرتون</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label>المورد</label>
                        <input type="text" id="supplier" placeholder="اسم المورد">
                    </div>
                    <div class="form-group">
                        <label>تاريخ الانتهاء</label>
                        <input type="date" id="expiry_date">
                    </div>
                </div>
                <div style="text-align: left; margin-top: 20px;">
                    <button type="submit">💾 حفظ المنتج</button>
                    <button type="button" class="secondary" onclick="resetForm()">🔄 مسح النموذج</button>
                </div>
            </form>
        </div>

        <!-- حركات المخزون -->
        <div id="inventory" class="content">
            <h2>📦 سجل حركات المخزون</h2>
            <div id="inventory-logs"></div>
        </div>

        <!-- Modal للتعديل -->
        <div id="editModal" class="modal">
            <div class="modal-content">
                <h3>✏️ تعديل المنتج</h3>
                <form id="edit-product-form">
                    <input type="hidden" id="edit-id">
                    <div class="form-grid">
                        <div class="form-group">
                            <label>اسم المنتج</label>
                            <input type="text" id="edit-name" required>
                        </div>
                        <div class="form-group">
                            <label>السعر</label>
                            <input type="number" id="edit-price" step="0.01" required>
                        </div>
                        <div class="form-group">
                            <label>الكمية</label>
                            <input type="number" id="edit-quantity" required>
                        </div>
                    </div>
                    <div style="text-align: left; margin-top: 20px;">
                        <button type="submit">💾 حفظ التغييرات</button>
                        <button type="button" class="secondary" onclick="closeModal()">إلغاء</button>
                    </div>
                </form>
            </div>
        </div>

        <script>
            let currentTab = 'dashboard';

            function showTab(tabName) {
                currentTab = tabName;
                document.querySelectorAll('.tab').forEach(tab => {
                    tab.classList.remove('active');
                });
                event.target.classList.add('active');

                document.querySelectorAll('.content').forEach(content => {
                    content.classList.remove('active');
                });
                document.getElementById(tabName).classList.add('active');

                if (tabName === 'dashboard') loadDashboard();
                if (tabName === 'products') loadProducts();
                if (tabName === 'inventory') loadInventoryLogs();
            }

            function loadDashboard() {
                fetch('/admin/products/stats')
                    .then(r => r.json())
                    .then(data => {
                        if (data.success) {
                            document.getElementById('stats').innerHTML = `
                                <div class="stat-card">
                                    <div>🛍️</div>
                                    <div class="stat-number">${data.total_products}</div>
                                    <div>إجمالي المنتجات</div>
                                </div>
                                <div class="stat-card">
                                    <div>💰</div>
                                    <div class="stat-number">${data.total_value.toFixed(2)}</div>
                                    <div>قيمة المخزون</div>
                                </div>
                                <div class="stat-card">
                                    <div>⚠️</div>
                                    <div class="stat-number">${data.low_stock}</div>
                                    <div>منخفضة المخزون</div>
                                </div>
                                <div class="stat-card">
                                    <div>📈</div>
                                    <div class="stat-number">${data.categories}</div>
                                    <div>الفئات</div>
                                </div>
                            `;

                            let lowStockHTML = '';
                            if (data.low_stock_products.length > 0) {
                                lowStockHTML = '<table>';
                                lowStockHTML += '<tr><th>المنتج</th><th>الكمية</th><th>الحد الأدنى</th><th></th></tr>';
                                data.low_stock_products.forEach(product => {
                                    lowStockHTML += `
                                        <tr class="low-stock">
                                            <td>${product.name}</td>
                                            <td>${product.quantity} ${product.unit}</td>
                                            <td>${product.min_quantity}</td>
                                            <td><button class="secondary" onclick="editProduct(${product.id})">تعديل</button></td>
                                        </tr>
                                    `;
                                });
                                lowStockHTML += '</table>';
                            } else {
                                lowStockHTML = '<div class="alert alert-success">جميع المنتجات في مستوى جيد ✓</div>';
                            }
                            document.getElementById('low-stock-alert').innerHTML = lowStockHTML;
                        }
                    });
            }

            function loadProducts() {
                const search = document.getElementById('search')?.value || '';
                const category = document.getElementById('filter-category')?.value || '';

                fetch(`/admin/products/list?search=${encodeURIComponent(search)}&category=${encodeURIComponent(category)}`)
                    .then(r => r.json())
                    .then(data => {
                        if (data.success) {
                            let html = '<table>';
                            html += `
                                <thead>
                                    <tr>
                                        <th>الباركود</th>
                                        <th>الاسم</th>
                                        <th>الفئة</th>
                                        <th>السعر</th>
                                        <th>المخزون</th>
                                        <th>القيمة</th>
                                        <th>الإجراءات</th>
                                    </tr>
                                </thead>
                                <tbody>
                            `;

                            data.products.forEach(product => {
                                const value = product.price * product.quantity;
                                const rowClass = product.quantity === 0 ? 'out-of-stock' : 
                                                product.quantity <= product.min_quantity ? 'low-stock' : '';

                                html += `
                                    <tr class="${rowClass}">
                                        <td>${product.barcode}</td>
                                        <td>${product.name}</td>
                                        <td>${product.category}</td>
                                        <td>${product.price.toFixed(2)} ر.س</td>
                                        <td>${product.quantity} ${product.unit}</td>
                                        <td>${value.toFixed(2)} ر.س</td>
                                        <td>
                                            <button class="secondary" onclick="editProduct(${product.id})">✏️</button>
                                            <button class="danger" onclick="deleteProduct(${product.id})">🗑️</button>
                                        </td>
                                    </tr>
                                `;
                            });

                            html += '</tbody></table>';
                            document.getElementById('products-list').innerHTML = html;
                        }
                    });
            }

            function addProduct(e) {
                e.preventDefault();

                const product = {
                    barcode: document.getElementById('barcode').value,
                    name: document.getElementById('name').value,
                    category: document.getElementById('category').value,
                    price: parseFloat(document.getElementById('price').value),
                    cost_price: parseFloat(document.getElementById('cost_price').value) || 0,
                    quantity: parseInt(document.getElementById('quantity').value),
                    min_quantity: parseInt(document.getElementById('min_quantity').value) || 10,
                    unit: document.getElementById('unit').value,
                    supplier: document.getElementById('supplier').value,
                    expiry_date: document.getElementById('expiry_date').value
                };

                fetch('/admin/products/add', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(product)
                })
                .then(r => r.json())
                .then(data => {
                    if (data.success) {
                        alert('✅ تم إضافة المنتج بنجاح');
                        resetForm();
                        loadProducts();
                        showTab('products');
                    } else {
                        alert('❌ ' + data.message);
                    }
                });
            }

            function resetForm() {
                document.getElementById('add-product-form').reset();
            }

            function editProduct(id) {
                fetch(`/admin/products/${id}`)
                    .then(r => r.json())
                    .then(data => {
                        if (data.success) {
                            document.getElementById('edit-id').value = data.product.id;
                            document.getElementById('edit-name').value = data.product.name;
                            document.getElementById('edit-price').value = data.product.price;
                            document.getElementById('edit-quantity').value = data.product.quantity;
                            document.getElementById('editModal').style.display = 'block';
                        }
                    });
            }

            document.getElementById('edit-product-form').onsubmit = function(e) {
                e.preventDefault();

                const product = {
                    id: document.getElementById('edit-id').value,
                    name: document.getElementById('edit-name').value,
                    price: parseFloat(document.getElementById('edit-price').value),
                    quantity: parseInt(document.getElementById('edit-quantity').value)
                };

                fetch('/admin/products/update', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(product)
                })
                .then(r => r.json())
                .then(data => {
                    if (data.success) {
                        alert('✅ تم تحديث المنتج بنجاح');
                        closeModal();
                        loadProducts();
                        loadDashboard();
                    } else {
                        alert('❌ ' + data.message);
                    }
                });
            };

            function deleteProduct(id) {
                if (confirm('هل أنت متأكد من حذف هذا المنتج؟')) {
                    fetch(`/admin/products/delete/${id}`, {
                        method: 'DELETE'
                    })
                    .then(r => r.json())
                    .then(data => {
                        if (data.success) {
                            alert('✅ تم حذف المنتج بنجاح');
                            loadProducts();
                            loadDashboard();
                        } else {
                            alert('❌ ' + data.message);
                        }
                    });
                }
            }

            function loadInventoryLogs() {
                fetch('/admin/products/logs')
                    .then(r => r.json())
                    .then(data => {
                        if (data.success) {
                            let html = '<table>';
                            html += `
                                <thead>
                                    <tr>
                                        <th>التاريخ</th>
                                        <th>المنتج</th>
                                        <th>نوع الحركة</th>
                                        <th>الكمية</th>
                                        <th>الملاحظات</th>
                                        <th>المستخدم</th>
                                    </tr>
                                </thead>
                                <tbody>
                            `;

                            data.logs.forEach(log => {
                                html += `
                                    <tr>
                                        <td>${log.timestamp}</td>
                                        <td>${log.product_name}</td>
                                        <td>${log.change_type}</td>
                                        <td>${log.quantity_change > 0 ? '+' : ''}${log.quantity_change}</td>
                                        <td>${log.notes || '-'}</td>
                                        <td>${log.user || 'نظام'}</td>
                                    </tr>
                                `;
                            });

                            html += '</tbody></table>';
                            document.getElementById('inventory-logs').innerHTML = html;
                        }
                    });
            }

            function closeModal() {
                document.getElementById('editModal').style.display = 'none';
            }

            document.addEventListener('DOMContentLoaded', function() {
                loadDashboard();
                fetch('/admin/products/categories')
                    .then(r => r.json())
                    .then(data => {
                        if (data.success) {
                            const select = document.getElementById('filter-category');
                            data.categories.forEach(cat => {
                                const option = document.createElement('option');
                                option.value = cat;
                                option.textContent = cat;
                                select.appendChild(option);
                            });
                        }
                    });
            });

            window.onclick = function(event) {
                const modal = document.getElementById('editModal');
                if (event.target == modal) {
                    closeModal();
                }
            };
        </script>
    </body>
    </html>
    ''')


# إعادة استخدام مسارات API للمنتجات مع إضافة login_required
@app.route('/admin/products/stats')
@login_required()
def products_stats():
    # نفس الكود الموجود مع تعديل بسيط
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        if DATABASE_URL:
            cur.execute("SELECT COUNT(*) FROM products WHERE is_active = 1")
            total_products = cur.fetchone()[0] or 0
            cur.execute("SELECT SUM(price * quantity) FROM products WHERE is_active = 1")
            total_value = cur.fetchone()[0] or 0
            cur.execute("SELECT COUNT(*) FROM products WHERE quantity <= min_quantity AND quantity > 0 AND is_active = 1")
            low_stock = cur.fetchone()[0] or 0
            cur.execute("SELECT COUNT(DISTINCT category) FROM products WHERE is_active = 1")
            categories = cur.fetchone()[0] or 0
            cur.execute("SELECT id, name, quantity, min_quantity, unit FROM products WHERE quantity <= min_quantity AND is_active = 1 ORDER BY quantity ASC LIMIT 10")
            low_stock_products = [{"id": r[0], "name": r[1], "quantity": r[2], "min_quantity": r[3], "unit": r[4]} for r in cur.fetchall()]
        else:
            cur.execute("SELECT COUNT(*) FROM products WHERE is_active = 1")
            total_products = cur.fetchone()[0] or 0
            cur.execute("SELECT SUM(price * quantity) FROM products WHERE is_active = 1")
            total_value = cur.fetchone()[0] or 0
            cur.execute("SELECT COUNT(*) FROM products WHERE quantity <= min_quantity AND quantity > 0 AND is_active = 1")
            low_stock = cur.fetchone()[0] or 0
            cur.execute("SELECT COUNT(DISTINCT category) FROM products WHERE is_active = 1")
            categories = cur.fetchone()[0] or 0
            cur.execute("SELECT id, name, quantity, min_quantity, unit FROM products WHERE quantity <= min_quantity AND is_active = 1 ORDER BY quantity ASC LIMIT 10")
            low_stock_products = [{"id": r[0], "name": r[1], "quantity": r[2], "min_quantity": r[3], "unit": r[4]} for r in cur.fetchall()]
        cur.close()
        conn.close()
        return jsonify({
            "success": True,
            "total_products": total_products,
            "total_value": total_value,
            "low_stock": low_stock,
            "categories": categories,
            "low_stock_products": low_stock_products
        })
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})


@app.route('/admin/products/list')
@login_required()
def admin_products_list():
    try:
        search = request.args.get('search', '')
        category = request.args.get('category', '')
        conn = get_db_connection()
        cur = conn.cursor()
        if DATABASE_URL:
            query = "SELECT id, barcode, name, category, price, cost_price, quantity, min_quantity, unit, supplier, expiry_date, added_date FROM products WHERE is_active = 1"
            params = []
            if search:
                query += " AND (name ILIKE %s OR barcode ILIKE %s)"
                params.append(f'%{search}%')
                params.append(f'%{search}%')
            if category:
                query += " AND category = %s"
                params.append(category)
            query += " ORDER BY name"
            cur.execute(query, params)
        else:
            query = "SELECT id, barcode, name, category, price, cost_price, quantity, min_quantity, unit, supplier, expiry_date, added_date FROM products WHERE is_active = 1"
            params = []
            if search:
                query += " AND (name LIKE ? OR barcode LIKE ?)"
                params.append(f'%{search}%')
                params.append(f'%{search}%')
            if category:
                query += " AND category = ?"
                params.append(category)
            query += " ORDER BY name"
            cur.execute(query, params)
        products = [{
            "id": r[0], "barcode": r[1], "name": r[2], "category": r[3], "price": r[4],
            "cost_price": r[5], "quantity": r[6], "min_quantity": r[7], "unit": r[8],
            "supplier": r[9], "expiry_date": r[10], "added_date": r[11]
        } for r in cur.fetchall()]
        cur.close()
        conn.close()
        return jsonify({"success": True, "products": products})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})


@app.route('/admin/products/categories')
@login_required()
def product_categories():
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        if DATABASE_URL:
            cur.execute("SELECT DISTINCT category FROM products WHERE is_active = 1 ORDER BY category")
        else:
            cur.execute("SELECT DISTINCT category FROM products WHERE is_active = 1 ORDER BY category")
        categories = [r[0] for r in cur.fetchall() if r[0]]
        cur.close()
        conn.close()
        return jsonify({"success": True, "categories": categories})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})


@app.route('/admin/products/add', methods=['POST'])
@login_required()
def add_product():
    try:
        data = request.json
        required_fields = ['barcode', 'name', 'price', 'quantity']
        for field in required_fields:
            if not data.get(field):
                return jsonify({"success": False, "message": f"حقل {field} مطلوب"})
        conn = get_db_connection()
        cur = conn.cursor()
        # التحقق من تكرار الباركود
        if DATABASE_URL:
            cur.execute("SELECT id FROM products WHERE barcode = %s", (data['barcode'],))
        else:
            cur.execute("SELECT id FROM products WHERE barcode = ?", (data['barcode'],))
        if cur.fetchone():
            cur.close()
            conn.close()
            return jsonify({"success": False, "message": "الباركود مسجل مسبقاً"})
        today = datetime.date.today().isoformat()
        if DATABASE_URL:
            cur.execute("""
                INSERT INTO products (barcode, name, category, price, cost_price, quantity, min_quantity, unit, supplier, expiry_date, added_date, last_updated)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id
            """, (data['barcode'], data['name'], data.get('category', 'مواد غذائية'), float(data['price']), float(data.get('cost_price', 0)), int(data['quantity']), int(data.get('min_quantity', 10)), data.get('unit', 'قطعة'), data.get('supplier', ''), data.get('expiry_date', ''), today, today))
            product_id = cur.fetchone()[0]
        else:
            cur.execute("""
                INSERT INTO products (barcode, name, category, price, cost_price, quantity, min_quantity, unit, supplier, expiry_date, added_date, last_updated)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (data['barcode'], data['name'], data.get('category', 'مواد غذائية'), float(data['price']), float(data.get('cost_price', 0)), int(data['quantity']), int(data.get('min_quantity', 10)), data.get('unit', 'قطعة'), data.get('supplier', ''), data.get('expiry_date', ''), today, today))
            product_id = cur.lastrowid
        # تسجيل حركة مخزون
        if DATABASE_URL:
            cur.execute("""
                INSERT INTO inventory_logs (product_id, product_name, change_type, quantity_change, old_quantity, new_quantity, notes, user, timestamp)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (product_id, data['name'], 'إضافة', int(data['quantity']), 0, int(data['quantity']), 'إضافة منتج جديد', session['username'], datetime.datetime.now().isoformat()))
        else:
            cur.execute("""
                INSERT INTO inventory_logs (product_id, product_name, change_type, quantity_change, old_quantity, new_quantity, notes, user, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (product_id, data['name'], 'إضافة', int(data['quantity']), 0, int(data['quantity']), 'إضافة منتج جديد', session['username'], datetime.datetime.now().isoformat()))
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({"success": True, "message": "تم إضافة المنتج بنجاح"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})


@app.route('/admin/products/<int:product_id>')
@login_required()
def get_product(product_id):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        if DATABASE_URL:
            cur.execute("SELECT id, name, price, quantity, category, barcode, unit, min_quantity FROM products WHERE id = %s AND is_active = 1", (product_id,))
        else:
            cur.execute("SELECT id, name, price, quantity, category, barcode, unit, min_quantity FROM products WHERE id = ? AND is_active = 1", (product_id,))
        row = cur.fetchone()
        cur.close()
        conn.close()
        if row:
            return jsonify({
                "success": True,
                "product": {
                    "id": row[0], "name": row[1], "price": row[2], "quantity": row[3],
                    "category": row[4], "barcode": row[5], "unit": row[6], "min_quantity": row[7]
                }
            })
        else:
            return jsonify({"success": False, "message": "المنتج غير موجود"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})


@app.route('/admin/products/update', methods=['POST'])
@login_required()
def update_product():
    try:
        data = request.json
        if not data.get('id'):
            return jsonify({"success": False, "message": "معرف المنتج مطلوب"})
        conn = get_db_connection()
        cur = conn.cursor()
        if DATABASE_URL:
            cur.execute("SELECT quantity, name FROM products WHERE id = %s", (data['id'],))
        else:
            cur.execute("SELECT quantity, name FROM products WHERE id = ?", (data['id'],))
        current = cur.fetchone()
        if not current:
            cur.close()
            conn.close()
            return jsonify({"success": False, "message": "المنتج غير موجود"})
        old_quantity = current[0]
        product_name = current[1]
        new_quantity = int(data.get('quantity', old_quantity))
        quantity_change = new_quantity - old_quantity
        if DATABASE_URL:
            cur.execute("UPDATE products SET name = %s, price = %s, quantity = %s, last_updated = %s WHERE id = %s",
                        (data['name'], float(data['price']), new_quantity, datetime.date.today().isoformat(), data['id']))
        else:
            cur.execute("UPDATE products SET name = ?, price = ?, quantity = ?, last_updated = ? WHERE id = ?",
                        (data['name'], float(data['price']), new_quantity, datetime.date.today().isoformat(), data['id']))
        if quantity_change != 0:
            if DATABASE_URL:
                cur.execute("""
                    INSERT INTO inventory_logs (product_id, product_name, change_type, quantity_change, old_quantity, new_quantity, notes, user, timestamp)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (data['id'], product_name, 'تعديل', quantity_change, old_quantity, new_quantity, 'تعديل المنتج', session['username'], datetime.datetime.now().isoformat()))
            else:
                cur.execute("""
                    INSERT INTO inventory_logs (product_id, product_name, change_type, quantity_change, old_quantity, new_quantity, notes, user, timestamp)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (data['id'], product_name, 'تعديل', quantity_change, old_quantity, new_quantity, 'تعديل المنتج', session['username'], datetime.datetime.now().isoformat()))
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({"success": True, "message": "تم تحديث المنتج بنجاح"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})


@app.route('/admin/products/delete/<int:product_id>', methods=['DELETE'])
@login_required()
def delete_product(product_id):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        if DATABASE_URL:
            cur.execute("SELECT name, quantity FROM products WHERE id = %s", (product_id,))
        else:
            cur.execute("SELECT name, quantity FROM products WHERE id = ?", (product_id,))
        product = cur.fetchone()
        if not product:
            cur.close()
            conn.close()
            return jsonify({"success": False, "message": "المنتج غير موجود"})
        if DATABASE_URL:
            cur.execute("UPDATE products SET is_active = 0 WHERE id = %s", (product_id,))
        else:
            cur.execute("UPDATE products SET is_active = 0 WHERE id = ?", (product_id,))
        if DATABASE_URL:
            cur.execute("""
                INSERT INTO inventory_logs (product_id, product_name, change_type, quantity_change, old_quantity, new_quantity, notes, user, timestamp)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (product_id, product[0], 'حذف', -product[1], product[1], 0, 'حذف المنتج', session['username'], datetime.datetime.now().isoformat()))
        else:
            cur.execute("""
                INSERT INTO inventory_logs (product_id, product_name, change_type, quantity_change, old_quantity, new_quantity, notes, user, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (product_id, product[0], 'حذف', -product[1], product[1], 0, 'حذف المنتج', session['username'], datetime.datetime.now().isoformat()))
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({"success": True, "message": "تم حذف المنتج بنجاح"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})


@app.route('/admin/products/logs')
@login_required()
def inventory_logs():
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        if DATABASE_URL:
            cur.execute("SELECT product_name, change_type, quantity_change, old_quantity, new_quantity, notes, user, timestamp FROM inventory_logs ORDER BY timestamp DESC LIMIT 50")
        else:
            cur.execute("SELECT product_name, change_type, quantity_change, old_quantity, new_quantity, notes, user, timestamp FROM inventory_logs ORDER BY timestamp DESC LIMIT 50")
        logs = [{
            "product_name": r[0], "change_type": r[1], "quantity_change": r[2],
            "old_quantity": r[3], "new_quantity": r[4], "notes": r[5], "user": r[6], "timestamp": r[7]
        } for r in cur.fetchall()]
        cur.close()
        conn.close()
        return jsonify({"success": True, "logs": logs})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})


# مسار /admin/customers (مثال بسيط)
@app.route('/admin/customers')
@login_required()
def admin_customers_list():
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        if DATABASE_URL:
            cur.execute("SELECT phone, name, loyalty_points, total_spent, visits, last_visit, customer_tier FROM customers WHERE is_active = 1 ORDER BY total_spent DESC")
        else:
            cur.execute("SELECT phone, name, loyalty_points, total_spent, visits, last_visit, customer_tier FROM customers WHERE is_active = 1 ORDER BY total_spent DESC")
        customers = cur.fetchall()
        cur.close()
        conn.close()
        html = '''
        <!DOCTYPE html>
        <html dir="rtl" lang="ar">
        <head>
            <meta charset="UTF-8">
            <title>قائمة العملاء</title>
            <style>
                * { margin:0; padding:0; box-sizing:border-box; }
                body { background:#f5f5f5; padding:20px; font-family:Arial; }
                .header { background:#2c3e50; color:white; padding:20px; border-radius:10px; margin-bottom:20px; display:flex; justify-content:space-between; align-items:center; }
                table { width:100%; background:white; border-radius:10px; overflow:hidden; box-shadow:0 5px 15px rgba(0,0,0,0.1); }
                th { background:#3498db; color:white; padding:15px; text-align:right; }
                td { padding:12px; border-bottom:1px solid #eee; }
                .back-btn { background:#e74c3c; color:white; padding:10px 20px; border:none; border-radius:5px; cursor:pointer; }
            </style>
        </head>
        <body>
            <div class="header">
                <h1>👥 قائمة العملاء</h1>
                <button class="back-btn" onclick="location.href='/admin'">العودة</button>
            </div>
            <table>
                <thead>
                    <tr>
                        <th>الاسم</th><th>الهاتف</th><th>النقاط</th><th>الإنفاق</th><th>الزيارات</th><th>آخر زيارة</th><th>المستوى</th>
                    </tr>
                </thead>
                <tbody>
        '''
        for cust in customers:
            html += f'''
                <tr>
                    <td>{cust[1]}</td>
                    <td>{cust[0]}</td>
                    <td>{cust[2]}</td>
                    <td>{cust[3]:.2f} ريال</td>
                    <td>{cust[4]}</td>
                    <td>{cust[5]}</td>
                    <td>{cust[6] or 'عادي'}</td>
                </tr>
            '''
        html += '''
                </tbody>
            </table>
        </body>
        </html>
        '''
        return html
    except Exception as e:
        return f"خطأ: {str(e)}"


# =============================== بدء التشغيل ===============================
if __name__ == '__main__':
    print("=" * 70)
    print("🚀 نظام سوبر ماركت متكامل - سوبر ماركت اولاد قايد محمد")
    print("=" * 70)
    print("📁 قاعدة البيانات: " + ("PostgreSQL" if DATABASE_URL else "SQLite local"))
    print("👤 مستخدم افتراضي: admin / admin123")
    print("🌐 الروابط المتاحة:")
    print("   👉 http://localhost:5000/            (للعملاء)")
    print("   👉 http://localhost:5000/login       (تسجيل الدخول للإدارة)")
    print("   👉 http://localhost:5000/admin       (لوحة التحكم)")
    print("   👉 http://localhost:5000/pos         (نقطة البيع)")
    print("=" * 70)
    app.run(host='127.0.0.1', port=5000, debug=True)
