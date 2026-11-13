import pymysql

class ObatDAO:
    def __init__(self, conn):
        self.conn = conn

    # ==========================================
    # ACTION 6: CRUD DENGAN PARAMETERIZED QUERY
    # ==========================================
    def ambil_kategori(self):
        """Mendapatkan daftar kategori obat"""
        sql = "SELECT kode_kategori, nama_kategori FROM kategori_obat ORDER BY kode_kategori"
        with self.conn.cursor() as cur:
            cur.execute(sql)
            return cur.fetchall()

    def ambil_semua(self):
        """READ: Mengambil semua obat beserta nama kategorinya"""
        sql = """
            SELECT o.kode_obat, o.nama_obat, o.kode_kategori, k.nama_kategori,
                   o.satuan, o.harga_jual, o.stok_minimum
            FROM obat o
            JOIN kategori_obat k ON k.kode_kategori = o.kode_kategori
            ORDER BY o.kode_obat
        """
        with self.conn.cursor() as cur:
            cur.execute(sql)
            return cur.fetchall()

    def cari_by_kode(self, kode):
        """READ: Cari obat spesifik berdasarkan kode_obat (%s parameterized)"""
        sql = """
            SELECT o.kode_obat, o.nama_obat, o.kode_kategori, k.nama_kategori,
                   o.satuan, o.harga_jual, o.stok_minimum
            FROM obat o
            JOIN kategori_obat k ON k.kode_kategori = o.kode_kategori
            WHERE o.kode_obat = %s
        """
        with self.conn.cursor() as cur:
            cur.execute(sql, (kode,))
            return cur.fetchone()

    def tambah_obat(self, kode, nama, kategori, satuan, harga, min_stok):
        """CREATE: Menambah obat baru (Hanya Admin Pusat)"""
        sql = """
            INSERT INTO obat (kode_obat, nama_obat, kode_kategori, satuan, harga_jual, stok_minimum)
            VALUES (%s, %s, %s, %s, %s, %s)
        """
        with self.conn.cursor() as cur:
            cur.execute(sql, (kode, nama, kategori, satuan, harga, min_stok))
        self.conn.commit()

    def update_harga(self, kode, harga_baru):
        """UPDATE: Mengubah harga obat (%s parameterized)"""
        sql = "UPDATE obat SET harga_jual = %s WHERE kode_obat = %s"
        with self.conn.cursor() as cur:
            cur.execute(sql, (harga_baru, kode))
        self.conn.commit()

    def hapus_obat(self, kode):
        """DELETE: Menghapus obat (%s parameterized)"""
        sql = "DELETE FROM obat WHERE kode_obat = %s"
        with self.conn.cursor() as cur:
            cur.execute(sql, (kode,))
        self.conn.commit()


# ========================================================
# ACTION 7: ALGORITMA SEARCHING & SORTING (IMPLEMENTASI MANDIRI)
# ========================================================

def cari_obat_linear(daftar_obat, keyword):
    """
    Algoritma Pencarian Linear (Linear Search)
    Kompleksitas Waktu: O(N)
    Kompleksitas Memori: O(1) tambahan
    Mencari keyword pada nama obat atau kode obat tanpa memandang urutan.
    """
    hasil = []
    keyword_lower = keyword.strip().lower()
    for item in daftar_obat:
        if keyword_lower in item["nama_obat"].lower() or keyword_lower in item["kode_obat"].lower():
            hasil.append(item)
    return hasil

def cari_obat_binary(daftar_obat_terurut, target_kode):
    """
    Algoritma Pencarian Biner (Binary Search)
    Prasyarat: Daftar obat harus terurut berdasarkan kode_obat.
    Kompleksitas Waktu: O(log N)
    Kompleksitas Memori: O(1)
    """
    low = 0
    high = len(daftar_obat_terurut) - 1
    target_clean = target_kode.strip().upper()

    while low <= high:
        mid = (low + high) // 2
        kode_mid = daftar_obat_terurut[mid]["kode_obat"].upper()
        
        if kode_mid == target_clean:
            return daftar_obat_terurut[mid]
        elif kode_mid < target_clean:
            low = mid + 1
        else:
            high = mid - 1
            
    return None

def quick_sort_obat(daftar_obat, key="harga_jual", ascending=True):
    """
    Algoritma Pengurutan Cepat (Quick Sort)
    Kompleksitas Waktu: Rata-rata O(N log N), Terburuk O(N^2)
    Kompleksitas Memori: O(N) untuk list rekursif
    Digunakan untuk mengurutkan laporan obat atau inventori.
    """
    if len(daftar_obat) <= 1:
        return daftar_obat
    
    pivot = daftar_obat[len(daftar_obat) // 2]
    pivot_val = pivot[key]
    
    if ascending:
        left = [x for x in daftar_obat if x[key] < pivot_val]
        middle = [x for x in daftar_obat if x[key] == pivot_val]
        right = [x for x in daftar_obat if x[key] > pivot_val]
    else:
        left = [x for x in daftar_obat if x[key] > pivot_val]
        middle = [x for x in daftar_obat if x[key] == pivot_val]
        right = [x for x in daftar_obat if x[key] < pivot_val]
        
    return quick_sort_obat(left, key, ascending) + middle + quick_sort_obat(right, key, ascending)
