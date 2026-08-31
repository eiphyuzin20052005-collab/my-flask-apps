from flask import Flask, render_template
from db import get_connection

app = Flask(__name__)


@app.route("/admin/users")
def users():

    db = get_connection()
    cursor = db.cursor( )

    cursor.execute("SELECT user_id, name, email, password, role FROM users")

    users = cursor.fetchall()

    cursor.close()
    db.close()

    return render_template("admindashboard.html", users=users)


if __name__ == "__main__":
    app.run(debug=True, port=5001)