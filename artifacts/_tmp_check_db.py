import mysql.connector as mc

conn = mc.connect(host="localhost", user="root", password="password123", database="moonlight_rpg")
cur = conn.cursor()
cur.execute("SHOW TABLES LIKE 'location'")
print("location_table_exists:", bool(cur.fetchone()))
cur.execute("SHOW TABLES")
rows = cur.fetchall()
print("table_count:", len(rows))
cur.close()
conn.close()
