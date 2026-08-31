from flask import Flask, render_template, request, redirect, session, jsonify
from db import get_connection
import pymysql
from equation_converter import convert_equation
from sympy import parse_expr, simplify, solve, Symbol
import re
import random
import os
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = "mathsolver_secret_key_here"

# Profile Upload Configurations
UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.template_filter('format_math')
def format_math_filter(text):
    return convert_equation(text)

@app.route("/")
def home():
    conn = get_connection()
    cursor = conn.cursor(pymysql.cursors.DictCursor)

    cursor.execute("SELECT COUNT(*) AS count FROM users")
    total_students = cursor.fetchone()['count']

    cursor.execute("SELECT COUNT(*) AS count FROM problems")
    total_problems = cursor.fetchone()['count']

    cursor.execute("SELECT COUNT(*) AS count FROM categories")
    total_categories = cursor.fetchone()['count']

    cursor.execute("SELECT * FROM categories")
    categories = cursor.fetchall()

    cursor.execute("""
        SELECT p.problem_id, p.question_text, c.category_name, COUNT(DISTINCT ua.user_id) AS solve_count
        FROM problems p
        LEFT JOIN user_answers ua ON p.problem_id = ua.problem_id AND ua.status = 'Correct'
        LEFT JOIN categories c ON p.category_id = c.category_id
        GROUP BY p.problem_id, p.question_text, c.category_name
        ORDER BY solve_count DESC
        LIMIT 5
    """)
    top_problems = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template(
        "hm.html",
        categories=categories,
        top_problems=top_problems,
        total_students=total_students,
        total_problems=total_problems,
        total_categories=total_categories
    )

# ================= CATEGORY DETAIL ROUTE =================
@app.route("/category/<int:category_id>")
def category_detail(category_id):
    conn = get_connection()
    cursor = conn.cursor(pymysql.cursors.DictCursor)

    cursor.execute("SELECT * FROM categories WHERE category_id = %s", (category_id,))
    category = cursor.fetchone()

    cursor.execute("""
        SELECT p.problem_id, p.question_text, p.category_id,
               GROUP_CONCAT(r.step_text ORDER BY r.rule_id SEPARATOR '\n') AS steps
        FROM problems p
        LEFT JOIN rules r ON p.problem_id = r.problem_id
        WHERE p.category_id = %s
        GROUP BY p.problem_id, p.question_text, p.category_id
    """, (category_id,))
    problems = cursor.fetchall()

    cursor.execute("SELECT * FROM formulas WHERE category_id = %s", (category_id,))
    formulas = cursor.fetchall()

    cursor.close()
    conn.close()

    if not category:
        return "Category Not Found", 404

    return render_template("category-detail.html", category=category, problems=problems, formulas=formulas)

# ================= STUDENT PRACTICE API ROUTES =================
@app.route("/api/register-user", methods=["POST"])
def register_user():
    data = request.get_json()
    user_name = data.get("user_name")
    email = data.get("email")
    user_class = data.get("user_class")

    conn = get_connection()
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    
    cursor.execute("SELECT user_id FROM users WHERE email = %s", (email,))
    existing_user = cursor.fetchone()

    if existing_user:
        user_id = existing_user['user_id']
        cursor.execute("UPDATE users SET user_name=%s, user_class=%s WHERE user_id=%s", (user_name, user_class, user_id))
        conn.commit()
    else:
        cursor.execute("INSERT INTO users (user_name, email, user_class) VALUES (%s, %s, %s)", (user_name, email, user_class))
        conn.commit()
        user_id = cursor.lastrowid

    cursor.close()
    conn.close()

    session['user_logged_in'] = True
    session['user_id'] = user_id
    session['user_email'] = email

    return jsonify({"status": "success", "user_id": user_id})

