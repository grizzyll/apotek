import time
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
    """Mengambil status penggunaan CPU, RAM, dan Disk Host"""
    cpu = psutil.cpu_percent(interval=0.2)
    ram = psutil.virtual_memory()
    disk = psutil.disk_usage("D:\\" if "D:\\" in [p.device for p in psutil.disk_partitions()] else "C:\\")

    return {
        "cpu_percent": cpu,
        "ram_percent": ram.percent,
        "ram_used_mb": round(ram.used / (1024 * 1024), 1),
        "ram_total_mb": round(ram.total / (1024 * 1024), 1),
        "disk_percent": disk.percent,
        "disk_free_gb": round(disk.free / (1024 * 1024 * 1024), 1)
    }

def get_database_resources(conn):
    """Mengambil metrik database: jumlah koneksi aktif dan latensi kueri"""
    res = {
        "db_connections": 1,
        "query_latency_ms": 0.0,
        "threads_running": 1
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

            # 2. Uji latensi kueri ping
            t0 = time.perf_counter()
            cur.execute("SELECT 1")
            cur.fetchone()
            t1 = time.perf_counter()
            res["query_latency_ms"] = round((t1 - t0) * 1000, 2)
    except Exception:
        pass
    
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
