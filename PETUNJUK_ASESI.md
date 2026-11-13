# PANDUAN DEMONSTRASI ASESI (SKEMA PROGRAMMER BASIS DATA)
**Proyek:** Sistem Inventori dan Penjualan Apotek Multi-Cabang  
**Aplikasi:** PT Sehat Bersama Farma (Streamlit App)

---

## 🚀 Cara Menjalankan Aplikasi

Buka PowerShell di folder proyek lalu jalankan:
```powershell
cd D:\apotek_app
streamlit run app.py
```
Aplikasi akan otomatis terbuka di browser pada alamat: `http://localhost:8501`

---

## 🎯 Panduan Demonstrasi Wajib di Depan Asesor (20 Menit)

### 1. Demonstrasi Hak Akses & Keamanan Akun (Action 6 & 14)
- **Tunjukkan Sidebar:**
  - Pilih peran `Kasir Depok (CBG-01)` -> Klik **Login**.
  - Tunjukkan bahwa aplikasi terhubung sebagai akun database `kasir.depok@localhost` (BUKAN root).
- **Buka Tab 2 (Master Obat):**
  - Coba klik tombol "Update Harga Obat".
  - Tunjukkan bahwa database MariaDB langsung **MENOLAK (Error 1142: UPDATE command denied)**.
  - Sekarang logout, pilih profil `Admin Pusat`, lalu login kembali.
  - Update harga obat berhasil! Ini membuktikan penerapan prinsip *least privilege*.

### 2. Demonstrasi Transaksi Penjualan & Keranjang (Action 3, 5, 6)
- **Login sebagai `Kasir Depok (CBG-01)`**
- **Buka Tab 1 (Transaksi & Keranjang):**
  - Pilih obat bebas (misal `OBT-001 - Paracetamol`), masukkan jumlah 2, klik "Masukkan Keranjang".
  - Tunjukkan bahwa keranjang belanja berupa struktur data `List of Dict` yang dinamis (Action 3).
  - Klik "Simpan Transaksi". Transaksi berhasil disimpan melalui Stored Procedure `sp_simpan_penjualan` dan stok berkurang otomatis secara real-time.
- **Uji Coba Penolakan Bisnis (Tombol Cepat):**
  - **Uji 1 (Kasir Jual Obat Keras):** Klik tombol "Uji 1: Kasir Jual Obat Keras" -> Muncul penolakan: *"DITOLAK: Obat Keras hanya boleh dijual oleh Apoteker"*.
  - **Uji 2 (Stok Tidak Cukup):** Klik tombol "Uji 2: Transaksi Melebihi Stok" -> Muncul penolakan: *"DITOLAK: stok tidak mencukupi"* dan seluruh transaksi di-ROLLBACK.
  - **Uji 3 (Cabang Lain):** Klik tombol "Uji 3: Transaksi di Cabang Lain" -> Muncul penolakan: *"DITOLAK: pengguna tidak boleh bertransaksi di cabang lain"*.

### 3. Demonstrasi Row-Level Security / View Cabang (Action 6)
- **Buka Tab 3 (View Cabang Terproteksi):**
  - Saat login sebagai `Kasir Depok`, pada tabel `v_stok_cabang` hanya muncul data cabang `CBG-01`.
  - Logout, lalu login sebagai `Kasir Bekasi`. Tabel otomatis hanya menampilkan `CBG-02`.
  - Logout, lalu login sebagai `Admin Pusat`. Tabel menampilkan seluruh cabang (`CBG-01`, `CBG-02`, `CBG-03`).

### 4. Demonstrasi Algoritma Searching & Sorting (Action 7)
- **Buka Tab 2 (Master Obat & Algoritma):**
  - Tunjukkan fitur **Linear Search O(N)** untuk mencari obat berdasarkan nama/kode.
  - Tunjukkan fitur **Binary Search O(log N)** untuk pencarian cepat data terurut.
  - Tunjukkan pengurutan menggunakan **Quick Sort O(N log N)** dari harga termurah ke termahal.

### 5. Demonstrasi Debugging & Code Review (Action 8 & 9)
- **Buka Tab 4 (Debugging & Code Review):**
  - Tunjukkan perbandingan kode warisan lama vs kode baru yang sudah menerapkan *Parameterized Query*, penanganan error, dan *ROLLBACK*.
  - Klik tombol "Uji Performa Kueri Sekarang". Tunjukkan perbandingan waktu eksekusi: kueri baru teroptimasi jauh lebih cepat karena menggunakan index range date (sargable query) dibandingkan fungsi `YEAR()/MONTH()`.

### 6. Demonstrasi Pemantauan Resource (Action 12)
- **Buka Tab 5 (Pemantauan Resource):**
  - Tunjukkan metrik CPU, RAM, Disk, Koneksi Database Aktif, dan Latensi Respon Kueri.
  - Tunjukkan visualisasi garis batas atas sebelum kegagalan (*Failure Threshold Line* 90%).

### 7. Demonstrasi Environment Switcher (Action 10)
- **Lihat Sidebar:**
  - Ubah dropdown environment dari `DEV` ke `STAGING` atau `PROD`.
  - Tunjukkan bahwa file konfigurasi `.ini` otomatis berganti target database dan level log-nya tanpa mengubah source code.

### 8. Demonstrasi Manajemen Batch & Penjualan FEFO (Action 11 & 13)
- **Buka Tab Baru: "⏳ Status Kedaluwarsa" (Tab 4 untuk Kasir/Apoteker, Tab 5 untuk Admin):**
  - Tunjukkan tabel monitoring masa berlaku obat lengkap dengan kolom **Status**:
    - `🟢 Masih Aman`: Batch obat aktif yang aman dijual (didukung filter status dan pencarian obat).
    - `🔴 Kadaluarsa`: Batch obat yang telah melewati tanggal kedaluwarsa dan otomatis diblokir dari penjualan.
  - Tunjukkan KPI ringkasan: Total Batch Terdaftar, Status Masih Aman, dan Status Kadaluarsa beserta banner peringatan farmasi BPOM.
- **Verifikasi Penjualan Algoritma FEFO (First Expired, First Out):**
  - Saat transaksi disimpan, Stored Procedure `sp_simpan_penjualan_fefo` otomatis memilih dan memotong stok dari nomor batch yang tanggal kedaluwarsanya paling awal.
  - Jika satu batch tidak mencukupi, sistem secara otomatis melakukan *split batch* ke batch berikutnya yang masih aktif.
  - Batch dengan status `🔴 Kadaluarsa` otomatis di-skip dan tidak akan dijual ke konsumen.
- **Verifikasi Skrip Migrasi & Rollback (Action 13):**
  - Migrasi diterapkan pada basis data `apotek` dan `apotek_staging` melalui script: `python -m scripts.run_migration`.
  - Rencana pemulihan darurat (*rollback*) telah disiapkan pada: `sql/04_rollback_fefo.sql`.
  - Dokumen resmi analisis dampak perubahan: [docs/analisis_dampak_perubahan_fefo.md](docs/analisis_dampak_perubahan_fefo.md).
