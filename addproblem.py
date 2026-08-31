from flask import Flask, render_template, request, redirect
from db import get_connection
import pymysql

app = Flask(__name__)

@app.route("/")
def home():
    return redirect("/add_problem")

@app.route("/add_problem", methods=["GET", "POST"])
def add_problem():
    conn = get_connection()
    cursor = conn.cursor(pymysql.cursors.DictCursor)

    if request.method == "POST":
        category_id = request.form["category_id"]
        question = request.form["question_text"]
        
        # text area တစ်ခုတည်းကနေ data ကို string အနေနဲ့ ဖတ်ပြီး line break နဲ့ ခွဲထုတ်ပါတယ်
        steps_text = request.form.get("steps", "")
        steps = steps_text.split("\n")
        
        # ၁။ Problems table ထဲကို အရင် insert လုပ်မယ်
        cursor.execute("""
            INSERT INTO Problems (category_id, question_text)
            VALUES (%s, %s)
        """, (category_id, question))

        # လက်ရှိဝင်သွားတဲ့ ပုစ္ဆာရဲ့ Auto ID ကို ယူမယ်
        problem_id = cursor.lastrowid

        # ၂။ Rules table ထဲကို Plain Text အနေနဲ့ပဲ စစ်ပြီး သွင်းမယ်
        for step in steps:
            cleaned_step = step.strip()
            if cleaned_step:  # စာသားအလွတ်မဟုတ်မှသာ DB ထဲ ထည့်သွင်းမယ်
                cursor.execute("""
                    INSERT INTO rules (problem_id, step_text)
                    VALUES (%s, %s)
                """, (problem_id, cleaned_step))

        conn.commit()
        cursor.close()
        conn.close()

        return redirect("/addproblem")

    # GET Method ဖြစ်လျှင် Categories ဆွဲထုတ်ပြီး Page ပြပေးမယ်
    cursor.execute("""
        SELECT *
        FROM categories
    """)
    categories = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template(
        "addproblem.html",
        categories=categories
    )

if __name__ == "__main__":
    app.run(
        debug=True,
        port=5001
    )