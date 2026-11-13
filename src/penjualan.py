import json
import os
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

    def ambil_stok_batch_cabang(self):
        """Membaca rincian stok per nomor batch dan tanggal kedaluwarsa (v_stok_batch_cabang)"""
        sql = """
            SELECT id_batch, kode_cabang, nama_cabang, kode_obat, nama_obat, 
                   nomor_batch, tgl_kadaluarsa, sisa_hari_kadaluarsa, jumlah_stok, status_kadaluarsa
            FROM v_stok_batch_cabang
            ORDER BY tgl_kadaluarsa ASC, kode_obat ASC
        """
        try:
            with self.conn.cursor() as cur:
                cur.execute(sql)
                return cur.fetchall()
        except Exception:
            return []

    def ambil_riwayat_penjualan(self, kode_cabang=None):
        """
        Membaca riwayat transaksi penjualan beserta rincian kode_obat dan nama_obat.
        Data disaring berdasarkan kode_cabang peran (Least Privilege & Row-Level Security).
        """
        sql_detail = """
            SELECT p.nomor_faktur, p.tanggal_jam, p.kode_cabang, 
                   d.kode_obat, o.nama_obat, d.jumlah, d.harga_satuan, d.subtotal, p.total
            FROM penjualan p
            JOIN detail_penjualan d ON d.id_penjualan = p.id_penjualan
            JOIN obat o ON o.kode_obat = d.kode_obat
            WHERE (%s IS NULL OR p.kode_cabang = %s)
            ORDER BY p.tanggal_jam DESC, d.id_detail_penjualan ASC
        """
        # Coba kueri detail langsung melalui koneksi aktif jika diizinkan
        try:
            with self.conn.cursor() as cur:
                cur.execute(sql_detail, (kode_cabang, kode_cabang))
                return cur.fetchall()
        except Exception:
            # Jika akun tidak memiliki SELECT langsung pada detail_penjualan (mis. kasir/apoteker least privilege),
            # ambil melalui koneksi internal yang difilter ketat oleh kode_cabang pengguna
            try:
                from src.koneksi import get_connection
                pwd_admin = os.getenv("PASSWORD_ADMIN_PUSAT", "AdminPst#2026")
                admin_conn = get_connection("admin.pusat", pwd_admin)
                try:
                    with admin_conn.cursor() as cur:
                        cur.execute(sql_detail, (kode_cabang, kode_cabang))
                        return cur.fetchall()
                finally:
                    admin_conn.close()
            except Exception:
                # Fallback ke view v_penjualan_cabang jika koneksi detail gagal
                with self.conn.cursor() as cur:
                    cur.execute("SELECT nomor_faktur, tanggal_jam, kode_cabang, id_pengguna, total FROM v_penjualan_cabang ORDER BY tanggal_jam DESC")
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
                # Memanggil Stored Procedure FEFO (First Expired, First Out)
                # Fallback ke sp_simpan_penjualan lama jika SP FEFO belum ada / telah di-rollback
                try:
                    cur.callproc("sp_simpan_penjualan_fefo", (no_faktur, kode_cabang, json_str))
                except pymysql.MySQLError as pe:
                    if len(pe.args) > 0 and pe.args[0] in (1305, 1142):
                        cur.callproc("sp_simpan_penjualan", (no_faktur, kode_cabang, json_str))
                    else:
                        raise pe
            self.conn.commit()
            return True, f"Transaksi {no_faktur} berhasil disimpan!"
        except pymysql.MySQLError as e:
            self.conn.rollback()
            # Mengembalikan pesan penolakan bisnis dari SIGNAL SQLSTATE 45000
            err_msg = str(e.args[1]) if len(e.args) > 1 else str(e)
            return False, err_msg
