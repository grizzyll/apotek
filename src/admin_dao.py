import pymysql

try:
    import bcrypt
    HAS_BCRYPT = True
except ImportError:
    HAS_BCRYPT = False

def hash_kata_sandi(plain_password):
    """
    Hashing kata sandi menggunakan bcrypt dengan salt adaptif (rounds=10).
    Standar keamanan SNI ISO/IEC 27001 (A.8.24 / A.10.1).
    Fallback ke algoritma hashing lemah tanpa salt (mis. SHA-256) DILARANG KERAS.
    """
    if not HAS_BCRYPT:
        raise RuntimeError("Modul 'bcrypt' wajib terinstal untuk keamanan penyimpanan kata sandi. Hashing tanpa salt tidak diizinkan.")
    salt = bcrypt.gensalt(rounds=10)
    return bcrypt.hashpw(plain_password.encode('utf-8'), salt).decode('utf-8')

# ==========================================
# AUTO-GENERATE KODE (Module-Level Functions)
# ==========================================
def generate_kode_cabang(conn):
    """Generate kode cabang berikutnya secara otomatis (CBG-XX)"""
    with conn.cursor() as cur:
        cur.execute("SELECT kode_cabang FROM cabang ORDER BY kode_cabang DESC LIMIT 1")
        row = cur.fetchone()
    if row:
        try:
            parts = row['kode_cabang'].split('-')
            last_num = int(parts[1])
            return f"CBG-{last_num + 1:02d}"
        except (ValueError, IndexError, KeyError):
            pass
    return "CBG-01"

def generate_kode_obat(conn):
    """Generate kode obat berikutnya secara otomatis (OBT-XXX)"""
    with conn.cursor() as cur:
        cur.execute("SELECT kode_obat FROM obat ORDER BY kode_obat DESC LIMIT 1")
        row = cur.fetchone()
    if row:
        try:
            parts = row['kode_obat'].split('-')
            last_num = int(parts[1])
            return f"OBT-{last_num + 1:03d}"
        except (ValueError, IndexError, KeyError):
            pass
    return "OBT-001"