@app.route("/api/save-user-data", methods=["POST"])
def save_user_data():
    data = request.get_json()
    user_id = data.get("user_id")
    email = data.get("email")
    problem_id = data.get("problem_id")
    user_answer = data.get("user_answer")
    status = data.get("status")

    conn = get_connection()
    cursor = conn.cursor()

    if not user_id and email:
        cursor_dict = conn.cursor(pymysql.cursors.DictCursor)
        cursor_dict.execute("SELECT user_id FROM users WHERE email = %s", (email,))
        u = cursor_dict.fetchone()
        if u:
            user_id = u['user_id']
        cursor_dict.close()

    if user_id:
        cursor.execute("""
            INSERT INTO user_answers (user_id, problem_id, user_answer, status)
            VALUES (%s, %s, %s, %s)
        """, (user_id, problem_id, user_answer, status))
        conn.commit()

    cursor.close()
    conn.close()

    return jsonify({"status": "success"})

# ================= USER PROFILE & PRACTICE HISTORY API (DUPLICATE FIX) =================
@app.route("/api/get-user-history", methods=["GET"])
def get_user_history():
    email = request.args.get("email")
    if not email:
        return jsonify({"status": "error", "message": "Email is required"}), 400

    conn = get_connection()
    cursor = conn.cursor(pymysql.cursors.DictCursor)

    # DISTINCT Subquery မသုံးဘဲ MAX(answer_id) ဖြင့် ပုစ္ဆာတစ်ပုဒ်ကို ၁ ခါပဲ ပေါ်အောင် Group လုပ်ထားခြင်း
    cursor.execute("""
        SELECT latest_ua.answer_id, latest_ua.user_answer, latest_ua.status, latest_ua.created_at AS solved_at,
               p.question_text, c.category_name,
               (
                   SELECT GROUP_CONCAT(r.step_text ORDER BY r.rule_id SEPARATOR '\n')
                   FROM rules r WHERE r.problem_id = p.problem_id
               ) AS full_solution
        FROM (
            SELECT MAX(ua.answer_id) as last_answer_id
            FROM user_answers ua
            JOIN users u ON ua.user_id = u.user_id
            WHERE u.email = %s
            GROUP BY ua.problem_id
        ) unique_problems
        JOIN user_answers latest_ua ON unique_problems.last_answer_id = latest_ua.answer_id
        JOIN problems p ON latest_ua.problem_id = p.problem_id
        LEFT JOIN categories c ON p.category_id = c.category_id
        ORDER BY latest_ua.created_at DESC
    """, (email,))
    
    history = cursor.fetchall()
    cursor.close()
    conn.close()

    return jsonify({"status": "success", "history": history})

@app.route("/api/upload-profile-photo", methods=["POST"])
def upload_profile_photo():
    if 'photo' not in request.files:
        return jsonify({"status": "error", "message": "No file uploaded"}), 400
    
    file = request.files['photo']
    email = request.form.get("email")

    if file.filename == '':
        return jsonify({"status": "error", "message": "No selected file"}), 400

    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        unique_filename = f"{email.replace('@', '_').replace('.', '_')}_{filename}"
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
        file.save(file_path)

        photo_url = f"/{file_path}"

        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("UPDATE users SET photo_url = %s WHERE email = %s", (photo_url, email))
            conn.commit()
        except Exception as e:
            conn.rollback()
        finally:
            cursor.close()
            conn.close()

        return jsonify({"status": "success", "photo_url": photo_url})

    return jsonify({"status": "error", "message": "Invalid file format"}), 400

