from flask import Flask, render_template_string, request, jsonify, redirect, url_for
import sqlite3
import os
import json

app = Flask(__name__)

# --- إعدادات قاعدة البيانات ---
DATABASE = 'supermarket_v2.db'

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db() as conn:
        # جدول الفئات
        conn.execute('''CREATE TABLE IF NOT EXISTS categories (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            name TEXT NOT NULL UNIQUE)''')
        # جدول المنتجات
        conn.execute('''CREATE TABLE IF NOT EXISTS products (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            category_id INTEGER,
                            name TEXT NOT NULL,
                            price REAL NOT NULL,
                            quantity TEXT,
                            FOREIGN KEY (category_id) REFERENCES categories (id) ON DELETE CASCADE)''')
        conn.commit()

init_db()

# --- القوالب (HTML/CSS/JS) ---

# واجهة الزبون (الرئيسية)
CUSTOMER_UI = """
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>سوبر ماركت أولاد قايد محمد</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://fonts.googleapis.com/css2?family=Tajawal:wght@400;700&display=swap" rel="stylesheet">
    <style>
        body { font-family: 'Tajawal', sans-serif; background-color: #000; color: #d4af37; }
        .gold-border { border-color: #d4af37; }
        .gold-bg { background-color: #d4af37; color: #000; }
        .gold-text { color: #d4af37; }
        .card { background: #1a1a1a; border: 1px solid #d4af37; border-radius: 12px; }
        .sticky-footer { position: fixed; bottom: 0; width: 100%; z-index: 50; }
        .category-tab { cursor: pointer; padding: 10px 20px; border-bottom: 2px solid transparent; white-space: nowrap; }
        .category-tab.active { border-bottom: 2px solid #d4af37; font-weight: bold; }
        #cart-modal { display: none; background: rgba(0,0,0,0.9); }
    </style>
</head>
<body class="pb-24">

    <!-- الهيدر والشعار -->
    <header class="text-center py-8 border-b gold-border bg-black">
        <h1 class="text-3xl font-bold mb-2">سوبر ماركت أولاد قايد محمد</h1>
        <p class="text-xl mb-4 text-gray-400">للتجارة العامة</p>
        <div class="flex justify-center">
             <div class="w-32 h-32 rounded-full border-4 gold-border flex items-center justify-center overflow-hidden bg-white">
                <span class="text-black font-bold text-center leading-tight">أولاد قايد<br>للتجارة العامة</span>
             </div>
        </div>
    </header>

    <!-- قائمة الفئات (تصفح أفقي) -->
    <div class="sticky top-0 bg-black z-40 border-b gold-border overflow-x-auto flex no-scrollbar" id="category-bar">
        <div class="category-tab active" onclick="filterCategory(0, this)">الكل</div>
        {% for cat in categories %}
        <div class="category-tab" onclick="filterCategory({{cat.id}}, this)">{{cat.name}}</div>
        {% endfor %}
    </div>

    <!-- قائمة المنتجات -->
    <main class="p-4 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {% for prod in products %}
        <div class="card p-4 product-item" data-category="{{prod.category_id}}">
            <h3 class="text-xl font-bold mb-1">{{prod.name}}</h3>
            <p class="text-gray-400 text-sm mb-2">الفئة: {{prod.cat_name}}</p>
            <div class="flex justify-between items-center">
                <span class="text-lg font-bold text-white">{{prod.price}} ريال</span>
                <button onclick="addToCart({{prod.id}}, '{{prod.name}}', {{prod.price}})" class="gold-bg px-4 py-2 rounded-lg font-bold">إضافة +</button>
            </div>
        </div>
        {% endfor %}
    </main>

    <!-- فوتر المعلومات -->
    <footer class="mt-10 p-6 border-t gold-border text-center text-sm">
        <p class="mb-2">الموقع: الأزرق / موعد حمادة : حبيل تود</p>
        <p class="mb-4">لصاحبها: « فايز / وإخوانه »</p>
        <div class="bg-gray-900 p-4 rounded-lg inline-block text-gray-300">
            إعداد وتصميم « م / وسيم العامري » <br> للتواصل: 967770295876
        </div>
    </footer>

    <!-- شريط السلة السفلي -->
    <div class="sticky-footer bg-black border-t gold-border p-4 flex justify-between items-center">
        <div class="text-lg">
            الإجمالي: <span id="cart-total" class="font-bold">0</span> ريال
        </div>
        <button onclick="toggleCart()" class="gold-bg px-6 py-2 rounded-full font-bold">عرض السلة (<span id="cart-count">0</span>)</button>
    </div>

    <!-- مودال السلة والطلب -->
    <div id="cart-modal" class="fixed inset-0 z-50 p-4 overflow-y-auto">
        <div class="max-w-md mx-auto bg-black border-2 gold-border rounded-xl p-6">
            <div class="flex justify-between items-center mb-6">
                <h2 class="text-2xl font-bold">سلة المشتريات</h2>
                <button onclick="toggleCart()" class="text-red-500 font-bold">إغلاق</button>
            </div>
            
            <div id="cart-items" class="space-y-4 mb-6">
                <!-- المنتجات تظهر هنا -->
            </div>

            <hr class="gold-border mb-4">

            <div class="space-y-4">
                <input type="text" id="cust-name" placeholder="إسم الزبون" class="w-full p-2 bg-gray-800 rounded gold-border border outline-none">
                <input type="tel" id="cust-phone" placeholder="رقم الهاتف" class="w-full p-2 bg-gray-800 rounded gold-border border outline-none">
                <input type="text" id="cust-loc" placeholder="الموقع / السكن" class="w-full p-2 bg-gray-800 rounded gold-border border outline-none">
            </div>

            <div class="flex gap-2 mt-6">
                <button onclick="sendToWhatsApp()" class="flex-1 bg-green-600 text-white py-3 rounded-lg font-bold">إرسال للواتساب</button>
                <button onclick="printInvoice()" class="flex-1 gold-bg py-3 rounded-lg font-bold">عرض الفاتورة</button>
            </div>
        </div>
    </div>

    <script>
        let cart = [];

        function filterCategory(id, el) {
            document.querySelectorAll('.category-tab').forEach(t => t.classList.remove('active'));
            el.classList.add('active');
            document.querySelectorAll('.product-item').forEach(item => {
                if (id === 0 || item.dataset.category == id) item.style.display = 'block';
                else item.style.display = 'none';
            });
        }

        function addToCart(id, name, price) {
            let item = cart.find(i => i.id === id);
            if (item) item.qty++;
            else cart.push({id, name, price, qty: 1});
            updateUI();
        }

        function updateUI() {
            document.getElementById('cart-count').innerText = cart.reduce((a, b) => a + b.qty, 0);
            document.getElementById('cart-total').innerText = cart.reduce((a, b) => a + (b.price * b.qty), 0);
            renderCart();
        }

        function renderCart() {
            const container = document.getElementById('cart-items');
            if (cart.length === 0) {
                container.innerHTML = '<p class="text-center text-gray-500">السلة فارغة</p>';
                return;
            }
            container.innerHTML = cart.map((item, idx) => `
                <div class="flex justify-between items-center border-b border-gray-800 pb-2">
                    <div>
                        <p class="font-bold text-white">${item.name}</p>
                        <p class="text-xs text-gray-400">${item.price} × ${item.qty}</p>
                    </div>
                    <div class="flex items-center gap-2">
                        <button onclick="changeQty(${idx}, -1)" class="w-8 h-8 rounded bg-gray-700">-</button>
                        <span>${item.qty}</span>
                        <button onclick="changeQty(${idx}, 1)" class="w-8 h-8 rounded bg-gray-700">+</button>
                    </div>
                </div>
            `).join('');
        }

        function changeQty(idx, delta) {
            cart[idx].qty += delta;
            if (cart[idx].qty <= 0) cart.splice(idx, 1);
            updateUI();
        }

        function toggleCart() {
            const modal = document.getElementById('cart-modal');
            modal.style.display = modal.style.display === 'block' ? 'none' : 'block';
        }

        function sendToWhatsApp() {
            const name = document.getElementById('cust-name').value;
            const phone = document.getElementById('cust-phone').value;
            const loc = document.getElementById('cust-loc').value;
            if(!name || !phone) { alert("يرجى إدخال الإسم ورقم الهاتف"); return; }

            let message = `*طلب جديد - أولاد قايد محمد*\\n`;
            message += `الزبون: ${name}\\n`;
            message += `الهاتف: ${phone}\\n`;
            message += `الموقع: ${loc}\\n`;
            message += `------------------------\\n`;
            cart.forEach(i => {
                message += `${i.name} (${i.qty}) = ${i.price * i.qty} ريال\\n`;
            });
            message += `------------------------\\n`;
            message += `*الإجمالي: ${document.getElementById('cart-total').innerText} ريال*`;

            const url = `https://wa.me/967770295876?text=${encodeURIComponent(message)}`;
            window.open(url, '_blank');
        }

        function printInvoice() {
            let win = window.open('', '_blank');
            let total = document.getElementById('cart-total').innerText;
            let rows = cart.map(i => `<tr><td>${i.name}</td><td>${i.qty}</td><td>${i.price * i.qty}</td></tr>`).join('');
            
            win.document.write(`
                <html dir="rtl"><head><title>فاتورة</title>
                <style>
                    body { font-family: 'Tajawal', sans-serif; text-align: center; padding: 20px; color: #000; }
                    table { width: 100%; border-collapse: collapse; margin-top: 20px; }
                    th, td { border: 1px solid #000; padding: 10px; }
                    .header { font-size: 24px; font-weight: bold; }
                </style></head>
                <body>
                    <div class="header">سوبر ماركت أولاد قايد محمد</div>
                    <p>الزبون: \${document.getElementById('cust-name').value}</p>
                    <p>الموقع: \${document.getElementById('cust-loc').value}</p>
                    <p>الهاتف: \${document.getElementById('cust-phone').value}</p>
                    <table>
                        <thead><tr><th>المنتج</th><th>الكمية</th><th>السعر</th></tr></thead>
                        <tbody>\${rows}</tbody>
                    </table>
                    <h3>الإجمالي: \${total} ريال</h3>
                </body></html>
            `);
            win.document.close();
            win.print();
        }
    </script>
</body>
</html>
"""

