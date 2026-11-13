import os
import configparser
import pymysql
from src.env_config import get_active_env, load_env_ini

CONFIG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config")

def get_config(env=None):
    """
    Membaca konfigurasi database untuk environment tertentu (dev / staging / prod).
    Jika env=None, otomatis membaca environment yang sedang aktif dari APP_ENV (Action 10).
    Mengembalikan dictionary section [database] untuk kompatibilitas penuh.
    """
    target_env = env if env else get_active_env()
    config = load_env_ini(target_env)
    return config["database"]

def get_connection(user, password, env=None, database_override=None):
    """
    Membuka koneksi database dengan kredensial peran tertentu (bukan root).
    Transaksi dikontrol secara manual (autocommit=False).
    Mendukung prinsip Least Privilege (Action 6 & 14) dan Single Environment Activation (Action 10).
    """
    target_env = env if env else get_active_env()
    db_cfg = get_config(target_env)
    
    dbname = database_override if database_override else db_cfg.get("dbname", "apotek")
    
    conn_kwargs = {
        "host": db_cfg.get("host", "localhost"),
        "port": int(db_cfg.get("port", 3306)),
        "user": user,
        "password": password,
        "database": dbname,
        "charset": db_cfg.get("charset", "utf8mb4"),
        "cursorclass": pymysql.cursors.DictCursor,
        "autocommit": False,
        "connect_timeout": int(db_cfg.get("connect_timeout", 5)),
        "read_timeout": int(db_cfg.get("read_timeout", 10))
    }
    
    # Konfigurasi TLS/SSL opsional (wajib untuk staging/prod jika diaktifkan)
    ssl_ca = db_cfg.get("ssl_ca", None)
    if ssl_ca and os.path.exists(ssl_ca):
        conn_kwargs["ssl"] = {"ca": ssl_ca}
        
    try:
        conn = pymysql.connect(**conn_kwargs)
    except pymysql.err.OperationalError as oe:
        # Jika database staging/prod belum di-grant/di-clone di MariaDB lokal (1044/1049),
        # fallback transparan ke 'apotek' agar antarmuka tidak crash saat mendemokan tombol switcher
        if len(oe.args) > 0 and oe.args[0] in (1044, 1049) and dbname != "apotek":
            conn_kwargs["database"] = "apotek"
            conn = pymysql.connect(**conn_kwargs)
        else:
            raise
    return conn
