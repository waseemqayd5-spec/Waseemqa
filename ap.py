from flask import Flask, render_template_string, request, redirect, session
import sqlite3
import os

app = Flask(__name__)
app.secret_key = "supermarket_secret"

DB = "store.db"

def db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

def init():
    conn = db()

    conn.execute("""
    CREATE TABLE IF NOT EXISTS products(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        price REAL,
        qty INTEGER
    )
    """)

    conn.commit()
    conn.close()

init()

# تصميم اسود ذهبي
STYLE = """
<style>

body{
background:#000;
color:#d4af37;
font-family:Arial;
text-align:center;
}

table{
width:80%;
margin:auto;
border-collapse:collapse;
}

th,td{
border:1px solid #d4af37;
padding:10px;
}

button{
background:#d4af37;
border:none;
padding:10px;
margin:5px;
}

input{
padding:8px;
margin:5px;
}

a{
color:#d4af37;
}

</style>
"""

# تسجيل الدخول
@app.route("/", methods=["GET","POST"])
def login():

    if request.method == "POST":

        if request.form["user"]=="admin" and request.form["pass"]=="1234":
            session["login"]=True
            return redirect("/dashboard")

    return STYLE + """
    <h1>سوبر ماركت أولاد قايد للتجارة العامة</h1>
    <h3>تسجيل دخول المدير</h3>

    <form method=post>

    <input name=user placeholder=اسم المستخدم>
    <br>

    <input name=pass placeholder=كلمة المرور type=password>
    <br>

    <button>دخول</button>

    </form>
    """

# لوحة التحكم
@app.route("/dashboard")
def dash():

    if not session.get("login"):
        return redirect("/")

    conn=db()
    products=conn.execute("SELECT * FROM products").fetchall()

    html="""
    <h1>لوحة التحكم</h1>

    <a href='/add'>اضافة منتج</a>
    <br><br>

    <table>

    <tr>
    <th>المنتج</th>
    <th>السعر</th>
    <th>الكمية</th>
    <th>حذف</th>
    </tr>
    """

    for p in products:
        html+=f"""
        <tr>
        <td>{p['name']}</td>
        <td>{p['price']}</td>
        <td>{p['qty']}</td>
        <td>
        <a href='/delete/{p['id']}'>حذف</a>
        </td>
        </tr>
        """

    html+="</table>"

    return STYLE+html


# إضافة منتج
@app.route("/add",methods=["GET","POST"])
def add():

    if request.method=="POST":

        name=request.form["name"]
        price=request.form["price"]
        qty=request.form["qty"]

        conn=db()

        conn.execute(
        "INSERT INTO products(name,price,qty) VALUES(?,?,?)",
        (name,price,qty)
        )

        conn.commit()

        return redirect("/dashboard")

    return STYLE+"""
    <h2>إضافة منتج</h2>

    <form method=post>

    <input name=name placeholder=اسم المنتج>
    <br>

    <input name=price placeholder=السعر>
    <br>

    <input name=qty placeholder=الكمية>
    <br>

    <button>حفظ</button>

    </form>
    """

# حذف
@app.route("/delete/<id>")
def delete(id):

    conn=db()
    conn.execute("DELETE FROM products WHERE id=?",(id,))
    conn.commit()

    return redirect("/dashboard")

if __name__ == "__main__":
    app.run(host="0.0.0.0",port=10000)
