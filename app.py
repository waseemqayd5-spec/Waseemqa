from flask import Flask, render_template_string
import random

app = Flask(__name__)

devices = []

def fake_scan():
    global devices

    sample = [
        {"ip": "192.168.1.2", "mac": "AA:BB:CC:11:22:33"},
        {"ip": "192.168.1.5", "mac": "DD:EE:FF:44:55:66"},
        {"ip": "192.168.1.7", "mac": "11:22:33:44:55:77"}
    ]

    devices = random.sample(sample, k=len(sample))


@app.route("/")
def home():

    fake_scan()

    html = """
    <html>
    <head>
    <title>AI Network Monitor</title>
    </head>

    <body style="font-family:Arial">

    <h2>Network Monitor Dashboard</h2>

    <table border=1 cellpadding=10>

    <tr>
    <th>IP Address</th>
    <th>MAC Address</th>
    </tr>

    {% for d in devices %}

    <tr>
    <td>{{d.ip}}</td>
    <td>{{d.mac}}</td>
    </tr>

    {% endfor %}

    </table>

    </body>
    </html>
    """

    return render_template_string(html, devices=devices)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
