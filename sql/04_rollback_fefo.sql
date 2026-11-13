-- ==============================================================================
-- SQL ROLLBACK SCRIPT: 04_rollback_fefo.sql
-- Proyek     : Sistem Inventori & Penjualan Apotek Multi-Cabang
-- Perusahaan : PT Sehat Bersama Farma
-- Fitur      : Rollback Pembaruan Batch & FEFO ke Kondisi Existing (As-Is)
-- Standar    : Action 13 (J.620100.047.01 - Melakukan Pembaharuan Perangkat Lunak)
-- Estimasi   : Eksekusi 5 - 10 Menit
-- ==============================================================================

USE apotek;

START TRANSACTION;

-- ------------------------------------------------------------------------------
-- 1. HAPUS PROSEDUR BARU (sp_simpan_penjualan_fefo)
-- ------------------------------------------------------------------------------
DROP PROCEDURE IF EXISTS `sp_simpan_penjualan_fefo`;

-- ------------------------------------------------------------------------------
-- 2. HAPUS VIEW BARU TERKAIT BATCH
-- ------------------------------------------------------------------------------
DROP VIEW IF EXISTS `v_stok_batch_cabang`;

-- ------------------------------------------------------------------------------
-- 3. HAPUS CONSTRAINT & KOLOM id_batch DARI detail_penjualan
-- ------------------------------------------------------------------------------
SET @fk_exists = (
    SELECT COUNT(*) FROM information_schema.TABLE_CONSTRAINTS 
    WHERE TABLE_SCHEMA = DATABASE() 
      AND TABLE_NAME = 'detail_penjualan' 
      AND CONSTRAINT_NAME = 'fk_detail_batch'
);

SET @sql_drop_fk = IF(@fk_exists > 0, 
    'ALTER TABLE `detail_penjualan` DROP FOREIGN KEY `fk_detail_batch`',
    'SELECT "FK fk_detail_batch tidak ditemukan" AS notice'
);
PREPARE stmt_fk FROM @sql_drop_fk;
EXECUTE stmt_fk;
DEALLOCATE PREPARE stmt_fk;

SET @col_exists = (
    SELECT COUNT(*) FROM information_schema.COLUMNS 
    WHERE TABLE_SCHEMA = DATABASE() 
      AND TABLE_NAME = 'detail_penjualan' 
      AND COLUMN_NAME = 'id_batch'
);

SET @sql_drop_col = IF(@col_exists > 0, 
    'ALTER TABLE `detail_penjualan` DROP COLUMN `id_batch`',
    'SELECT "Kolom id_batch tidak ditemukan" AS notice'
);
PREPARE stmt_col FROM @sql_drop_col;
EXECUTE stmt_col;
DEALLOCATE PREPARE stmt_col;

-- ------------------------------------------------------------------------------
-- 4. HAPUS TABEL batch_obat
-- ------------------------------------------------------------------------------
DROP TABLE IF EXISTS `batch_obat`;

-- ------------------------------------------------------------------------------
-- 5. VERIFIKASI STORED PROCEDURE LAMA TETAP AKTIF
-- ------------------------------------------------------------------------------
SELECT ROUTINE_NAME, ROUTINE_TYPE, DEFINER, CREATED, LAST_ALTERED 
FROM information_schema.ROUTINES 
WHERE ROUTINE_SCHEMA = 'apotek' 
  AND ROUTINE_NAME = 'sp_simpan_penjualan';

COMMIT;

SELECT "ROLLBACK FEFO BERHASIL DITERAPKAN. SISTEM KEMBALI KE VERSI SEBELUMNYA." AS status;
