import pytest
import pymysql
import time
from src.koneksi import get_connection, get_config
from src.penjualan import PenjualanService
from src.monitor import get_system_resources, get_database_resources

# ==============================================================================
# 4 DEMONSTRASI WAJIB SERTIFIKASI MUK DATABASE PROGRAMMER (FR.IA.04A)
# ==============================================================================

def test_demo_1_transaksi_berhasil_stok_berkurang():
    """
    DEMO 1: Penyimpanan transaksi penjualan yang berhasil
    Stok cabang berkurang tepat sesuai jumlah yang dibeli.
    """
    # Gunakan akun Apoteker Depok di cabang CBG-01
    conn = get_connection("apoteker.depok", "ApotDpk#2026", env="dev")
    svc = PenjualanService(conn)
    kode_cabang = "CBG-01"
    kode_obat = "OBT-001" # Paracetamol
    jumlah_beli = 2

    try:
        # 1. Cek stok awal via v_stok_cabang
        with conn.cursor() as cur:
            cur.execute(
                "SELECT jumlah_stok FROM v_stok_cabang WHERE kode_cabang = %s AND kode_obat = %s",
                (kode_cabang, kode_obat)
            )
            row_awal = cur.fetchone()
            assert row_awal is not None, "Obat tidak ditemukan di v_stok_cabang"
            stok_awal = row_awal["jumlah_stok"]

        # 2. Simpan transaksi
        no_faktur = f"FKT-DEMO1-{int(time.time())}"
        daftar_item = [{"kode_obat": kode_obat, "jumlah": jumlah_beli}]
        ok, pesan = svc.simpan_transaksi(no_faktur, kode_cabang, daftar_item)
        assert ok is True, f"Transaksi gagal disimpan: {pesan}"

        # 3. Cek stok akhir via v_stok_cabang
        with conn.cursor() as cur:
            cur.execute(
                "SELECT jumlah_stok FROM v_stok_cabang WHERE kode_cabang = %s AND kode_obat = %s",
                (kode_cabang, kode_obat)
            )
            row_akhir = cur.fetchone()
            stok_akhir = row_akhir["jumlah_stok"]

        # Verifikasi stok berkurang tepat
        assert stok_akhir == stok_awal - jumlah_beli, (
            f"Stok tidak berkurang tepat: awal={stok_awal}, beli={jumlah_beli}, akhir={stok_akhir}"
        )
    finally:
        conn.close()

def test_demo_2_melebihi_stok_ditolak_dan_rollback():
    """
    DEMO 2: Transaksi melebihi stok ditolak dan seluruh transaksi di-ROLLBACK
    Stok tidak berubah sama sekali di database.
    """
    conn = get_connection("apoteker.depok", "ApotDpk#2026", env="dev")
    svc = PenjualanService(conn)
    kode_cabang = "CBG-01"
    kode_obat = "OBT-001"

    try:
        # 1. Ambil stok awal
        with conn.cursor() as cur:
            cur.execute(
                "SELECT jumlah_stok FROM v_stok_cabang WHERE kode_cabang = %s AND kode_obat = %s",
                (kode_cabang, kode_obat)
            )
            stok_awal = cur.fetchone()["jumlah_stok"]

        # 2. Coba transaksi dengan jumlah raksasa (99.999 unit)
        no_faktur = f"FKT-DEMO2-{int(time.time())}"
        daftar_item = [{"kode_obat": kode_obat, "jumlah": 99999}]
        ok, pesan = svc.simpan_transaksi(no_faktur, kode_cabang, daftar_item)

        # Verifikasi ditolak
        assert ok is False, "Seharusnya transaksi ditolak karena melebihi stok"
        assert "stok tidak mencukupi" in pesan.lower()

        # 3. Verifikasi stok setelah rollback tetap sama dengan stok awal
        with conn.cursor() as cur:
            cur.execute(
                "SELECT jumlah_stok FROM v_stok_cabang WHERE kode_cabang = %s AND kode_obat = %s",
                (kode_cabang, kode_obat)
            )
            stok_akhir = cur.fetchone()["jumlah_stok"]

        assert stok_akhir == stok_awal, f"Stok berubah meskipun transaksi dibatalkan! Awal: {stok_awal}, Akhir: {stok_akhir}"
    finally:
        conn.close()

def test_demo_3_kasir_obat_keras_ditolak_dan_isolasi_cabang():
    """
    DEMO 3:
    a) Kasir DITOLAK saat mencoba menjual Obat Keras (Amoxicillin / Ciprofloxacin).
    b) Kasir Depok TIDAK DAPAT melihat data cabang lain (hanya melihat CBG-01).
    """
    # 3a. Kasir Depok coba jual Obat Keras (OBT-007: Ciprofloxacin - KTG-03)
    conn_kasir = get_connection("kasir.depok", "KasirDpk#2026", env="dev")
    svc_kasir = PenjualanService(conn_kasir)
    no_faktur = f"FKT-DEMO3-{int(time.time())}"

    try:
        ok, pesan = svc_kasir.simpan_transaksi(no_faktur, "CBG-01", [{"kode_obat": "OBT-007", "jumlah": 1}])
        assert ok is False, "Kasir seharusnya DITOLAK saat menjual Obat Keras"
        assert "obat keras hanya boleh dijual oleh apoteker" in pesan.lower()

        # 3b. Isolasi cabang: Kasir Depok hanya melihat data cabang CBG-01 di v_stok_cabang
        with conn_kasir.cursor() as cur:
            cur.execute("SELECT DISTINCT kode_cabang FROM v_stok_cabang")
            cabang_terlihat = [r["kode_cabang"] for r in cur.fetchall()]
            assert cabang_terlihat == ["CBG-01"], f"Kasir Depok melihat cabang lain: {cabang_terlihat}"

            # Kasir coba SELECT cabang lain langsung di view -> harus 0 baris
            cur.execute("SELECT COUNT(*) AS c FROM v_stok_cabang WHERE kode_cabang = 'CBG-02'")
            count_cbg2 = cur.fetchone()["c"]
            assert count_cbg2 == 0, "Kasir Depok tidak boleh bisa membaca stok cabang Bekasi (CBG-02)"
    finally:
        conn_kasir.close()

def test_demo_4_environment_config_dan_monitoring():
    """
    DEMO 4:
    a) Pengambilan konfigurasi environment (dev, staging, prod) terpisah.
    b) Pemantauan resource (CPU, RAM, Disk, DB connections, Latency) berfungsi normal.
    """
    # 4a. Cek konfigurasi dev, staging, prod
    cfg_dev = get_config("dev")
    cfg_staging = get_config("staging")
    cfg_prod = get_config("prod")

    assert cfg_dev["dbname"] == "apotek"
    assert cfg_staging["dbname"] == "apotek_staging"
    assert cfg_prod["dbname"] == "apotek_prod"
    assert cfg_dev["log_level"] == "DEBUG"
    assert cfg_prod["log_level"] == "WARNING"

    # 4b. Cek modul monitoring
    sys_res = get_system_resources()
    assert "cpu_percent" in sys_res
    assert "ram_percent" in sys_res
    assert "disk_percent" in sys_res

    conn = get_connection("admin.pusat", "AdminPst#2026", env="dev")
    try:
        db_res = get_database_resources(conn)
        assert "db_connections" in db_res
        assert "query_latency_ms" in db_res
        assert db_res["db_connections"] >= 1
    finally:
        conn.close()
