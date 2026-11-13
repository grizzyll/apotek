"""
Unit Testing Khusus Fitur FEFO (First Expired, First Out)
Action 11 & 13 (J.620100.043.01 & J.620100.047.01)
Menguji:
1. Pemotongan batch mendahulukan tanggal kedaluwarsa terdekat (FEFO)
2. Pembagian pemotongan otomatis antar batch (Split Batch)
3. Isolasi Row-Level Security pada view batch cabang
"""
import pytest
import pymysql
import time
from src.koneksi import get_connection
from src.penjualan import PenjualanService

def test_fefo_pemotongan_batch_terdekat_dahulu():
    """Memverifikasi bahwa penjualan mendahulukan batch dengan tgl_kadaluarsa paling awal"""
    conn = get_connection("apoteker.depok", "ApotDpk#2026", env="dev")
    svc = PenjualanService(conn)
    kode_cabang = "CBG-01"

    try:
        # 1. Cari obat yang memiliki minimal 2 batch aktif terurut FEFO
        with conn.cursor() as cur:
            cur.execute("""
                SELECT kode_obat
                FROM v_stok_batch_cabang
                WHERE kode_cabang = %s AND jumlah_stok > 0 AND tgl_kadaluarsa > CURRENT_DATE
                GROUP BY kode_obat
                HAVING COUNT(*) >= 2
                LIMIT 1
            """, (kode_cabang,))
            row_obat = cur.fetchone()
            assert row_obat is not None, "Harus ada obat dengan minimal 2 batch aktif"
            kode_obat = row_obat["kode_obat"]

            cur.execute("""
                SELECT id_batch, nomor_batch, tgl_kadaluarsa, jumlah_stok 
                FROM v_stok_batch_cabang 
                WHERE kode_cabang = %s AND kode_obat = %s AND jumlah_stok > 0 AND tgl_kadaluarsa > CURRENT_DATE
                ORDER BY tgl_kadaluarsa ASC, id_batch ASC
            """, (kode_cabang, kode_obat))
            batches = cur.fetchall()
            assert len(batches) >= 2, "Perlu minimal 2 batch aktif untuk uji FEFO"
            
            batch_pertama = batches[0]
            batch_kedua = batches[1]
            stok_awal_b1 = batch_pertama["jumlah_stok"]
            stok_awal_b2 = batch_kedua["jumlah_stok"]

        # 2. Beli 1 unit (cukup dari batch pertama saja)
        no_faktur = f"FKT-F1-{int(time.time()*1000)%100000000}"
        ok, msg = svc.simpan_transaksi(no_faktur, kode_cabang, [{"kode_obat": kode_obat, "jumlah": 1}])
        assert ok is True, f"Transaksi FEFO gagal: {msg}"

        # 3. Verifikasi hanya batch pertama yang berkurang, batch kedua tetap utuh
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id_batch, jumlah_stok 
                FROM v_stok_batch_cabang 
                WHERE id_batch IN (%s, %s)
            """, (batch_pertama["id_batch"], batch_kedua["id_batch"]))
            rows = {r["id_batch"]: r["jumlah_stok"] for r in cur.fetchall()}

            assert rows[batch_pertama["id_batch"]] == stok_awal_b1 - 1, "Batch terdekat harus berkurang 1 unit"
            assert rows[batch_kedua["id_batch"]] == stok_awal_b2, "Batch kedua tidak boleh berkurang"
    finally:
        conn.close()

def test_fefo_split_batch_otomatis():
    """Memverifikasi bahwa sistem otomatis memotong lebih dari satu batch jika batch terdekat tidak cukup"""
    conn = get_connection("apoteker.depok", "ApotDpk#2026", env="dev")
    svc = PenjualanService(conn)
    kode_cabang = "CBG-01"
    
    try:
        # Cari obat di cabang CBG-01 yang memiliki minimal 2 batch aktif (belum kedaluwarsa)
        with conn.cursor() as cur:
            cur.execute("""
                SELECT kode_obat
                FROM v_stok_batch_cabang
                WHERE kode_cabang = %s AND jumlah_stok > 0 AND tgl_kadaluarsa > CURRENT_DATE
                GROUP BY kode_obat
                HAVING COUNT(*) >= 2
                LIMIT 1
            """, (kode_cabang,))
            row_obat = cur.fetchone()
            assert row_obat is not None, "Harus ada obat dengan minimal 2 batch aktif"
            kode_obat = row_obat["kode_obat"]

            # Ambil 2 batch aktif teratas
            cur.execute("""
                SELECT id_batch, nomor_batch, tgl_kadaluarsa, jumlah_stok 
                FROM v_stok_batch_cabang 
                WHERE kode_cabang = %s AND kode_obat = %s AND jumlah_stok > 0 AND tgl_kadaluarsa > CURRENT_DATE
                ORDER BY tgl_kadaluarsa ASC, id_batch ASC
            """, (kode_cabang, kode_obat))
            batches = cur.fetchall()
            b1 = batches[0]
            b2 = batches[1]
            sisa_b1 = b1["jumlah_stok"]
            sisa_b2 = b2["jumlah_stok"]

        # Beli sisa batch 1 + 1 unit dari batch 2
        jumlah_beli = sisa_b1 + 1
        no_faktur = f"FKT-FS-{int(time.time()*1000)%100000000}"
        ok, msg = svc.simpan_transaksi(no_faktur, kode_cabang, [{"kode_obat": kode_obat, "jumlah": jumlah_beli}])
        assert ok is True, f"Transaksi split FEFO gagal: {msg}"

        # Cek stok kedua batch
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id_batch, jumlah_stok 
                FROM v_stok_batch_cabang 
                WHERE id_batch IN (%s, %s)
            """, (b1["id_batch"], b2["id_batch"]))
            rows = {r["id_batch"]: r["jumlah_stok"] for r in cur.fetchall()}

            # Batch 1 harus habis (0)
            assert rows.get(b1["id_batch"], 0) == 0, "Batch 1 harus habis diserap terlebih dahulu"
            # Batch 2 harus berkurang 1 unit
            assert rows[b2["id_batch"]] == sisa_b2 - 1, "Batch 2 harus berkurang sisa kebutuhan (1 unit)"
    finally:
        conn.close()