# ================= MATH EVALUATOR API =================
@app.route("/api/evaluate-user-step", methods=["POST"])
def evaluate_user_step():
    data = request.get_json()
    user_input = data.get("user_answer", "").strip()
    expected_step = data.get("expected_step", "").strip()

    if not user_input:
        return jsonify({"is_correct": False, "message": "Please enter your step/answer first."})

    try:
        def clean_math_string(expr_str):
            s = re.sub(r'\\frac\{([^}]+)\}\{([^}]+)\}', r'((\1)/(\2))', expr_str)
            s = s.replace('\\cdot', '*').replace('^', '**')
            s = re.sub(r'\\[a-zA-Z]+', '', s)
            s = re.sub(r'[\$\{\}]', '', s)
            return s.strip()

        u_clean = clean_math_string(user_input)
        e_clean = clean_math_string(expected_step)

        if '=' in u_clean and '=' in e_clean:
            u_lhs, u_rhs = u_clean.split('=')
            e_lhs, e_rhs = e_clean.split('=')
            u_diff = simplify(parse_expr(u_lhs) - parse_expr(u_rhs))
            e_diff = simplify(parse_expr(e_lhs) - parse_expr(e_rhs))
            is_valid = (simplify(u_diff - e_diff) == 0) or (simplify(u_diff + e_diff) == 0)
        else:
            u_expr = parse_expr(u_clean)
            e_expr = parse_expr(e_clean)
            is_valid = simplify(u_expr - e_expr) == 0

        if is_valid:
            return jsonify({"is_correct": True, "message": "Step verified and mathematically valid!"})
        else:
            return jsonify({"is_correct": False, "message": "Incorrect for the current step."})

    except Exception:
        u_norm = re.sub(r'\s+', '', user_input.lower())
        e_norm = re.sub(r'\s+', '', expected_step.lower())
        if u_norm in e_norm or e_norm in u_norm:
            return jsonify({"is_correct": True, "message": "Step verified!"})
        return jsonify({"is_correct": False, "message": "Incorrect mathematical format or step."})

@app.route("/api/generate-random-variant", methods=["POST"])
def generate_random_variant():
    data = request.get_json()
    q_text = data.get("question_text", "")
    steps_text = data.get("steps_text", "")

    numbers = re.findall(r'\b\d+\b', q_text)
    new_q = q_text
    new_steps = steps_text

    if numbers:
        for num in set(numbers):
            if int(num) > 0:
                rand_val = str(random.randint(2, 20))
                new_q = re.sub(r'\b' + num + r'\b', rand_val, new_q)
                new_steps = re.sub(r'\b' + num + r'\b', rand_val, new_steps)

    return jsonify({
        "status": "success",
        "new_question": new_q,
        "new_steps": new_steps.split("\n")
    })

# ================= UNIFIED LOGIN & PROFILE ROUTES =================
@app.route("/login", methods=["POST"])
def unified_login():
    role = request.form.get("role")
    email = request.form.get("email")

    conn = get_connection()
    cursor = conn.cursor(pymysql.cursors.DictCursor)

    if role == "admin":
        name = request.form.get("name")
        password = request.form.get("password")
        cursor.execute("""
            SELECT * FROM admin 
            WHERE admin_name = %s AND email = %s AND password = %s
        """, (name, email, password))
        admin = cursor.fetchone()
        cursor.close()
        conn.close()

        if admin:
            session['admin_logged_in'] = True
            session['admin_name'] = name
            return redirect("/admin")
        else:
            return "<script>alert('Invalid Admin Name, Email, or Password!'); window.location.href='/';</script>"
    
    else: # Student User Login
        cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
        user = cursor.fetchone()
        cursor.close()
        conn.close()

        if user:
            session['user_logged_in'] = True
            session['user_id'] = user['user_id']
            session['user_email'] = user['email']
            return redirect(f"/user/profile/{user['user_id']}")
        else:
            return "<script>alert('No account found with this Email! Please practice first to register.'); window.location.href='/';</script>"

@app.route("/user/profile/<int:user_id>")
def user_profile(user_id):
    if not session.get('user_logged_in') or session.get('user_id') != user_id:
        return redirect("/")

    conn = get_connection()
    cursor = conn.cursor(pymysql.cursors.DictCursor)

    cursor.execute("SELECT * FROM users WHERE user_id = %s", (user_id,))
    user_info = cursor.fetchone()

    cursor.close()
    conn.close()

    return render_template("user_profile.html", user=user_info)

