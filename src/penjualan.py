import json
import pymysql

class PenjualanService:
    def __init__(self, conn):
        self.conn = conn

    def ambil_stok_cabang(self):
        """
        Membaca stok melalui View terproteksi (v_stok_cabang).
        Secara otomatis disaring database berdasarkan akun pengguna yang login:
        - Kasir Depok hanya melihat cabang CBG-01
        - Kasir Bekasi hanya melihat cabang CBG-02
        - Admin Pusat melihat seluruh cabang
        """
        sql = "SELECT kode_cabang, nama_cabang, kode_obat, nama_obat, jumlah_stok, stok_minimum FROM v_stok_cabang ORDER BY kode_cabang, kode_obat"
        with self.conn.cursor() as cur:
            cur.execute(sql)
            return cur.fetchall()

    def ambil_stok_kritis(self):
        """Membaca stok yang <= stok minimum (v_stok_kritis_cabang)"""
        sql = "SELECT kode_cabang, nama_cabang, kode_obat, nama_obat, jumlah_stok, stok_minimum FROM v_stok_kritis_cabang ORDER BY jumlah_stok ASC"
        with self.conn.cursor() as cur:
            cur.execute(sql)
            return cur.fetchall()

    def ambil_riwayat_penjualan(self):
        """Membaca riwayat transaksi (v_penjualan_cabang)"""
        sql = "SELECT nomor_faktur, tanggal_jam, kode_cabang, id_pengguna, total FROM v_penjualan_cabang ORDER BY tanggal_jam DESC"
        with self.conn.cursor() as cur:
            cur.execute(sql)
            return cur.fetchall()

    def simpan_transaksi(self, no_faktur, kode_cabang, daftar_item):
        """
        ACTION 3: Struktur Data Keranjang Belanja (List of Dicts)
        ACTION 5 & 6: Pemanggilan Stored Procedure sp_simpan_penjualan dengan JSON
        Transaksi ACID: Commit jika sukses, Rollback otomatis jika gagal di database
        """
        # Konversi struktur data program (List of Dict) menjadi string JSON untuk Stored Procedure
        payload_items = []
        for it in daftar_item:
            payload_items.append({
                "kode_obat": it["kode_obat"],
                "jumlah": int(it["jumlah"])
            })
        
        json_str = json.dumps(payload_items)

        try:
            with self.conn.cursor() as cur:
                # Memanggil stored procedure
                cur.callproc("sp_simpan_penjualan", (no_faktur, kode_cabang, json_str))
            self.conn.commit()
            return True, f"Transaksi {no_faktur} berhasil disimpan!"
        except pymysql.MySQLError as e:
            self.conn.rollback()
            # Mengembalikan pesan penolakan bisnis dari SIGNAL SQLSTATE 45000
            err_msg = str(e.args[1]) if len(e.args) > 1 else str(e)
            return False, err_msg
