import pymysql

# Coba login root dengan beberapa kemungkinan umum atau input manual
pwds = ["", "root", "admin", "123456"]
connected = False

for pwd in pwds:
    try:
        conn = pymysql.connect(host='localhost', port=3306, user='root', password=pwd)
        with conn.cursor() as cur:
            cur.execute("SELECT User, Host FROM mysql.user WHERE User NOT IN ('mariadb.sys', 'mysql.sys', 'mysql.session');")
            users = cur.fetchall()
            print("\n[BERHASIL] Terhubung sebagai root!")
            print("Daftar user yang ada di database Anda:")
            for u in users:
                print(f"  -> User: '{u[0]}' @ '{u[1]}'")
        conn.close()
        connected = True
        break
    except Exception:
        continue

if not connected:
    print("\nRoot menggunakan password khusus. Silakan jalankan:")
    print("python cek_user_manual.py")
