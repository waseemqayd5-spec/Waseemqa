from flask import Flask, render_template_string, request, redirect
import sqlite3
import os

app = Flask(__name__)
DB = "store.db"

# -------------------------
# تهيئة قاعدة البيانات
# -------------------------
def init_db():
    if not os.path.exists(DB):
        conn = sqlite3.connect(DB)
        c = conn.cursor()
        c.execute("""
        CREATE TABLE categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT
        )""")
        c.execute("""
        CREATE TABLE products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            price REAL,
            category_id INTEGER,
            FOREIGN KEY(category_id) REFERENCES categories(id)
        )""")
        conn.commit()
        conn.close()

init_db()

# -------------------------
# الصفحة الرئيسية (واجهة الزبون)
# -------------------------
@app.route("/", methods=["GET"])
def home():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("SELECT * FROM categories")
    categories = c.fetchall()
    
    products_by_category = {}
    for cat in categories:
        c.execute("SELECT * FROM products WHERE category_id=?", (cat[0],))
        products_by_category[cat[0]] = c.fetchall()
    
    conn.close()
    
    return render_template_string(CUSTOMER_TEMPLATE, categories=categories, products_by_category=products_by_category)

# -------------------------
# لوحة المدير لإدارة الفئات والمنتجات
# -------------------------
@app.route("/admin", methods=["GET", "POST"])
def admin():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    
    if request.method == "POST":
        if "category_name" in request.form:
            c.execute("INSERT INTO categories (name) VALUES (?)", (request.form["category_name"],))
        if "product_name" in request.form:
            c.execute("INSERT INTO products (name, price, category_id) VALUES (?,?,?)",
                      (request.form["product_name"], request.form["price"], request.form["category_id"]))
        conn.commit()
    
    c.execute("SELECT * FROM categories")
    categories = c.fetchall()
    
    c.execute("""SELECT products.id, products.name, products.price, categories.name
                 FROM products
                 JOIN categories ON products.category_id = categories.id""")
    products = c.fetchall()
    
    conn.close()
    
    return render_template_string(ADMIN_TEMPLATE, categories=categories, products=products)

# -------------------------
# حذف فئة
# -------------------------
@app.route("/delete_category/<int:id>")
def delete_category(id):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("DELETE FROM categories WHERE id=?", (id,))
    conn.commit()
    conn.close()
    return redirect("/admin")

# -------------------------
# حذف منتج
# -------------------------
@app.route("/delete_product/<int:id>")
def delete_product(id):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("DELETE FROM products WHERE id=?", (id,))
    conn.commit()
    conn.close()
    return redirect("/admin")

# -------------------------
# قالب واجهة الزبون
# -------------------------
CUSTOMER_TEMPLATE = """
<!DOCTYPE html>
<html dir="rtl">
<head>
<meta charset="UTF-8">
<title>سوبر ماركت أولاد قايد</title>
<style>
body{background:#000;color:#FFD700;font-family:Tahoma;margin:0;padding:0}
header{text-align:center;padding:20px}
h1{margin:0}
.category{margin:15px;padding:10px;border:1px solid #FFD700}
.product{display:flex;justify-content:space-between;margin:5px 0}
button{background:#FFD700;color:black;border:none;padding:5px 10px;cursor:pointer}
input{padding:5px;margin:3px 0;width:95%}
footer{text-align:center;margin-top:30px;padding:20px;border-top:1px solid #FFD700;font-size:12px}
</style>
<script>
let cart=[];

function addToCart(name,price){
    cart.push({name:name,price:price});
    alert("تمت الإضافة للسلة");
}

function showInvoice(){
    let customer=document.getElementById("customer").value;
    let phone=document.getElementById("phone").value;
    let location=document.getElementById("location").value;

    if(!customer || !phone || !location){
        alert("يرجى إدخال بياناتك كاملة");
        return;
    }

    let text="🛒 سوبر ماركت أولاد قايد محمد\\n";
    text+="الاسم: "+customer+"\\n";
    text+="الرقم: "+phone+"\\n";
    text+="الموقع: "+location+"\\n\\n";

    let total=0;
    cart.forEach(item=>{
        text+=item.name+" - "+item.price+" ريال\\n";
        total+=parseFloat(item.price);
    });
    text+="\\nالإجمالي: "+total+" ريال";

    window.open("https://wa.me/967770295876?text="+encodeURIComponent(text));
}
</script>
</head>
<body>

<header>
<h1>سوبر ماركت أولاد قايد محمد</h1>
<p>أولاد قايد للتجارة العامة</p>
</header>

<div style="padding:15px">

{% for cat in categories %}
<div class="category">
<h3>{{cat[1]}}</h3>
{% for p in products_by_category[cat[0]] %}
<div class="product">
<span>{{p[1]}} - {{p[2]}} ريال</span>
<button onclick="addToCart('{{p[1]}}','{{p[2]}}')">إضافة</button>
</div>
{% endfor %}
</div>
{% endfor %}

<h3>بيانات الزبون</h3>
<input id="customer" placeholder="اسمك"><br>
<input id="phone" placeholder="رقمك"><br>
<input id="location" placeholder="موقعك"><br><br>

<button onclick="showInvoice()">ارسال الى واتساب</button>

</div>

<footer>
📍 الازرق / موعد حماده : حبيل تود<br>
لصاحبها «فايز / وإخوانه»<br>
إعداد وتصميم «م / وسيم العامري»<br>
للتواصل 967770295876
</footer>

</body>
</html>
"""

# -------------------------
# قالب لوحة المدير
# -------------------------
ADMIN_TEMPLATE = """
<!DOCTYPE html>
<html dir="rtl">
<head>
<meta charset="UTF-8">
<title>لوحة المدير</title>
<style>input, select{margin:5px;padding:5px}</style>
</head>
<body>
<h2>إضافة فئة</h2>
<form method="POST">
<input name="category_name" placeholder="اسم الفئة">
<button>إضافة</button>
</form>

<h2>إضافة منتج</h2>
<form method="POST">
<input name="product_name" placeholder="اسم المنتج">
<input name="price" placeholder="السعر">
<select name="category_id">
{% for c in categories %}
<option value="{{c[0]}}">{{c[1]}}</option>
{% endfor %}
</select>
<button>إضافة</button>
</form>

<h2>الفئات</h2>
{% for c in categories %}
{{c[1]}} <a href="/delete_category/{{c[0]}}">حذف</a><br>
{% endfor %}

<h2>المنتجات</h2>
{% for p in products %}
{{p[1]}} - {{p[2]}} ريال ({{p[3]}})
<a href="/delete_product/{{p[0]}}">حذف</a><br>
{% endfor %}
</body>
</html>
"""

# -------------------------
# تشغيل التطبيق
# -------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