# واجهة لوحة التحكم (المدير)
ADMIN_UI = """
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>لوحة التحكم - الإدارة</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style> body { font-family: 'Tajawal', sans-serif; background: #f4f4f4; } </style>
</head>
<body class="p-4 max-w-4xl mx-auto">
    <div class="flex justify-between items-center mb-8">
        <h1 class="text-2xl font-bold">إدارة السوبر ماركت</h1>
        <a href="/" class="bg-blue-600 text-white px-4 py-2 rounded">عرض واجهة الزبون</a>
    </div>

    <!-- إضافة فئة -->
    <section class="bg-white p-6 rounded-lg shadow-md mb-8">
        <h2 class="text-xl font-bold mb-4">إضافة فئة جديدة</h2>
        <form action="/admin/add_category" method="POST" class="flex gap-2">
            <input type="text" name="name" placeholder="اسم الفئة (مثلاً: بهارات)" class="flex-1 border p-2 rounded" required>
            <button class="bg-green-600 text-white px-6 py-2 rounded font-bold">إضافة</button>
        </form>
        <div class="mt-4 flex flex-wrap gap-2">
            {% for cat in categories %}
            <span class="bg-gray-200 px-3 py-1 rounded-full flex items-center gap-2">
                {{cat.name}}
                <a href="/admin/del_category/{{cat.id}}" class="text-red-500 font-bold">×</a>
            </span>
            {% endfor %}
        </div>
    </section>

    <!-- إضافة منتج -->
    <section class="bg-white p-6 rounded-lg shadow-md">
        <h2 class="text-xl font-bold mb-4">إضافة منتج جديد</h2>
        <form action="/admin/add_product" method="POST" class="grid grid-cols-1 md:grid-cols-2 gap-4">
            <select name="category_id" class="border p-2 rounded" required>
                <option value="">اختر الفئة</option>
                {% for cat in categories %}
                <option value="{{cat.id}}">{{cat.name}}</option>
                {% endfor %}
            </select>
            <input type="text" name="name" placeholder="اسم المنتج" class="border p-2 rounded" required>
            <input type="number" name="price" placeholder="السعر" step="0.01" class="border p-2 rounded" required>
            <input type="text" name="quantity" placeholder="الوصف/الكمية (مثلاً: كيس 1كجم)" class="border p-2 rounded">
            <button class="bg-blue-600 text-white px-6 py-3 rounded font-bold col-span-full">إضافة المنتج للقائمة</button>
        </form>
    </section>

    <section class="mt-8 bg-white p-6 rounded-lg shadow-md overflow-x-auto">
        <h2 class="text-xl font-bold mb-4">قائمة المنتجات الحالية</h2>
        <table class="w-full text-right border-collapse">
            <thead>
                <tr class="bg-gray-100">
                    <th class="p-2 border">المنتج</th>
                    <th class="p-2 border">الفئة</th>
                    <th class="p-2 border">السعر</th>
                    <th class="p-2 border">إجراءات</th>
                </tr>
            </thead>
            <tbody>
                {% for prod in products %}
                <tr>
                    <td class="p-2 border">{{prod.name}}</td>
                    <td class="p-2 border">{{prod.cat_name}}</td>
                    <td class="p-2 border">{{prod.price}} ريال</td>
                    <td class="p-2 border text-red-600">
                        <a href="/admin/del_product/{{prod.id}}">حذف</a>
                    </td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
    </section>
</body>
</html>
"""

