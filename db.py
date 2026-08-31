import pymysql

def get_connection():
    return pymysql.connect(
        host="mysql.railway.internal",
        user="root",
        password="SRngbIgSRqxoCuyVZiFrQNbericfRpos",
        database="railway",
        port=3306
    )