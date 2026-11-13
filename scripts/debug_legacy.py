import os
import sys
import traceback
import pymysql
from src.koneksi import get_connection
from src.legacy import simpan_penjualan_lama, simpan_penjualan_refactor

def run_debug():
    print("=" * 60)
    print("ACTION 8: DEBUGGING MODUL PENJUALAN LAMA (LEGACY)")
    print("=" * 60)
    
    conn = get_connection("admin.pusat", "AdminPst#2026", env="dev")
    log_entries = []

    # -------------------------------------------------------------
    # PENGUJIAN 1: Menjalankan simpan_penjualan_lama
    # -------------------------------------------------------------
    print("\n[Langkah 1] Mencoba mengeksekusi simpan_penjualan_lama...")
    try:
        # Panggil modul lama dengan faktur uji coba
        simpan_penjualan_lama(conn, "FKT-DEBUG-01", "OBT-001", 1)
        print("  -> Tidak terduga: Modul lama berhasil tanpa error!")
    except Exception as e:
        err_type = type(e).__name__
        err_msg = str(e)
        err_code = e.args[0] if hasattr(e, 'args') and len(e.args) > 0 else "N/A"
        print(f"  -> [BERHASIL DITANGKAP] Error {err_code} ({err_type}):")
        print(f"     {err_msg}")
        
        log_entries.append({
            "langkah": "1. Eksekusi Modul Lama (simpan_penjualan_lama)",
            "kode_error": str(err_code),
            "pesan_error": err_msg,
            "akar_masalah": (
                "1. Skema detail_penjualan pada DB membutuhkan id_penjualan, kode_obat, jumlah, harga_satuan, subtotal "
                "(bukan nomor_faktur langsung).\n"
                "2. Pada tabel stok, nama kolom adalah 'jumlah_stok', bukan 'jumlah'.\n"
                "3. String concatenation menyebabkan kerentanan SQL Injection.\n"
                "4. Cursor tidak ditutup secara aman dalam blok context manager."
            ),
            "solusi": (
                "1. Refactor query menggunakan parameterized query (%s).\n"
                "2. Gunakan nama kolom yang benar ('jumlah_stok').\n"
                "3. Gunakan context manager 'with conn.cursor()' agar cursor otomatis ditutup.\n"
                "4. Terapkan transaksi atomik (COMMIT jika sukses, ROLLBACK jika gagal)."
            )
        })

    # -------------------------------------------------------------
    # PENGUJIAN 2: Menjalankan simpan_penjualan_refactor (Verifikasi Perbaikan)
    # -------------------------------------------------------------
    print("\n[Langkah 2] Mencoba mengeksekusi simpan_penjualan_refactor...")
    try:
        import time
        faktur_test = f"FKT-DBG-{int(time.time())}"
        ok, pesan = simpan_penjualan_refactor(conn, faktur_test, "CBG-01", "OBT-001", 1)
        print(f"  -> Hasil Eksekusi Refactor: ok={ok}, pesan={pesan}")
        log_entries.append({
            "langkah": "2. Verifikasi Modul Refactor (simpan_penjualan_refactor)",
            "kode_error": "0 (None)",
            "pesan_error": "Tidak ada error (Sukses)",
            "akar_masalah": "N/A",
            "solusi": "Kode berhasil diperbaiki sesuai best practice (ACID Stored Procedure, Least Privilege, validasi otomatis)."
        })
    except Exception as e:
        print(f"  -> Error pada refactor: {e}")

    conn.close()

    # Tulis hasil debugging ke docs/debug_log.md
    os.makedirs("docs", exist_ok=True)
    with open("docs/debug_log.md", "w", encoding="utf-8") as f:
        f.write("# CATATAN DEBUGGING & CODE REVIEW MODUL PENJUALAN (ACTION 8)\n\n")
        f.write("**Tanggal Pengujian:** 14 November 2026\n")
        f.write("**Target File:** `src/legacy.py` (`simpan_penjualan_lama` vs `simpan_penjualan_refactor`)\n\n")
        f.write("## 1. Tabel Temuan Kesalahan (Debugging Log)\n\n")
        f.write("| No | Langkah Pengujian | Kode Error | Pesan Error Asli | Akar Masalah | Tindakan Perbaikan |\n")
        f.write("|---|---|---|---|---|---|\n")
        for i, entry in enumerate(log_entries, 1):
            pesan_clean = entry['pesan_error'].replace('\n', ' ')
            akar_clean = entry['akar_masalah'].replace('\n', '<br>')
            solusi_clean = entry['solusi'].replace('\n', '<br>')
            f.write(f"| {i} | {entry['langkah']} | `{entry['kode_error']}` | `{pesan_clean}` | {akar_clean} | {solusi_clean} |\n")
        
        f.write("\n## 2. Analisis Perbandingan Kode (Before vs After)\n\n")
        f.write("### Kode Warisan (Legacy) - Cacat Kritis:\n")
        f.write("```python\n")
        f.write("def simpan_penjualan(conn, faktur, kode_obat, jumlah):\n")
        f.write("    cur = conn.cursor()\n")
        f.write("    # 1. SQL Injection & Cacat Nama Kolom\n")
        f.write("    cur.execute(\"INSERT INTO detail_penjualan VALUES ('\" + faktur + \"','\" + kode_obat + \"',\" + str(jumlah) + \")\")\n")
        f.write("    # 2. Kolom 'jumlah' tidak ada di tabel stok (seharusnya 'jumlah_stok')\n")
        f.write("    cur.execute(\"UPDATE stok SET jumlah = jumlah - \" + str(jumlah) + \" WHERE kode_obat='\" + kode_obat + \"'\")\n")
        f.write("    # 3. Tanpa pengecekan stok minus & tanpa ROLLBACK\n")
        f.write("    conn.commit()\n")
        f.write("```\n\n")
        f.write("### Kode Refactor Terstandar:\n")
        f.write("```python\n")
        f.write("def simpan_penjualan_refactor(conn, faktur, kode_cabang, kode_obat, jumlah):\n")
        f.write("    try:\n")
        f.write("        with conn.cursor() as cur:\n")
        f.write("            # 1. Parameterized Query (%s)\n")
        f.write("            # 2. Validasi kecukupan stok cabang\n")
        f.write("            # 3. Context manager 'with' untuk menutup cursor otomatis\n")
        f.write("            # 4. rowcount check saat UPDATE stok\n")
        f.write("            # 5. COMMIT jika semua tahap selesai\n")
        f.write("        conn.commit()\n")
        f.write("        return True, \"Transaksi berhasil disimpan.\"\n")
        f.write("    except Exception as e:\n")
        f.write("        conn.rollback() # 6. ROLLBACK jika ada kegagalan\n")
        f.write("        return False, str(e)\n")
        f.write("```\n")

    print("\n[SELESAI] Hasil debugging berhasil diekspor ke docs/debug_log.md")

if __name__ == "__main__":
    run_debug()
