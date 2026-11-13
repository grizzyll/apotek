"""
Modul Manajemen Konfigurasi Multi-Environment (Action 10: J.620100.042.01)
PT Sehat Bersama Farma - Sistem Basis Data Apotek Multi-Cabang

Menerapkan standar:
1. The Twelve-Factor App (Factor III: Config) — Pemisahan konfigurasi dari kode
2. SNI ISO/IEC 27001 (A.12.1.2) — Pemisahan fasilitas pengembangan, uji coba, dan operasional
3. Single Active Environment — Hanya satu environment yang aktif pada satu waktu
"""

import os
import re
import configparser
from typing import Dict, Any, Optional

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_DIR = os.path.join(PROJECT_ROOT, "config")
ENV_FILE = os.path.join(PROJECT_ROOT, ".env")

VALID_ENVIRONMENTS = ("dev", "staging", "prod")

ENV_METADATA = {
    "dev": {
        "title": "Development (Lokal)",
        "badge": "🛠️ DEV",
        "description": "Pengembangan fitur, pengujian kode baru, dan debugging modul database lokal",
        "target_db": "apotek",
        "log_level": "DEBUG",
        "isolated": True,
    },
    "staging": {
        "title": "Staging (Server Uji)",
        "badge": "🧪 STAGING",
        "description": "Simulasi identik produksi untuk migrasi patch DDL, UAT, dan sertifikasi asesi",
        "target_db": "apotek_staging",
        "log_level": "INFO",
        "isolated": True,
    },
    "prod": {
        "title": "Production (Live Multi-Cabang)",
        "badge": "🚀 PROD",
        "description": "Operasional live transaksi 5 cabang apotek PT Sehat Bersama Farma 24/7",
        "target_db": "apotek_prod",
        "log_level": "WARNING",
        "isolated": False,
    }
}


