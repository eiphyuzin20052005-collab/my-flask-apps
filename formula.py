from flask import Flask, render_template, request, jsonify
import mysql.connector
from equation_converter import format_question, convert_equation

app = Flask(__name__)

# Jinja Filter
app.jinja_env.filters["format_math"] = convert_equation


def get_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="root",
        database="MPS"
    )


@app.route("/")
def home():
    db = get_connection()
    cursor = db.cursor(dictionary=True)

    cursor.execute("SELECT * FROM categories")
    categories = cursor.fetchall()

    cursor.close()
    db.close()

    return render_template("hm.html", categories=categories)


@app.route("/category/<int:id>")
def category_page(id):

    db = get_connection()
    cursor = db.cursor()

    cursor.execute(
        "SELECT category_name, level FROM categories WHERE category_id=%s",
        (id,)
    )

    row = cursor.fetchone()

    category = None

    if row:
        category = {
            "category_name": row[0],
            "level": row[1]
        }

    cursor.execute(
        """
        SELECT formula_name, latex_formula
        FROM formulas
        WHERE category_id=%s
        """,
        (id,)
    )

    formulas = []

    for r in cursor.fetchall():
        formulas.append({
            "formula_name": r[0],
            "latex_formula": r[1]
        })

    cursor.execute(
        """
        SELECT problem_id,question_text
        FROM problems
        WHERE category_id=%s
        """,
        (id,)
    )

    problems = []

    for p in cursor.fetchall():

        pid = p[0]
        question = p[1]

        cursor.execute(
            """
            SELECT step_text
            FROM rules
            WHERE problem_id=%s
            ORDER BY rule_id
            """,
            (pid,)
        )

        steps = "\n".join([x[0] for x in cursor.fetchall()])

        problems.append({

            "problem_id": pid,

            # Question ကို convert မလုပ်သေး
            "question": question,

            # Step ကို convert လုပ်
            "steps": convert_equation(steps)

        })

    cursor.close()
    db.close()

    return render_template(
        "category-detail.html",
        category=category,
        formulas=formulas,
        problems=problems
    )


# ၁။ User ကို Registration ပထမဆုံးလုပ်ချိန်တွင် Database ထဲထည့်၍ user_id ပြန်ထုတ်ပေးသည့် API
@app.route("/api/register-user", methods=["POST"])
def register_user():
    try:
        data = request.get_json()
        user_name = data.get("user_name")
        user_class = data.get("user_class")

        db = get_connection()
        cursor = db.cursor()

        sql = "INSERT INTO users (user_name, user_class) VALUES (%s, %s)"
        cursor.execute(sql, (user_name, user_class))
        db.commit()

        user_id = cursor.lastrowid  # ထွက်လာသည့် user_id ကို ယူခြင်း

        cursor.close()
        db.close()

        return jsonify({"status": "success", "user_id": user_id}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# ၂။ Step တိုင်းအတွက် ရှိပြီးသား user_id ဖြင့်သာ Answer သိမ်းပေးသည့် API
@app.route("/api/save-user-data", methods=["POST"])
def save_user_data():
    try:
        data = request.get_json()
        user_id = data.get("user_id")
        problem_id = data.get("problem_id")
        user_answer = data.get("user_answer", "")
        status = data.get("status")

        db = get_connection()
        cursor = db.cursor()

        sql = """
            INSERT INTO user_answers (user_id, problem_id, user_answer, status)
            VALUES (%s, %s, %s, %s)
        """
        cursor.execute(sql, (user_id, problem_id, user_answer, status))
        db.commit()

        cursor.close()
        db.close()

        return jsonify({"status": "success", "message": "User data saved successfully"}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


if __name__ == "__main__":
    app.run(debug=True, port=5000)