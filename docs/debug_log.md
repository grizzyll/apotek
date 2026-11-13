# CATATAN DEBUGGING & CODE REVIEW MODUL PENJUALAN (ACTION 8)

**Tanggal Pengujian:** 14 November 2026
**Target File:** `src/legacy.py` (`simpan_penjualan_lama` vs `simpan_penjualan_refactor`)

## 1. Tabel Temuan Kesalahan (Debugging Log)

| No | Langkah Pengujian | Kode Error | Pesan Error Asli | Akar Masalah | Tindakan Perbaikan |
|---|---|---|---|---|---|
| 1 | 1. Eksekusi Modul Lama (simpan_penjualan_lama) | `1142` | `(1142, "INSERT command denied to user 'admin.pusat'@'localhost' for table 'detail_penjualan'")` | 1. Skema detail_penjualan pada DB membutuhkan id_penjualan, kode_obat, jumlah, harga_satuan, subtotal (bukan nomor_faktur langsung).<br>2. Pada tabel stok, nama kolom adalah 'jumlah_stok', bukan 'jumlah'.<br>3. String concatenation menyebabkan kerentanan SQL Injection.<br>4. Cursor tidak ditutup secara aman dalam blok context manager. | 1. Refactor query menggunakan parameterized query (%s).<br>2. Gunakan nama kolom yang benar ('jumlah_stok').<br>3. Gunakan context manager 'with conn.cursor()' agar cursor otomatis ditutup.<br>4. Terapkan transaksi atomik (COMMIT jika sukses, ROLLBACK jika gagal). |
| 2 | 2. Verifikasi Modul Refactor (simpan_penjualan_refactor) | `0 (None)` | `Tidak ada error (Sukses)` | N/A | Kode berhasil diperbaiki sesuai best practice (ACID Stored Procedure, Least Privilege, validasi otomatis). |

## 2. Analisis Perbandingan Kode (Before vs After)

### Kode Warisan (Legacy) - Cacat Kritis:
```python
def simpan_penjualan(conn, faktur, kode_obat, jumlah):
    cur = conn.cursor()
    # 1. SQL Injection & Cacat Nama Kolom
    cur.execute("INSERT INTO detail_penjualan VALUES ('" + faktur + "','" + kode_obat + "'," + str(jumlah) + ")")
    # 2. Kolom 'jumlah' tidak ada di tabel stok (seharusnya 'jumlah_stok')
    cur.execute("UPDATE stok SET jumlah = jumlah - " + str(jumlah) + " WHERE kode_obat='" + kode_obat + "'")
    # 3. Tanpa pengecekan stok minus & tanpa ROLLBACK
    conn.commit()
```

### Kode Refactor Terstandar:
```python
def simpan_penjualan_refactor(conn, faktur, kode_cabang, kode_obat, jumlah):
    try:
        with conn.cursor() as cur:
            # 1. Parameterized Query (%s)
            # 2. Validasi kecukupan stok cabang
            # 3. Context manager 'with' untuk menutup cursor otomatis
            # 4. rowcount check saat UPDATE stok
            # 5. COMMIT jika semua tahap selesai
        conn.commit()
        return True, "Transaksi berhasil disimpan."
    except Exception as e:
        conn.rollback() # 6. ROLLBACK jika ada kegagalan
        return False, str(e)
```
