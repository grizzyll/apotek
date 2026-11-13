-- ==============================================================================
-- SQL MIGRATION SCRIPT: 03_migration_fefo.sql
-- Proyek     : Sistem Inventori & Penjualan Apotek Multi-Cabang
-- Perusahaan : PT Sehat Bersama Farma
-- Fitur      : Manajemen Batch Obat & Penjualan FEFO (First Expired, First Out)
-- Standar    : Action 11 & 13 (J.620100.043.01 & J.620100.047.01)
-- Target DB  : apotek_staging / apotek_prod
-- ==============================================================================

USE apotek;

-- ------------------------------------------------------------------------------
-- 1. TABEL BARU: batch_obat
-- Mencatat detail nomor batch pabrikan dan tanggal kedaluwarsa per cabang
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `batch_obat` (
  `id_batch` INT(11) NOT NULL AUTO_INCREMENT,
  `kode_cabang` VARCHAR(10) NOT NULL,
  `kode_obat` VARCHAR(15) NOT NULL,
  `nomor_batch` VARCHAR(30) NOT NULL,
  `tgl_kadaluarsa` DATE NOT NULL,
  `jumlah_stok` INT(11) NOT NULL DEFAULT 0 CHECK (`jumlah_stok` >= 0),
  `tgl_masuk` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id_batch`),
  UNIQUE KEY `uk_cabang_obat_batch` (`kode_cabang`, `kode_obat`, `nomor_batch`),
  KEY `idx_batch_fefo` (`kode_cabang`, `kode_obat`, `tgl_kadaluarsa`, `jumlah_stok`),
  CONSTRAINT `fk_batch_cabang` FOREIGN KEY (`kode_cabang`) REFERENCES `cabang` (`kode_cabang`),
  CONSTRAINT `fk_batch_obat` FOREIGN KEY (`kode_obat`) REFERENCES `obat` (`kode_obat`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ------------------------------------------------------------------------------
-- 2. ALTER TABLE: detail_penjualan (Mencatat id_batch yang terjual)
-- ------------------------------------------------------------------------------
-- Menambahkan kolom id_batch jika belum ada
SET @col_exists = (
    SELECT COUNT(*) FROM information_schema.COLUMNS 
    WHERE TABLE_SCHEMA = DATABASE() 
      AND TABLE_NAME = 'detail_penjualan' 
      AND COLUMN_NAME = 'id_batch'
);

SET @sql_alter = IF(@col_exists = 0, 
    'ALTER TABLE `detail_penjualan` ADD COLUMN `id_batch` INT(11) NULL AFTER `kode_obat`, ADD CONSTRAINT `fk_detail_batch` FOREIGN KEY (`id_batch`) REFERENCES `batch_obat` (`id_batch`)',
    'SELECT "Kolom id_batch sudah ada" AS notice'
);
PREPARE stmt FROM @sql_alter;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- ------------------------------------------------------------------------------
-- 3. MIGRASI DATA EXISTING: Menyuntikkan Default Batch untuk Data Stok Lama
-- Mengisi batch_obat dari data stok yang ada dengan tgl_kadaluarsa konservatif (+12 bulan)
-- ------------------------------------------------------------------------------
INSERT IGNORE INTO `batch_obat` (kode_cabang, kode_obat, nomor_batch, tgl_kadaluarsa, jumlah_stok)
SELECT 
    s.kode_cabang,
    s.kode_obat,
    CONCAT('INIT-', s.kode_cabang, '-', SUBSTRING(MD5(s.kode_obat), 1, 6)),
    DATE_ADD(CURRENT_DATE, INTERVAL 12 MONTH),
    s.jumlah_stok
FROM `stok` s
WHERE s.jumlah_stok > 0;

-- ------------------------------------------------------------------------------
-- 4. VIEW ROW-LEVEL SECURITY: v_stok_batch_cabang & v_batch_near_expired
-- ------------------------------------------------------------------------------
CREATE OR REPLACE DEFINER=`root`@`localhost` SQL SECURITY DEFINER VIEW `v_stok_batch_cabang` AS
SELECT 
    b.id_batch,
    b.kode_cabang,
    c.nama_cabang,
    b.kode_obat,
    o.nama_obat,
    b.nomor_batch,
    b.tgl_kadaluarsa,
    DATEDIFF(b.tgl_kadaluarsa, CURRENT_DATE) AS sisa_hari_kadaluarsa,
    b.jumlah_stok,
    o.stok_minimum,
    CASE 
        WHEN b.tgl_kadaluarsa <= CURRENT_DATE THEN 'KADALUARSA'
        WHEN DATEDIFF(b.tgl_kadaluarsa, CURRENT_DATE) <= 90 THEN 'MENDEKATI_KADALUARSA'
        ELSE 'AMAN'
    END AS status_kadaluarsa
FROM `batch_obat` b
JOIN `obat` o ON o.kode_obat = b.kode_obat
JOIN `cabang` c ON c.kode_cabang = b.kode_cabang
JOIN `pengguna` p ON p.username = SUBSTRING_INDEX(USER(), '@', 1)
WHERE p.peran = 'ADMIN_PUSAT' OR p.kode_cabang = b.kode_cabang;

-- ------------------------------------------------------------------------------
-- 5. REFAKTOR STORED PROCEDURE: sp_simpan_penjualan_fefo
-- Logika FEFO: Mengambil batch dengan tgl_kadaluarsa terdekat yang masih memiliki stok
-- ------------------------------------------------------------------------------
DELIMITER $$

CREATE OR REPLACE DEFINER=`root`@`localhost` PROCEDURE `sp_simpan_penjualan_fefo` (
    IN `p_faktur` VARCHAR(20),
    IN `p_cabang` VARCHAR(10),
    IN `p_items` TEXT
)
BEGIN
  DECLARE v_username     VARCHAR(80);
  DECLARE v_id_pengguna  INT;
  DECLARE v_peran        VARCHAR(20);
  DECLARE v_cabang_user  VARCHAR(10);
  DECLARE v_id_penjualan INT;
  DECLARE v_n            INT;
  DECLARE v_i            INT DEFAULT 0;
  DECLARE v_kode         VARCHAR(15);
  DECLARE v_qty_needed   INT;
  DECLARE v_qty_rem      INT;
  DECLARE v_harga        DECIMAL(12,2);
  DECLARE v_kategori     VARCHAR(50);
  
  -- Variabel Cursor Batch FEFO
  DECLARE v_b_id         INT;
  DECLARE v_b_stok       INT;
  DECLARE v_b_tgl        DATE;
  DECLARE v_potong       INT;
  DECLARE v_done         INT DEFAULT FALSE;

  -- Cursor mengambil batch aktif terurut tanggal kedaluwarsa terdekat (FEFO)
  DECLARE cur_batch CURSOR FOR 
    SELECT id_batch, jumlah_stok, tgl_kadaluarsa
    FROM batch_obat
    WHERE kode_cabang = p_cabang
      AND kode_obat = v_kode
      AND jumlah_stok > 0
      AND tgl_kadaluarsa > CURRENT_DATE
    ORDER BY tgl_kadaluarsa ASC, id_batch ASC;

  DECLARE CONTINUE HANDLER FOR NOT FOUND SET v_done = TRUE;

  DECLARE EXIT HANDLER FOR SQLEXCEPTION
  BEGIN
    ROLLBACK;
    SET @log_faktur = NULL;
    RESIGNAL;
  END;

  START TRANSACTION;
  SET @log_faktur = p_faktur;

  -- 1. Validasi Akun
  SET v_username = SUBSTRING_INDEX(USER(), '@', 1);
  SET v_id_pengguna = NULL;
  SELECT id_pengguna, peran, kode_cabang
    INTO v_id_pengguna, v_peran, v_cabang_user
  FROM pengguna WHERE username = v_username;

  IF v_id_pengguna IS NULL THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'DITOLAK: akun tidak terdaftar sebagai pengguna aplikasi';
  END IF;

  -- 2. Validasi Batas Cabang
  IF v_peran <> 'ADMIN_PUSAT' AND NOT (v_cabang_user <=> p_cabang) THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'DITOLAK: pengguna tidak boleh bertransaksi di cabang lain';
  END IF;

  -- 3. Validasi JSON Payload
  IF p_items IS NULL OR NOT JSON_VALID(p_items) OR JSON_LENGTH(p_items) = 0 THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'DITOLAK: daftar item kosong atau format salah';
  END IF;

  -- 4. Header Penjualan
  INSERT INTO penjualan (nomor_faktur, kode_cabang, id_pengguna, total)
  VALUES (p_faktur, p_cabang, v_id_pengguna, 0);
  SET v_id_penjualan = LAST_INSERT_ID();

  -- 5. Loop Setiap Item Transaksi
  SET v_n = JSON_LENGTH(p_items);
  WHILE v_i < v_n DO
    SET v_kode       = JSON_VALUE(p_items, CONCAT('$[', v_i, '].kode_obat'));
    SET v_qty_needed = JSON_VALUE(p_items, CONCAT('$[', v_i, '].jumlah'));
    SET v_qty_rem    = v_qty_needed;

    IF v_qty_needed IS NULL OR v_qty_needed <= 0 THEN
      SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'DITOLAK: jumlah harus lebih dari 0';
    END IF;

    -- Validasi Harga & Kategori
    SET v_harga = NULL;
    SELECT o.harga_jual, k.nama_kategori INTO v_harga, v_kategori
    FROM obat o JOIN kategori_obat k ON k.kode_kategori = o.kode_kategori
    WHERE o.kode_obat = v_kode;

    IF v_harga IS NULL THEN
      SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'DITOLAK: kode obat tidak ditemukan';
    END IF;

    -- Aturan Bisnis Obat Keras
    IF v_kategori = 'Obat Keras' AND v_peran <> 'APOTEKER' THEN
      SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'DITOLAK: Obat Keras hanya boleh dijual oleh Apoteker';
    END IF;

    -- ALGORITMA FEFO: Potong dari batch terdekat
    SET v_done = FALSE;
    OPEN cur_batch;
    read_loop: LOOP
      FETCH cur_batch INTO v_b_id, v_b_stok, v_b_tgl;
      IF v_done OR v_qty_rem <= 0 THEN
        LEAVE read_loop;
      END IF;

      IF v_b_stok >= v_qty_rem THEN
        SET v_potong = v_qty_rem;
      ELSE
        SET v_potong = v_b_stok;
      END IF;

      -- Potong stok batch
      UPDATE batch_obat 
         SET jumlah_stok = jumlah_stok - v_potong
       WHERE id_batch = v_b_id;

      -- Rekam detail penjualan beserta id_batch
      INSERT INTO detail_penjualan (id_penjualan, kode_obat, id_batch, jumlah, harga_satuan, subtotal)
      VALUES (v_id_penjualan, v_kode, v_b_id, v_potong, v_harga, v_potong * v_harga);

      SET v_qty_rem = v_qty_rem - v_potong;
    END LOOP;
    CLOSE cur_batch;

    -- Jika stok batch aktif tidak mencukupi
    IF v_qty_rem > 0 THEN
      SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'DITOLAK: stok tidak mencukupi atau obat sudah kedaluwarsa';
    END IF;

    -- Sinkronisasi tabel agregat stok cabang
    UPDATE stok
       SET jumlah_stok = jumlah_stok - v_qty_needed
     WHERE kode_cabang = p_cabang
       AND kode_obat   = v_kode
       AND jumlah_stok >= v_qty_needed;

    SET v_i = v_i + 1;
  END WHILE;

  -- 6. Update Total Faktur
  UPDATE penjualan SET total = fn_total_faktur(p_faktur)
  WHERE id_penjualan = v_id_penjualan;

  COMMIT;
  SET @log_faktur = NULL;
END$$

DELIMITER ;
