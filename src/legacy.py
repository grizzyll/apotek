import time
import pymysql

def simpan_penjualan_lama(conn, faktur, kode_obat, jumlah):
    """
    MODUL PENJUALAN LAMA (LEGACY) - Sumber: Soal Studi Kasus PT Sehat Bersama Farma
    Kelemahan & Cacat Kritis:
    1. Kerentanan SQL Injection parah akibat penggabungan string (' + faktur + ')
    2. Nama kolom salah (di DB adalah jumlah_stok, nomor_faktur, dll.)
    3. Tidak ada penanganan error (try-except) dan tidak ada ROLLBACK jika gagal
    4. Cursor tidak ditutup (memory leak)
    5. Mengabaikan validasi stok cabang dan aturan Obat Keras
    """
    cur = conn.cursor()
    # Query rentan SQL Injection
    cur.execute("INSERT INTO detail_penjualan (nomor_faktur, kode_obat, jumlah) VALUES ('" + faktur + "','" + kode_obat + "'," + str(jumlah) + ")")
    cur.execute("UPDATE stok SET jumlah = jumlah - " + str(jumlah) + " WHERE kode_obat='" + kode_obat + "'")
    conn.commit()

def simpan_penjualan_refactor(conn, faktur, kode_cabang, kode_obat, jumlah):
    """
    MODUL SETELAH CODE REVIEW & PERBAIKAN (ACTION 9):
    1. Menggunakan Stored Procedure sp_simpan_penjualan (Centralized Business Logic & Least Privilege).
    2. Menerapkan transaksi atomik (ACID): COMMIT jika sukses, ROLLBACK otomatis jika gagal.
    3. Mencegah SQL Injection sepenuhnya via parameterized callproc.
    4. Validasi aturan Obat Keras, otorisasi cabang, dan stok ditegakkan di level database.
    """
    import json
    payload = json.dumps([{"kode_obat": kode_obat, "jumlah": int(jumlah)}])
    try:
        with conn.cursor() as cur:
            cur.callproc("sp_simpan_penjualan", (faktur, kode_cabang, payload))
        conn.commit()
        return True, f"Transaksi {faktur} berhasil disimpan dengan aman (ACID Stored Procedure)."
    except pymysql.MySQLError as e:
        conn.rollback()
        err_msg = str(e.args[1]) if len(e.args) > 1 else str(e)
        return False, f"Transaksi dibatalkan (ROLLBACK): {err_msg}"

def bandingkan_kueri_laporan(conn, tahun=2026, bulan=11, jumlah_run=5):
    """
    OPTIMASI KUERI LAPORAN (ACTION 9):
    Kueri Lama:
      SELECT * FROM penjualan p, detail_penjualan d WHERE p.id_penjualan = d.id_penjualan AND YEAR(p.tanggal_jam) = 2026 AND MONTH(p.tanggal_jam) = 11;
      (Non-sargable: fungsi YEAR/MONTH mematikan penggunaan B-Tree Index!)
    
    Kueri Baru (Optimasi):
      SELECT p.nomor_faktur, p.tanggal_jam, d.kode_obat, d.jumlah, d.subtotal
      FROM penjualan p
      INNER JOIN detail_penjualan d ON d.id_penjualan = p.id_penjualan
      WHERE p.tanggal_jam >= %s AND p.tanggal_jam < %s;
      (Sargable range query yang langsung memanfaatkan 'idx_penjualan_tanggal'!)
      
    Pengujian empiris dilakukan 5 kali run, mengeliminasi run pertama (warm-up run),
    lalu merata-ratakan 4 run berikutnya.
    """
    sql_lama = """
        SELECT * FROM penjualan p, detail_penjualan d
        WHERE p.id_penjualan = d.id_penjualan
          AND YEAR(p.tanggal_jam) = %s AND MONTH(p.tanggal_jam) = %s
    """
    
    bulan_next = bulan + 1 if bulan < 12 else 1
    tahun_next = tahun if bulan < 12 else tahun + 1
    start_date = f"{tahun:04d}-{bulan:02d}-01 00:00:00"
    end_date = f"{tahun_next:04d}-{bulan_next:02d}-01 00:00:00"

    sql_baru = """
        SELECT p.nomor_faktur, p.tanggal_jam, p.kode_cabang, d.kode_obat, d.jumlah, d.subtotal
        FROM penjualan p
        INNER JOIN detail_penjualan d ON d.id_penjualan = p.id_penjualan
        WHERE p.tanggal_jam >= %s AND p.tanggal_jam < %s
    """
    
    durasi_lama = []
    durasi_baru = []
    res_baru = []

    with conn.cursor() as cur:
        # Jalankan beberapa run bergantian untuk menghilangkan bias caching
        for i in range(jumlah_run):
            # Kueri lama
            t0 = time.perf_counter()
            cur.execute(sql_lama, (tahun, bulan))
            cur.fetchall()
            t1 = time.perf_counter()
            durasi_lama.append((t1 - t0) * 1000)

            # Kueri baru
            t2 = time.perf_counter()
            cur.execute(sql_baru, (start_date, end_date))
            res_baru = cur.fetchall()
            t3 = time.perf_counter()
            durasi_baru.append((t3 - t2) * 1000)

    # Buang run pertama (warm-up) jika jumlah_run > 1
    sample_lama = durasi_lama[1:] if len(durasi_lama) > 1 else durasi_lama
    sample_baru = durasi_baru[1:] if len(durasi_baru) > 1 else durasi_baru

    avg_lama = sum(sample_lama) / len(sample_lama)
    avg_baru = sum(sample_baru) / len(sample_baru)

    return {
        "waktu_lama_ms": round(avg_lama, 3),
        "waktu_baru_ms": round(avg_baru, 3),
        "min_lama_ms": round(min(sample_lama), 3),
        "max_lama_ms": round(max(sample_lama), 3),
        "min_baru_ms": round(min(sample_baru), 3),
        "max_baru_ms": round(max(sample_baru), 3),
        "total_data": len(res_baru),
        "sql_lama": sql_lama.strip(),
        "sql_baru": sql_baru.strip()
    }