@app.route("/user/logout")
def user_logout():
    session.pop('user_logged_in', None)
    session.pop('user_id', None)
    session.pop('user_email', None)
    return redirect("/")

@app.route("/admin/login", methods=["POST"])
def admin_login():
    name = request.form.get("name")
    email = request.form.get("email")
    password = request.form.get("password")

    conn = get_connection()
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    cursor.execute("""
        SELECT * FROM admin 
        WHERE admin_name = %s AND email = %s AND password = %s
    """, (name, email, password))
    admin = cursor.fetchone()
    cursor.close()
    conn.close()

    if admin:
        session['admin_logged_in'] = True
        session['admin_name'] = name
        return redirect("/admin")
    else:
        return "<script>alert('Invalid Admin Name, Email, or Password!'); window.location.href='/';</script>"

@app.route("/admin/logout")
def admin_logout():
    session.pop('admin_logged_in', None)
    session.pop('admin_name', None)
    return redirect("/")

@app.route("/admin")
def admin():
    if not session.get('admin_logged_in'):
        return redirect("/")

    conn = get_connection()
    cursor = conn.cursor(pymysql.cursors.DictCursor)

    cursor.execute("SELECT user_id, user_name, user_class, created_at FROM users")
    users = cursor.fetchall()

    cursor.execute("SELECT * FROM categories")
    categories = cursor.fetchall()

    cursor.execute("SELECT * FROM problems")
    problems = cursor.fetchall()

    cursor.execute("SELECT * FROM formulas")
    formulas = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template(
        "admin.html",
        users=users,
        categories=categories,
        problems=problems,
        formulas=formulas,
        total_users=len(users),
        total_categories=len(categories),
        total_problems=len(problems),
        total_formulas=len(formulas)
    )

@app.route("/admin/profile")
def admin_profile():
    if not session.get('admin_logged_in'):
        return redirect("/")

    conn = get_connection()
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    cursor.execute("SELECT * from admin")
    admin = cursor.fetchone()
    cursor.close()
    conn.close()

    return render_template("admin_profile.html", admin=admin)

# ================= USER ROUTES =================
@app.route("/delete_user/<int:user_id>", methods=["POST"])
def delete_user(user_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM users WHERE user_id=%s", (user_id,))
    conn.commit()
    cursor.close()
    conn.close()
    return "", 200

# ================= CATEGORY ROUTES =================
@app.route("/add_category", methods=["GET", "POST"])
def add_category():
    if not session.get('admin_logged_in'):
        return redirect("/")

    if request.method == "POST":
        category_name = request.form.get("category_name")
        level = request.form.get("level")

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO categories (category_name, level) VALUES (%s, %s)",
            (category_name, level)
        )
        conn.commit()
        cursor.close()
        conn.close()

        return redirect("/admin#categories")

    return render_template("addcategories.html")

@app.route("/edit_category/<int:category_id>", methods=["GET", "POST"])
def edit_category(category_id):
    if not session.get('admin_logged_in'):
        return redirect("/")

    conn = get_connection()
    cursor = conn.cursor(pymysql.cursors.DictCursor)

    if request.method == "POST":
        category_name = request.form.get("category_name")
        level = request.form.get("category_level") or request.form.get("level")

        cursor.execute("""
            UPDATE categories
            SET category_name=%s, level=%s
            WHERE category_id=%s
        """, (category_name, level, category_id))
        conn.commit()
        cursor.close()
        conn.close()
        return redirect("/admin#categories")

    cursor.execute("SELECT * FROM categories WHERE category_id=%s", (category_id,))
    category = cursor.fetchone()
    cursor.close()
    conn.close()

    return render_template("edit_categories.html", category=category)

@app.route("/delete_category/<int:category_id>", methods=["POST"])
def delete_category(category_id):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM categories WHERE category_id=%s", (category_id,))
        conn.commit()
        cursor.close()
        conn.close()
        return "", 200
    except Exception as e:
        conn.rollback()
        cursor.close()
        conn.close()
        return str(e), 500

