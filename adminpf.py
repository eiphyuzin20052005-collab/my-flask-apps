from flask import Flask, app, render_template,request, redirect

from admin import get_connection
@app.route('/admin/profile')
def admin_profile():

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        select admin_id,usename,password from admin
    """)

    admin = cursor.fetchone()

    cursor.close()
    conn.close()

    return render_template(
        "admin_profile.html",
        admin=admin
    )