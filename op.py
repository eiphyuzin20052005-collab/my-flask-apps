from flask import Flask, render_template
from db import get_connection
from equation_converter import convert_equation, convert_question
app = Flask(__name__)


@app.route("/")
def home():

    db = get_connection()
    cursor = db.cursor()


    cursor.execute("""
        SELECT 
        problem_id,
        question_text,
        category_id
        FROM problems
    """)


    problems = cursor.fetchall()


    all_data = []


    for p in problems:


        cursor.execute("""
            SELECT step_text
            FROM rules
            WHERE problem_id = %s
        """, (p[0],))


        steps = [
            row[0]
            for row in cursor.fetchall()
        ]


        # combine all steps
        steps_text = "\n".join(steps)



        all_data.append({

    "question":
        convert_question(p[1]),

    "steps":
        convert_equation(steps_text)

    

})



    cursor.close()
    db.close()


    return render_template(
        "P.html",
        problems=all_data
    )



if __name__ == "__main__":
    app.run(
        debug=True,
        port=5001
    )