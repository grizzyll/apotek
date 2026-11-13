import pymysql

def replicate_to_staging():
    print("Menduplikasi skema dan data eksisting dari 'apotek' ke 'apotek_staging'...")
    conn = pymysql.connect(
        host="localhost",
        port=3306,
        user="root",
        password="",
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True
    )
    
    with conn.cursor() as cur:
        cur.execute("CREATE DATABASE IF NOT EXISTS apotek_staging CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci")
        
        # Ambil semua tabel dasar (bukan view)
        cur.execute("""
            SELECT TABLE_NAME 
            FROM information_schema.TABLES 
            WHERE TABLE_SCHEMA = 'apotek' AND TABLE_TYPE = 'BASE TABLE'
        """)
        base_tables = [r["TABLE_NAME"] for r in cur.fetchall()]
        
        # Buat tabel dan copy data
        for t in base_tables:
            cur.execute(f"DROP TABLE IF EXISTS apotek_staging.`{t}`")
            cur.execute(f"CREATE TABLE apotek_staging.`{t}` LIKE apotek.`{t}`")
            cur.execute(f"INSERT INTO apotek_staging.`{t}` SELECT * FROM apotek.`{t}`")
            print(f"  ✅ Tabel '{t}' berhasil disalin ke apotek_staging.")
            
        # Replikasi Views
        views = [
            "v_penjualan_cabang",
            "v_stok_cabang",
            "v_stok_kritis",
            "v_stok_kritis_cabang",
            "v_profil_saya"
        ]
        for v in views:
            cur.execute(f"SHOW CREATE VIEW apotek.`{v}`")
            row = cur.fetchone()
            create_sql = row["Create View"]
            # Ganti referensi `apotek`. jika ada
            create_sql = create_sql.replace("`apotek`.", "`apotek_staging`.")
            cur.execute(f"DROP VIEW IF EXISTS apotek_staging.`{v}`")
            cur.execute(f"USE apotek_staging")
            cur.execute(create_sql)
            print(f"  ✅ View '{v}' berhasil dibuat di apotek_staging.")
            
        # Replikasi Function & Stored Procedure lama
        cur.execute("USE apotek_staging")
        cur.execute("""
            CREATE OR REPLACE DEFINER=`root`@`localhost` FUNCTION `fn_total_faktur` (`p_faktur` VARCHAR(20)) 
            RETURNS DECIMAL(14,2) READS SQL DATA 
            RETURN (
                SELECT COALESCE(SUM(d.subtotal), 0)
                FROM detail_penjualan d
                JOIN penjualan p ON p.id_penjualan = d.id_penjualan
                WHERE p.nomor_faktur = p_faktur
            )
        """)
        print("  ✅ Function fn_total_faktur berhasil disalin ke apotek_staging.")

        # Grants pada apotek_staging
        grants = [
            "GRANT ALL PRIVILEGES ON apotek_staging.* TO 'admin.pusat'@'localhost'",
            "GRANT EXECUTE, SELECT ON apotek_staging.* TO 'kasir.depok'@'localhost'",
            "GRANT EXECUTE, SELECT ON apotek_staging.* TO 'kasir.bekasi'@'localhost'",
            "GRANT EXECUTE, SELECT ON apotek_staging.* TO 'apoteker.depok'@'localhost'",
            "FLUSH PRIVILEGES"
        ]
        for g in grants:
            try:
                cur.execute(g)
            except Exception as e:
                print(f"  ⚠️ Warning grant: {e}")
        print("  ✅ Hak akses pengguna ke apotek_staging berhasil diset.")

    conn.close()
    print("Duplikasi ke apotek_staging selesai!")

if __name__ == "__main__":
    replicate_to_staging()