def test_fefo_isolasi_row_level_security():
    """Memverifikasi bahwa Kasir Depok hanya dapat melihat batch milik cabang CBG-01"""
    conn_kasir = get_connection("kasir.depok", "KasirDpk#2026", env="dev")
    try:
        with conn_kasir.cursor() as cur:
            cur.execute("SELECT DISTINCT kode_cabang FROM v_stok_batch_cabang")
            cabang_list = [r["kode_cabang"] for r in cur.fetchall()]
            assert cabang_list == ["CBG-01"], f"Kasir Depok hanya boleh melihat CBG-01, didapat: {cabang_list}"
    finally:
        conn_kasir.close()

def test_fefo_klasifikasi_status_kadaluarsa():
    """Memverifikasi deteksi status aman vs kadaluarsa pada v_stok_batch_cabang"""
    conn = get_connection("admin.pusat", "AdminPst#2026", env="dev")
    svc = PenjualanService(conn)
    try:
        data = svc.ambil_stok_batch_cabang()
        assert len(data) > 0, "Harus ada data batch terdaftar"
        
        statuses = {r["status_kadaluarsa"] for r in data}
        assert "AMAN" in statuses, "Harus ada batch dengan status AMAN"
        # Verifikasi format field yang dibutuhkan fitur status kedaluwarsa
        sample = data[0]
        assert "nomor_batch" in sample
        assert "tgl_kadaluarsa" in sample
        assert "sisa_hari_kadaluarsa" in sample
        assert "status_kadaluarsa" in sample
    finally:
        conn.close()

