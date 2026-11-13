import hashlib
import pymysql

try:
    import bcrypt
    HAS_BCRYPT = True
except ImportError:
    HAS_BCRYPT = False

def hash_kata_sandi(plain_password):
    """Hashing kata sandi menggunakan bcrypt atau fallback sha256"""
    if HAS_BCRYPT:
        salt = bcrypt.gensalt(rounds=10)
        return bcrypt.hashpw(plain_password.encode('utf-8'), salt).decode('utf-8')
    else:
        return hashlib.sha256(plain_password.encode('utf-8')).hexdigest()

class AdminDAO:
    def __init__(self, conn):
        self.conn = conn

    # ==========================================
    # CRUD & PANTAU CABANG
    # ==========================================
    def ambil_semua_cabang(self):
        sql = "SELECT kode_cabang, nama_cabang, alamat, telepon FROM cabang ORDER BY kode_cabang"
        with self.conn.cursor() as cur:
            cur.execute(sql)
            return cur.fetchall()

    def tambah_cabang(self, kode, nama, alamat, telepon):
        sql = "INSERT INTO cabang (kode_cabang, nama_cabang, alamat, telepon) VALUES (%s, %s, %s, %s)"
        with self.conn.cursor() as cur:
            cur.execute(sql, (kode, nama, alamat, telepon))
        self.conn.commit()

    def update_cabang(self, kode, nama, alamat, telepon):
        sql = "UPDATE cabang SET nama_cabang = %s, alamat = %s, telepon = %s WHERE kode_cabang = %s"
        with self.conn.cursor() as cur:
            cur.execute(sql, (nama, alamat, telepon, kode))
        self.conn.commit()

    def hapus_cabang(self, kode):
        sql = "DELETE FROM cabang WHERE kode_cabang = %s"
        with self.conn.cursor() as cur:
            cur.execute(sql, (kode,))
        self.conn.commit()

    def ringkasan_pantau_cabang(self):
        """
        Dashboard Monitoring Antar Cabang untuk Admin Pusat:
        Menampilkan total transaksi, total omset penjualan, total unit stok, dan stok kritis per cabang.
        """
        sql = """
            SELECT 
                c.kode_cabang,
                c.nama_cabang,
                c.telepon,
                COALESCE(p.total_transaksi, 0) AS total_transaksi,
                COALESCE(p.total_omset, 0) AS total_omset,
                COALESCE(s.total_stok, 0) AS total_stok,
                COALESCE(s.stok_kritis, 0) AS stok_kritis
            FROM cabang c
            LEFT JOIN (
                SELECT kode_cabang, COUNT(id_penjualan) AS total_transaksi, SUM(total) AS total_omset
                FROM penjualan
                GROUP BY kode_cabang
            ) p ON p.kode_cabang = c.kode_cabang
            LEFT JOIN (
                SELECT st.kode_cabang, SUM(st.jumlah_stok) AS total_stok,
                       COUNT(CASE WHEN st.jumlah_stok <= ob.stok_minimum THEN 1 END) AS stok_kritis
                FROM stok st
                JOIN obat ob ON ob.kode_obat = st.kode_obat
                GROUP BY st.kode_cabang
            ) s ON s.kode_cabang = c.kode_cabang
            ORDER BY c.kode_cabang
        """
        with self.conn.cursor() as cur:
            cur.execute(sql)
            return cur.fetchall()

    # ==========================================
    # CRUD MANAJEMEN PENGGUNA
    # ==========================================
    def ambil_semua_pengguna(self):
        sql = """
            SELECT p.id_pengguna, p.username, p.nama_lengkap, p.peran, 
                   p.kode_cabang, COALESCE(c.nama_cabang, 'Pusat (Semua Cabang)') AS nama_cabang
            FROM pengguna p
            LEFT JOIN cabang c ON c.kode_cabang = p.kode_cabang
            ORDER BY p.id_pengguna
        """
        with self.conn.cursor() as cur:
            cur.execute(sql)
            return cur.fetchall()

    def tambah_pengguna(self, username, password_plain, nama, peran, kode_cabang):
        pwd_hash = hash_kata_sandi(password_plain)
        # Jika ADMIN_PUSAT, kode_cabang bisa NULL
        cbg_val = None if peran == "ADMIN_PUSAT" or not kode_cabang or kode_cabang == "NONE" else kode_cabang
        
        sql = """
            INSERT INTO pengguna (username, password_hash, nama_lengkap, peran, kode_cabang)
            VALUES (%s, %s, %s, %s, %s)
        """
        with self.conn.cursor() as cur:
            cur.execute(sql, (username, pwd_hash, nama, peran, cbg_val))
        self.conn.commit()

    def update_pengguna(self, id_pengguna, nama, peran, kode_cabang, password_baru=None):
        cbg_val = None if peran == "ADMIN_PUSAT" or not kode_cabang or kode_cabang == "NONE" else kode_cabang
        if password_baru and password_baru.strip():
            pwd_hash = hash_kata_sandi(password_baru.strip())
            sql = "UPDATE pengguna SET nama_lengkap = %s, peran = %s, kode_cabang = %s, password_hash = %s WHERE id_pengguna = %s"
            params = (nama, peran, cbg_val, pwd_hash, id_pengguna)
        else:
            sql = "UPDATE pengguna SET nama_lengkap = %s, peran = %s, kode_cabang = %s WHERE id_pengguna = %s"
            params = (nama, peran, cbg_val, id_pengguna)
            
        with self.conn.cursor() as cur:
            cur.execute(sql, params)
        self.conn.commit()

    def hapus_pengguna(self, id_pengguna):
        sql = "DELETE FROM pengguna WHERE id_pengguna = %s"
        with self.conn.cursor() as cur:
            cur.execute(sql, (id_pengguna,))
        self.conn.commit()
