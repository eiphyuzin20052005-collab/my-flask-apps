from flask import *
from admin import get_connection

@app.route("/edit_problem/<int:problem_id>", methods=["GET", "POST"])
def edit_problem(problem_id):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    if request.method == "POST":
        question = request.form["question"]
        answer = request.form["answer"]

        cursor.execute("""
            UPDATE Problems
            SET question_text=%s,
                final_answer=%s
            WHERE problem_id=%s
        """, (question, answer, problem_id))

        conn.commit()
        cursor.close()
        conn.close()

        return redirect("/admin/problems")

    cursor.execute(
        "SELECT * FROM Problems WHERE problem_id=%s",
        (problem_id,)
    )
    problem = cursor.fetchone()

    cursor.close()
    conn.close()

    return render_template("edit_problem.html", problem=problem)


@app.route("/delete_problem/<int:problem_id>", methods=["POST"])
def delete_problem(problem_id):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "DELETE FROM Problems WHERE problem_id=%s",
        (problem_id,)
    )
    conn.commit()

    cursor.close()
    conn.close()

    return redirect("/admin/problems")