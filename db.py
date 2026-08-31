import pymysql

def get_connection():
    return pymysql.connect(
        host="zephyr.proxy.rlwy.net",
        user="root",
        password="SRngbIgSRqxoCuyViFrQNbericfRpos",
        database="railway",
        port=45336
    )