class AdminDAO:
    def __init__(self, conn):
        self.conn = conn

    # ==========================================
    # AUTO-GENERATE KODE (Primary Key otomatis)
    # ==========================================
    def generate_kode_cabang(self):
        """Generate kode cabang berikutnya secara otomatis (CBG-XX)"""
        return generate_kode_cabang(self.conn)

    def generate_kode_obat(self):
        """Generate kode obat berikutnya secara otomatis (OBT-XXX)"""
        return generate_kode_obat(self.conn)

    # ==========================================
    # VALIDASI
    # ==========================================
    def cek_nama_cabang_unik(self, nama, exclude_kode=None):
        """Cek apakah nama cabang sudah digunakan (case-insensitive)"""
        if exclude_kode:
            sql = "SELECT COUNT(*) as cnt FROM cabang WHERE LOWER(TRIM(nama_cabang)) = LOWER(TRIM(%s)) AND kode_cabang != %s"
            params = (nama, exclude_kode)
        else:
            sql = "SELECT COUNT(*) as cnt FROM cabang WHERE LOWER(TRIM(nama_cabang)) = LOWER(TRIM(%s))"
            params = (nama,)
        with self.conn.cursor() as cur:
            cur.execute(sql, params)
            row = cur.fetchone()
        return row['cnt'] > 0

    def cek_relasi_obat(self, kode_obat):
        """Cek jumlah data terkait obat (stok & detail penjualan)"""
        with self.conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) as cnt FROM stok WHERE kode_obat = %s", (kode_obat,))
            stok_cnt = cur.fetchone()['cnt']
            cur.execute("SELECT COUNT(*) as cnt FROM detail_penjualan WHERE kode_obat = %s", (kode_obat,))
            dp_cnt = cur.fetchone()['cnt']
        return stok_cnt, dp_cnt

    def cek_relasi_cabang(self, kode_cabang):
        """Cek jumlah data terkait cabang"""
        with self.conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) as cnt FROM stok WHERE kode_cabang = %s", (kode_cabang,))
            stok_cnt = cur.fetchone()['cnt']
            cur.execute("SELECT COUNT(*) as cnt FROM penjualan WHERE kode_cabang = %s", (kode_cabang,))
            pen_cnt = cur.fetchone()['cnt']
            cur.execute("SELECT COUNT(*) as cnt FROM pengguna WHERE kode_cabang = %s", (kode_cabang,))
            usr_cnt = cur.fetchone()['cnt']
        return stok_cnt, pen_cnt, usr_cnt

    def cek_relasi_pengguna(self, id_pengguna):
        """Cek jumlah transaksi milik pengguna"""
        with self.conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) as cnt FROM penjualan WHERE id_pengguna = %s", (id_pengguna,))
            row = cur.fetchone()
        return row['cnt']

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
        try:
            with self.conn.cursor() as cur:
                cur.execute(sql, (kode, nama, alamat, telepon))
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise

    def update_cabang(self, kode, nama, alamat, telepon):
        sql = "UPDATE cabang SET nama_cabang = %s, alamat = %s, telepon = %s WHERE kode_cabang = %s"
        try:
            with self.conn.cursor() as cur:
                cur.execute(sql, (nama, alamat, telepon, kode))
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise

    def hapus_cabang(self, kode):
        """
        DROP CABANG:
        Menghapus cabang apotek.
        1. Pengguna/pegawai yang bertugas di cabang ini dialihkan statusnya menjadi Nonaktif (kode_cabang = NULL).
        2. Cabang di-drop langsung menggunakan foreign_key_checks=0.
        3. Riwayat transaksi penjualan masa lalu tetap tersimpan aman di database utama untuk audit.
        """
        sql_del = "DELETE FROM cabang WHERE kode_cabang = %s"
        try:
            with self.conn.cursor() as cur:
                # Alihkan staf cabang menjadi Nonaktif (kode_cabang = NULL)
                cur.execute("UPDATE pengguna SET kode_cabang = NULL WHERE kode_cabang = %s", (kode,))
                cur.execute("SET FOREIGN_KEY_CHECKS = 0")
                cur.execute(sql_del, (kode,))
                cur.execute("SET FOREIGN_KEY_CHECKS = 1")
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            try:
                with self.conn.cursor() as cur:
                    cur.execute("SET FOREIGN_KEY_CHECKS = 1")
            except Exception:
                pass
            raise

    def ringkasan_pantau_cabang(self):
        """
        Dashboard Monitoring Antar Cabang untuk Admin Pusat.
        HANYA boleh dipanggil oleh ADMIN_PUSAT — mengakses tabel cabang, stok, penjualan
        secara langsung (kasir/apoteker tidak punya SELECT pada tabel-tabel ini).
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
        cbg_val = None if peran == "ADMIN_PUSAT" or not kode_cabang or kode_cabang == "NONE" else kode_cabang
        
        sql = """
            INSERT INTO pengguna (username, password_hash, nama_lengkap, peran, kode_cabang)
            VALUES (%s, %s, %s, %s, %s)
        """
        try:
            with self.conn.cursor() as cur:
                cur.execute(sql, (username, pwd_hash, nama, peran, cbg_val))
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise

    def update_pengguna(self, id_pengguna, nama, peran, kode_cabang, password_baru=None):
        cbg_val = None if peran == "ADMIN_PUSAT" or not kode_cabang or kode_cabang == "NONE" else kode_cabang
        if password_baru and password_baru.strip():
            pwd_hash = hash_kata_sandi(password_baru.strip())
            sql = "UPDATE pengguna SET nama_lengkap = %s, peran = %s, kode_cabang = %s, password_hash = %s WHERE id_pengguna = %s"
            params = (nama, peran, cbg_val, pwd_hash, id_pengguna)
        else:
            sql = "UPDATE pengguna SET nama_lengkap = %s, peran = %s, kode_cabang = %s WHERE id_pengguna = %s"
            params = (nama, peran, cbg_val, id_pengguna)
            
        try:
            with self.conn.cursor() as cur:
                cur.execute(sql, params)
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise

    def hapus_pengguna(self, id_pengguna):
        """
        DROP PENGGUNA:
        Menghapus akun pengguna dari sistem.
        1. Data profil pengguna dan ringkasan transaksinya di-backup ke file log JSON sebelum akun di-drop.
        2. Pengguna di-drop langsung menggunakan foreign_key_checks=0.
        3. Riwayat transaksi di tabel penjualan tetap tersimpan aman di database utama untuk audit relasional.
        """
        import os
        import json
        from datetime import datetime
        try:
            with self.conn.cursor() as cur:
                # 1. Backup snapshot pengguna & transaksinya
                cur.execute("SELECT * FROM pengguna WHERE id_pengguna = %s", (id_pengguna,))
                user_info = cur.fetchone()
                cur.execute("SELECT id_penjualan, nomor_faktur, tanggal_jam, total FROM penjualan WHERE id_pengguna = %s", (id_pengguna,))
                trx_list = cur.fetchall()

                if user_info:
                    try:
                        backup_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs")
                        os.makedirs(backup_dir, exist_ok=True)
                        backup_file = os.path.join(backup_dir, "backup_pengguna_deleted.jsonl")
                        backup_entry = {
                            "deleted_at": datetime.now().isoformat(),
                            "id_pengguna": id_pengguna,
                            "user_profile": {k: str(v) for k, v in user_info.items()},
                            "total_transaksi": len(trx_list) if trx_list else 0,
                            "riwayat_transaksi": [{k: str(v) for k, v in t.items()} for t in (trx_list or [])]
                        }
                        with open(backup_file, "a", encoding="utf-8") as f:
                            f.write(json.dumps(backup_entry, default=str) + "\n")
                    except Exception:
                        pass

                # 2. Drop pengguna dari database
                cur.execute("SET FOREIGN_KEY_CHECKS = 0")
                cur.execute("DELETE FROM pengguna WHERE id_pengguna = %s", (id_pengguna,))
                cur.execute("SET FOREIGN_KEY_CHECKS = 1")
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            try:
                with self.conn.cursor() as cur:
                    cur.execute("SET FOREIGN_KEY_CHECKS = 1")
            except Exception:
                pass
            raise
