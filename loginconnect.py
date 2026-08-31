from flask import Flask, render_template, request
from db import get_connection
import re

app = Flask(__name__)

# Email Validation Pattern
EMAIL_PATTERN = r'^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$'


# Signup Page
@app.route("/")
def home():
    return render_template("logintest.html")


# Register
@app.route("/register", methods=["POST"])
def register():

    name = request.form["name"].strip()
    email = request.form["email"].strip()
    password = request.form["password"]

    # Empty Validation
    if name == "" or email == "" or password == "":
        return "Please fill all fields."

    # Email Validation
    if not re.match(EMAIL_PATTERN, email):
        return "Invalid Email Format"

    conn = get_connection()
    cursor = conn.cursor()

    # Duplicate Email Check
    cursor.execute("SELECT * FROM users WHERE email=%s", (email,))
    user = cursor.fetchone()

    if user:
        cursor.close()
        conn.close()
        return "Email already exists."

    # Insert User
    sql = """
    INSERT INTO users(name,email,password)
    VALUES(%s,%s,%s)
    """

    cursor.execute(sql, (name, email, password))

    conn.commit()

    cursor.close()
    conn.close()

    return """
    <script>
        alert('Account Created Successfully!');
        window.location.href='/';
    </script>
    """


if __name__ == "__main__":
    app.run(debug=True)