def get_active_env() -> str:
    """
    Mengambil environment aktif saat ini.
    Hierarki resolusi:
    1. OS Environment Variable `APP_ENV`
    2. File `.env` pada direktori root proyek
    3. Fallback default: 'dev'
    """
    # 1. Cek OS Environment Variable
    env_var = os.getenv("APP_ENV")
    if env_var and env_var.strip().lower() in VALID_ENVIRONMENTS:
        return env_var.strip().lower()

    # 2. Cek file .env
    if os.path.exists(ENV_FILE):
        try:
            with open(ENV_FILE, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("APP_ENV="):
                        val = line.split("=", 1)[1].strip().strip('"').strip("'").lower()
                        if val in VALID_ENVIRONMENTS:
                            return val
        except Exception:
            pass

    # 3. Default fallback
    return "dev"


def set_active_env(target_env: str) -> bool:
    """
    Mengubah environment aktif secara atomik pada file .env (Mekanisme Single Active Environment).
    Memastikan hanya satu environment yang aktif pada satu waktu.
    """
    target = target_env.strip().lower()
    if target not in VALID_ENVIRONMENTS:
        raise ValueError(f"Environment tidak valid: '{target}'. Pilihan yang diizinkan: {VALID_ENVIRONMENTS}")

    # Update file .env
    lines = []
    found = False
    if os.path.exists(ENV_FILE):
        with open(ENV_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()

    new_lines = []
    for line in lines:
        if re.match(r"^\s*APP_ENV\s*=", line):
            new_lines.append(f"APP_ENV={target}\n")
            found = True
        else:
            new_lines.append(line)

    if not found:
        new_lines.insert(0, f"APP_ENV={target}\n")

    with open(ENV_FILE, "w", encoding="utf-8") as f:
        f.writelines(new_lines)

    # Sinkronisasi ke runtime OS env
    os.environ["APP_ENV"] = target
    return True


def load_env_ini(env_name: Optional[str] = None) -> configparser.ConfigParser:
    """
    Membaca dan mem-parsing file .ini untuk environment tertentu.
    Jika env_name tidak diberikan, membaca environment aktif.
    """
    env = (env_name or get_active_env()).strip().lower()
    if env not in VALID_ENVIRONMENTS:
        raise ValueError(f"Environment '{env}' tidak valid. Harus salah satu dari: {VALID_ENVIRONMENTS}")

    file_path = os.path.join(CONFIG_DIR, f"{env}.ini")
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File konfigurasi tidak ditemukan: {file_path}")

    config = configparser.ConfigParser()
    config.read(file_path, encoding="utf-8")
    return config


def get_environment_specification() -> Dict[str, Any]:
    """
    Mengidentifikasi kebutuhan dan spesifikasi perbandingan 3 environment
    (Development, Staging, Production) untuk laporan asesmen dan antarmuka.
    """
    specs = {}
    for code in VALID_ENVIRONMENTS:
        cfg = load_env_ini(code)
        meta = ENV_METADATA[code]
        specs[code] = {
            "code": code,
            "title": meta["title"],
            "badge": meta["badge"],
            "description": meta["description"],
            "host": cfg.get("database", "host", fallback="localhost"),
            "port": cfg.getint("database", "port", fallback=3306),
            "dbname": cfg.get("database", "dbname", fallback="apotek"),
            "log_level": cfg.get("database", "log_level", fallback="INFO"),
            "is_production": cfg.getboolean("environment", "is_production", fallback=False),
            "debug_mode": cfg.getboolean("environment", "debug_mode", fallback=False),
            "allow_demo": cfg.getboolean("environment", "allow_demo_accounts", fallback=True),
            "connect_timeout": cfg.getint("database", "connect_timeout", fallback=5),
            "read_timeout": cfg.getint("database", "read_timeout", fallback=10),
            "ssl_required": cfg.getboolean("database", "ssl_required", fallback=False),
            "max_connections": cfg.getint("performance", "max_connections", fallback=50),
            "latency_threshold_warning_ms": cfg.getint("performance", "latency_threshold_warning_ms", fallback=100),
            "latency_threshold_critical_ms": cfg.getint("performance", "latency_threshold_critical_ms", fallback=300),
            "session_timeout_minutes": cfg.getint("auth", "session_timeout_minutes", fallback=60),
            "log_file": cfg.get("logging", "log_file", fallback=f"docs/{code}_app.log")
        }
    return specs


def validate_all_environments() -> Dict[str, Any]:
    """
    Melakukan validasi integritas terhadap seluruh file konfigurasi.
    Memastikan parameter wajib (host, dbname, port, log_level) ada dan valid.
    """
    results = {}
    required_sections = ["environment", "database", "auth", "logging", "performance"]
    required_db_keys = ["host", "port", "dbname", "log_level"]

    for code in VALID_ENVIRONMENTS:
        file_path = os.path.join(CONFIG_DIR, f"{code}.ini")
        status = {"file_exists": os.path.exists(file_path), "valid": True, "errors": []}

        if not status["file_exists"]:
            status["valid"] = False
            status["errors"].append(f"File {code}.ini tidak ditemukan pada {CONFIG_DIR}")
            results[code] = status
            continue

        try:
            cfg = configparser.ConfigParser()
            cfg.read(file_path, encoding="utf-8")

            for sec in required_sections:
                if not cfg.has_section(sec):
                    status["valid"] = False
                    status["errors"].append(f"Section '[{sec}]' hilang dari {code}.ini")

            if cfg.has_section("database"):
                for k in required_db_keys:
                    if not cfg.has_option("database", k):
                        status["valid"] = False
                        status["errors"].append(f"Key '{k}' hilang dari section [database] di {code}.ini")

            status["dbname"] = cfg.get("database", "dbname", fallback="N/A")
            status["log_level"] = cfg.get("database", "log_level", fallback="N/A")
        except Exception as e:
            status["valid"] = False
            status["errors"].append(f"Gagal parse {code}.ini: {e}")

        results[code] = status

    return results