# --- المسارات (Routes) ---

@app.route('/')
def index():
    db = get_db()
    categories = db.execute("SELECT * FROM categories").fetchall()
    # جلب المنتجات مع اسم الفئة
    products = db.execute('''SELECT p.*, c.name as cat_name FROM products p 
                             JOIN categories c ON p.category_id = c.id''').fetchall()
    return render_template_string(CUSTOMER_UI, categories=categories, products=products)

@app.route('/admin')
def admin():
    db = get_db()
    categories = db.execute("SELECT * FROM categories").fetchall()
    products = db.execute('''SELECT p.*, c.name as cat_name FROM products p 
                             JOIN categories c ON p.category_id = c.id''').fetchall()
    return render_template_string(ADMIN_UI, categories=categories, products=products)

# عمليات المدير
@app.route('/admin/add_category', methods=['POST'])
def add_category():
    name = request.form.get('name')
    if name:
        db = get_db()
        try:
            db.execute("INSERT INTO categories (name) VALUES (?)", (name,))
            db.commit()
        except: pass
    return redirect(url_for('admin'))

@app.route('/admin/del_category/<int:id>')
def del_category(id):
    db = get_db()
    db.execute("DELETE FROM categories WHERE id = ?", (id,))
    db.commit()
    return redirect(url_for('admin'))

@app.route('/admin/add_product', methods=['POST'])
def add_product():
    cat_id = request.form.get('category_id')
    name = request.form.get('name')
    price = request.form.get('price')
    qty = request.form.get('quantity')
    if cat_id and name and price:
        db = get_db()
        db.execute("INSERT INTO products (category_id, name, price, quantity) VALUES (?, ?, ?, ?)", 
                   (cat_id, name, price, qty))
        db.commit()
    return redirect(url_for('admin'))

@app.route('/admin/del_product/<int:id>')
def del_product(id):
    db = get_db()
    db.execute("DELETE FROM products WHERE id = ?", (id,))
    db.commit()
    return redirect(url_for('admin'))

if __name__ == '__main__':
    app.run(debug=True, port=5000)

