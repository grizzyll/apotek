import sys
from src.koneksi import get_connection

if len(sys.argv) < 3:
    print("Penggunaan: python tes_koneksi.py <username> <password>")
    sys.exit(1)

user = sys.argv[1]
pwd = sys.argv[2]

try:
    env = sys.argv[3] if len(sys.argv) > 3 else "dev"
    conn = get_connection(user, pwd, env=env)
    with conn.cursor() as cur:
        cur.execute("SELECT USER() AS u, CURRENT_USER() AS cu, DATABASE() AS db")
        res = cur.fetchone()
        print("\n[BERHASIL] Terhubung ke Database!")
        print("Koneksi sebagai :", res["u"])
        print("Hak akses peran :", res["cu"])
        print("Database aktif  :", res["db"])
    conn.close()
except Exception as e:
    print(f"\n[GAGAL] Error koneksi: {e}")
