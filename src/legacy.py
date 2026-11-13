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
    1. Menggunakan Parameterized Query (%s) anti SQL Injection
    2. Validasi stok sebelum update
    3. Menggunakan blok try-except dengan COMMIT dan ROLLBACK eksplisit
    4. Menggunakan context manager 'with' untuk menutup cursor otomatis
    """
    try:
        with conn.cursor() as cur:
            # 1. Validasi kecukupan stok cabang
            cur.execute(
                "SELECT jumlah_stok FROM stok WHERE kode_cabang = %s AND kode_obat = %s",
                (kode_cabang, kode_obat)
            )
            stok_data = cur.fetchone()
            if not stok_data or stok_data["jumlah_stok"] < jumlah:
                raise ValueError(f"Stok obat {kode_obat} di cabang {kode_cabang} tidak mencukupi!")

            # 2. Ambil harga obat
            cur.execute("SELECT harga_jual FROM obat WHERE kode_obat = %s", (kode_obat,))
            obat_data = cur.fetchone()
            if not obat_data:
                raise ValueError(f"Obat {kode_obat} tidak ditemukan!")
            
            harga = obat_data["harga_jual"]
            subtotal = harga * jumlah

            # 3. Cari id_penjualan berdasarkan nomor faktur
            cur.execute("SELECT id_penjualan FROM penjualan WHERE nomor_faktur = %s", (faktur,))
            penjualan_data = cur.fetchone()
            if not penjualan_data:
                raise ValueError(f"Faktur {faktur} belum terdaftar di tabel penjualan!")

            id_penjualan = penjualan_data["id_penjualan"]

            # 4. Insert detail penjualan dengan parameterized query
            sql_insert = """
                INSERT INTO detail_penjualan (id_penjualan, kode_obat, jumlah, harga_satuan, subtotal)
                VALUES (%s, %s, %s, %s, %s)
            """
            cur.execute(sql_insert, (id_penjualan, kode_obat, jumlah, harga, subtotal))

            # 5. Potong stok cabang
            sql_update = """
                UPDATE stok
                SET jumlah_stok = jumlah_stok - %s
                WHERE kode_cabang = %s AND kode_obat = %s AND jumlah_stok >= %s
            """
            cur.execute(sql_update, (jumlah, kode_cabang, kode_obat, jumlah))

        conn.commit()
        return True, "Transaksi berhasil disimpan dengan aman (ACID & Prepared Statement)."
    except Exception as e:
        conn.rollback()
        return False, f"Transaksi dibatalkan (ROLLBACK): {e}"

def bandingkan_kueri_laporan(conn, tahun=2026, bulan=11):
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
    """
    # 1. Jalankan Kueri Lama
    t0 = time.perf_counter()
    sql_lama = """
        SELECT * FROM penjualan p, detail_penjualan d
        WHERE p.id_penjualan = d.id_penjualan
          AND YEAR(p.tanggal_jam) = %s AND MONTH(p.tanggal_jam) = %s
    """
    with conn.cursor() as cur:
        cur.execute(sql_lama, (tahun, bulan))
        res_lama = cur.fetchall()
    t1 = time.perf_counter()
    waktu_lama = (t1 - t0) * 1000  # milidetik

    # 2. Jalankan Kueri Baru Teroptimasi
    bulan_next = bulan + 1 if bulan < 12 else 1
    tahun_next = tahun if bulan < 12 else tahun + 1
    start_date = f"{tahun:04d}-{bulan:02d}-01 00:00:00"
    end_date = f"{tahun_next:04d}-{bulan_next:02d}-01 00:00:00"

    t2 = time.perf_counter()
    sql_baru = """
        SELECT p.nomor_faktur, p.tanggal_jam, p.kode_cabang, d.kode_obat, d.jumlah, d.subtotal
        FROM penjualan p
        INNER JOIN detail_penjualan d ON d.id_penjualan = p.id_penjualan
        WHERE p.tanggal_jam >= %s AND p.tanggal_jam < %s
    """
    with conn.cursor() as cur:
        cur.execute(sql_baru, (start_date, end_date))
        res_baru = cur.fetchall()
    t3 = time.perf_counter()
    waktu_baru = (t3 - t2) * 1000

    return {
        "waktu_lama_ms": round(waktu_lama, 3),
        "waktu_baru_ms": round(waktu_baru, 3),
        "total_data": len(res_baru),
        "sql_lama": sql_lama.strip(),
        "sql_baru": sql_baru.strip()
    }
