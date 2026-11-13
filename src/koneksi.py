import os
import configparser
import pymysql

CONFIG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config")

def get_config(env="dev"):
    """Membaca konfigurasi environment (dev / staging / prod)"""
    file_path = os.path.join(CONFIG_DIR, f"{env}.ini")
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File konfigurasi tidak ditemukan: {file_path}")
    
    config = configparser.ConfigParser()
    config.read(file_path)
    return config["database"]

def get_connection(user, password, env="dev", database_override=None):
    """
    Membuka koneksi database dengan kredensial peran tertentu (bukan root).
    Transaksi dikontrol secara manual (autocommit=False).
    """
    db_cfg = get_config(env)
    
    dbname = database_override if database_override else db_cfg.get("dbname", "apotek")
    
    conn = pymysql.connect(
        host=db_cfg.get("host", "localhost"),
        port=int(db_cfg.get("port", 3306)),
        user=user,
        password=password,
        database=dbname,
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=False
    )
    return conn