# ================= FORMULA ROUTES =================
@app.route("/add_formula", methods=["GET", "POST"])
def add_formula():
    if not session.get('admin_logged_in'):
        return redirect("/")

    conn = get_connection()
    cursor = conn.cursor(pymysql.cursors.DictCursor)

    if request.method == "POST":
        category_id = request.form.get("category_id")
        formula_name = request.form.get("formula_name")
        latex_formula = request.form.get("formula_text") or request.form.get("latex_formula")

        cursor.execute(
            "INSERT INTO formulas (category_id, formula_name, latex_formula) VALUES (%s, %s, %s)",
            (category_id, formula_name, latex_formula)
        )
        conn.commit()
        cursor.close()
        conn.close()

        return redirect("/admin#formulas")

    cursor.execute("SELECT * FROM categories")
    categories = cursor.fetchall()
    cursor.close()
    conn.close()

    return render_template("addformulas.html", categories=categories)

@app.route("/delete_formula/<int:formula_id>", methods=["POST"])
def delete_formula(formula_id):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM formulas WHERE formula_id=%s", (formula_id,))
        conn.commit()
        cursor.close()
        conn.close()
        return "", 200
    except Exception as e:
        conn.rollback()
        cursor.close()
        conn.close()
        return str(e), 500

# ================= PROBLEM ROUTES =================
@app.route("/add_problem", methods=["GET", "POST"])
def add_problem():
    if not session.get('admin_logged_in'):
        return redirect("/")

    conn = get_connection()
    cursor = conn.cursor(pymysql.cursors.DictCursor)

    if request.method == "POST":
        category_id = request.form["category_id"]
        question = request.form["question_text"]
        steps_text = request.form.get("steps", "")
        steps = steps_text.split("\n")

        cursor.execute("""
            INSERT INTO problems (category_id, question_text)
            VALUES (%s, %s)
        """, (category_id, question))

        problem_id = cursor.lastrowid

        for step in steps:
            if step.strip() != "":
                cursor.execute("""
                    INSERT INTO rules (problem_id, step_text)
                    VALUES (%s, %s)
                """, (problem_id, step.strip()))

        conn.commit()
        cursor.close()
        conn.close()

        return redirect("/admin#problems")

    cursor.execute("SELECT * FROM categories")
    categories = cursor.fetchall()
    cursor.close()
    conn.close()

    return render_template("addproblem.html", categories=categories)

@app.route("/edit_problem/<int:problem_id>", methods=["GET", "POST"])
def edit_problem(problem_id):
    if not session.get('admin_logged_in'):
        return redirect("/")

    conn = get_connection()
    cursor = conn.cursor(pymysql.cursors.DictCursor)

    if request.method == "POST":
        question = request.form.get("question_text") or request.form.get("question")

        cursor.execute("""
            UPDATE problems
            SET question_text=%s
            WHERE problem_id=%s
        """, (question, problem_id))

        conn.commit()
        cursor.close()
        conn.close()

        return redirect("/admin#problems")

    cursor.execute("SELECT * FROM problems WHERE problem_id=%s", (problem_id,))
    problem = cursor.fetchone()
    cursor.close()
    conn.close()

    return render_template("edit_problem.html", problem=problem)

@app.route("/delete_problem/<int:problem_id>", methods=["POST"])
def delete_problem(problem_id):
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("DELETE FROM rules WHERE problem_id=%s", (problem_id,))
        cursor.execute("DELETE FROM user_answers WHERE problem_id=%s", (problem_id,))
        cursor.execute("DELETE FROM problems WHERE problem_id=%s", (problem_id,))

        conn.commit()
        cursor.close()
        conn.close()
        return "", 200

    except Exception as e:
        conn.rollback()
        cursor.close()
        conn.close()
        return str(e), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0" , port=5000, debug=True)