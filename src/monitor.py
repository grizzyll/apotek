import time
import os
import psutil
import pymysql

# ========================================================
# ACTION 12: RESOURCE MONITORING & AMBANG BATAS (THRESHOLDS)
# ========================================================
BATAS_ATAS = {
    "cpu_percent": {"warning": 75.0, "critical": 90.0, "unit": "%"},
    "ram_percent": {"warning": 80.0, "critical": 90.0, "unit": "%"},
    "disk_percent": {"warning": 80.0, "critical": 90.0, "unit": "%"},
    "db_connections": {"warning": 70, "critical": 90, "unit": "koneksi"},
    "query_latency_ms": {"warning": 100.0, "critical": 300.0, "unit": "ms"}
}

def get_system_resources():
    """Mengambil status penggunaan CPU, RAM, dan Disk Host (lintas platform)"""
    cpu = psutil.cpu_percent(interval=0.2)
    ram = psutil.virtual_memory()
    
    # Deteksi path root storage secara dinamis lintas OS
    drive_root = os.path.splitdrive(os.path.abspath("."))[0] + os.sep if os.name == 'nt' else "/"
    disk = psutil.disk_usage(drive_root)

    return {
        "cpu_percent": cpu,
        "ram_percent": ram.percent,
        "ram_used_mb": round(ram.used / (1024 * 1024), 1),
        "ram_total_mb": round(ram.total / (1024 * 1024), 1),
        "disk_percent": disk.percent,
        "disk_free_gb": round(disk.free / (1024 * 1024 * 1024), 1),
        "drive_monitored": drive_root
    }

def get_database_resources(conn):
    """Mengambil metrik database: jumlah koneksi aktif, max_connections, dan latensi kueri"""
    res = {
        "db_connections": 1,
        "max_connections": 100,
        "query_latency_ms": 0.0,
        "threads_running": 1,
        "status": "NORMAL"
    }
    try:
        with conn.cursor() as cur:
            # 1. Jumlah koneksi aktif di MySQL/MariaDB
            cur.execute("SHOW STATUS LIKE 'Threads_connected'")
            row = cur.fetchone()
            if row:
                res["db_connections"] = int(row.get("Value", 1))

            cur.execute("SHOW STATUS LIKE 'Threads_running'")
            row2 = cur.fetchone()
            if row2:
                res["threads_running"] = int(row2.get("Value", 1))

            # 2. Ambil max_connections dinamis dari server
            cur.execute("SHOW VARIABLES LIKE 'max_connections'")
            row3 = cur.fetchone()
            if row3:
                res["max_connections"] = int(row3.get("Value", 100))

            # 3. Uji latensi kueri ping
            t0 = time.perf_counter()
            cur.execute("SELECT 1")
            cur.fetchone()
            t1 = time.perf_counter()
            res["query_latency_ms"] = round((t1 - t0) * 1000, 2)
    except Exception as e:
        res["status"] = "ERROR"
        res["error_msg"] = str(e)
    
    return res

def evaluasi_status(metrik, nilai):
    """Menentukan status NORMAL, WARNING, atau CRITICAL berdasarkan ambang batas"""
    cfg = BATAS_ATAS.get(metrik)
    if not cfg:
        return "NORMAL"
    if nilai >= cfg["critical"]:
        return "CRITICAL"
    elif nilai >= cfg["warning"]:
        return "WARNING"
    return "NORMAL"
