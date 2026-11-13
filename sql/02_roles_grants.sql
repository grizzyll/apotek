-- ============================================================================
-- SQL Script: 02_roles_grants.sql
-- Deskripsi : Pembuatan Pengguna dan Penetapan Hak Akses (Principle of Least Privilege)
-- Peran     : kasir.depok, apoteker.depok, kasir.bekasi, admin.pusat
-- Host      : localhost
-- Catatan   : Ganti placeholder ${PASSWORD_...} dengan kata sandi dari file .env
--             sebelum mengeksekusi file ini.
-- ============================================================================

-- Pastikan database aktif adalah apotek
USE apotek;

-- ----------------------------------------------------------------------------
-- 1. VIEW PROFIL PENGGUNA TERISOLASI (v_profil_saya)
-- View ini menyaring data pengguna berdasarkan akun database yang login saat ini
-- ----------------------------------------------------------------------------
CREATE OR REPLACE DEFINER=`root`@`localhost` SQL SECURITY DEFINER VIEW `v_profil_saya` AS
SELECT 
    id_pengguna, 
    username, 
    nama_lengkap, 
    peran, 
    kode_cabang
FROM pengguna
WHERE username = SUBSTRING_INDEX(USER(), '@', 1);

-- ----------------------------------------------------------------------------
-- 2. PEMBUATAN AKUN PENGGUNA BASIS DATA
-- ----------------------------------------------------------------------------
CREATE USER IF NOT EXISTS 'kasir.depok'@'localhost' IDENTIFIED BY '${PASSWORD_KASIR_DEPOK}';
CREATE USER IF NOT EXISTS 'apoteker.depok'@'localhost' IDENTIFIED BY '${PASSWORD_APOTEKER_DEPOK}';
CREATE USER IF NOT EXISTS 'kasir.bekasi'@'localhost' IDENTIFIED BY '${PASSWORD_KASIR_BEKASI}';
CREATE USER IF NOT EXISTS 'admin.pusat'@'localhost' IDENTIFIED BY '${PASSWORD_ADMIN_PUSAT}';

-- ----------------------------------------------------------------------------
-- 3. HAK AKSES PERAN KASIR & APOTEKER (LEAST PRIVILEGE)
--    - Boleh membaca master obat & kategori obat
--    - Boleh mengeksekusi Stored Procedure transaksi penjualan & fungsi total faktur
--    - Boleh membaca profil pribadi via view v_profil_saya
--    - Boleh membaca data cabang via views yang terisolasi otomatis
--    - DILARANG KERAS akses langsung ke tabel dasar: stok, penjualan, detail_penjualan, pengguna
-- ----------------------------------------------------------------------------

-- Kasir Depok
REVOKE ALL PRIVILEGES, GRANT OPTION FROM 'kasir.depok'@'localhost';
GRANT USAGE ON *.* TO 'kasir.depok'@'localhost';
GRANT SELECT ON apotek.obat TO 'kasir.depok'@'localhost';
GRANT SELECT ON apotek.kategori_obat TO 'kasir.depok'@'localhost';
GRANT SELECT ON apotek.v_profil_saya TO 'kasir.depok'@'localhost';
GRANT SELECT ON apotek.v_stok_cabang TO 'kasir.depok'@'localhost';
GRANT SELECT ON apotek.v_penjualan_cabang TO 'kasir.depok'@'localhost';
GRANT SELECT ON apotek.v_stok_kritis_cabang TO 'kasir.depok'@'localhost';
GRANT EXECUTE ON PROCEDURE apotek.sp_simpan_penjualan TO 'kasir.depok'@'localhost';
GRANT EXECUTE ON FUNCTION apotek.fn_total_faktur TO 'kasir.depok'@'localhost';

-- Apoteker Depok
REVOKE ALL PRIVILEGES, GRANT OPTION FROM 'apoteker.depok'@'localhost';
GRANT USAGE ON *.* TO 'apoteker.depok'@'localhost';
GRANT SELECT ON apotek.obat TO 'apoteker.depok'@'localhost';
GRANT SELECT ON apotek.kategori_obat TO 'apoteker.depok'@'localhost';
GRANT SELECT ON apotek.v_profil_saya TO 'apoteker.depok'@'localhost';
GRANT SELECT ON apotek.v_stok_cabang TO 'apoteker.depok'@'localhost';
GRANT SELECT ON apotek.v_penjualan_cabang TO 'apoteker.depok'@'localhost';
GRANT SELECT ON apotek.v_stok_kritis_cabang TO 'apoteker.depok'@'localhost';
GRANT EXECUTE ON PROCEDURE apotek.sp_simpan_penjualan TO 'apoteker.depok'@'localhost';
GRANT EXECUTE ON FUNCTION apotek.fn_total_faktur TO 'apoteker.depok'@'localhost';

-- Kasir Bekasi
REVOKE ALL PRIVILEGES, GRANT OPTION FROM 'kasir.bekasi'@'localhost';
GRANT USAGE ON *.* TO 'kasir.bekasi'@'localhost';
GRANT SELECT ON apotek.obat TO 'kasir.bekasi'@'localhost';
GRANT SELECT ON apotek.kategori_obat TO 'kasir.bekasi'@'localhost';
GRANT SELECT ON apotek.v_profil_saya TO 'kasir.bekasi'@'localhost';
GRANT SELECT ON apotek.v_stok_cabang TO 'kasir.bekasi'@'localhost';
GRANT SELECT ON apotek.v_penjualan_cabang TO 'kasir.bekasi'@'localhost';
GRANT SELECT ON apotek.v_stok_kritis_cabang TO 'kasir.bekasi'@'localhost';
GRANT EXECUTE ON PROCEDURE apotek.sp_simpan_penjualan TO 'kasir.bekasi'@'localhost';
GRANT EXECUTE ON FUNCTION apotek.fn_total_faktur TO 'kasir.bekasi'@'localhost';

-- ----------------------------------------------------------------------------
-- 4. HAK AKSES PERAN ADMIN PUSAT
--    - Boleh CRUD penuh tabel master: obat, cabang, pengguna
--    - Boleh membaca seluruh view
--    - Boleh mengeksekusi stored procedure & function
-- ----------------------------------------------------------------------------
REVOKE ALL PRIVILEGES, GRANT OPTION FROM 'admin.pusat'@'localhost';
GRANT USAGE ON *.* TO 'admin.pusat'@'localhost';
GRANT SELECT ON apotek.* TO 'admin.pusat'@'localhost';
GRANT INSERT, UPDATE, DELETE ON apotek.obat TO 'admin.pusat'@'localhost';
GRANT INSERT, UPDATE, DELETE ON apotek.cabang TO 'admin.pusat'@'localhost';
GRANT INSERT, UPDATE, DELETE ON apotek.pengguna TO 'admin.pusat'@'localhost';
GRANT EXECUTE ON PROCEDURE apotek.sp_simpan_penjualan TO 'admin.pusat'@'localhost';
GRANT EXECUTE ON FUNCTION apotek.fn_total_faktur TO 'admin.pusat'@'localhost';

FLUSH PRIVILEGES;
