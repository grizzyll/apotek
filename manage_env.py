#!/usr/bin/env python
"""
CLI Tool: Pengelola Konfigurasi Multi-Environment (Action 10: J.620100.042.01)
PT Sehat Bersama Farma - Sistem Basis Data Apotek Multi-Cabang

Penggunaan:
    python manage_env.py status
    python manage_env.py set <dev|staging|prod>
    python manage_env.py validate
    python manage_env.py test-conn [username] [password]
"""

import sys
import os
from src.env_config import (
    get_active_env,
    set_active_env,
    get_environment_specification,
    validate_all_environments,
    VALID_ENVIRONMENTS
)
from src.koneksi import get_connection

def print_header(title):
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)

def cmd_status():
    active = get_active_env()
    specs = get_environment_specification()

    print_header("STATUS KONFIGURASI MULTI-ENVIRONMENT (ACTION 10)")
    print(f"  Environment Aktif Saat Ini : [{active.upper()}] — {specs[active]['title']}")
    print(f"  Target Basis Data         : {specs[active]['dbname']} @ {specs[active]['host']}:{specs[active]['port']}")
    print(f"  Level Logging             : {specs[active]['log_level']}")
    print(f"  Mode Produksi             : {'Ya (Live)' if specs[active]['is_production'] else 'Tidak (Uji / Debug)'}")
    print("-" * 70)

    print("\n📋 MATRIKS SPESIFIKASI KETIGA ENVIRONMENT:")
    print(f"{'Environment':<12} | {'Basis Data':<16} | {'Host:Port':<16} | {'Log Level':<10} | {'Status':<10}")
    print("-" * 70)
    for code, s in specs.items():
        is_curr = " (AKTIF)" if code == active else ""
        print(f"{code.upper() + is_curr:<12} | {s['dbname']:<16} | {s['host']}:{s['port']:<11} | {s['log_level']:<10} | {s['badge']}")
    print("=" * 70 + "\n")

def cmd_set(target):
    target = target.lower().strip()
    if target not in VALID_ENVIRONMENTS:
        print(f"❌ Error: Environment '{target}' tidak dikenal.")
        print(f"   Pilihan yang valid: {', '.join(VALID_ENVIRONMENTS)}")
        sys.exit(1)

    set_active_env(target)
    specs = get_environment_specification()
    print_header("AKTIVASI ENVIRONMENT BERHASIL (SINGLE ACTIVE ENVIRONMENT)")
    print(f"  ✅ Environment berhasil dialihkan ke: [{target.upper()}]")
    print(f"  📌 Target Basis Data : {specs[target]['dbname']}")
    print(f"  📝 Level Logging     : {specs[target]['log_level']}")
    print(f"  🔒 Mode Produksi     : {specs[target]['is_production']}")
    print("=" * 70 + "\n")

def cmd_validate():
    val_results = validate_all_environments()
    print_header("VALIDASI FILE KONFIGURASI ENVIRONMENT (config/*.ini)")

    all_ok = True
    for env_code, res in val_results.items():
        icon = "✅" if res["valid"] else "❌"
        status_text = "Lengkap & Valid" if res["valid"] else "Bermasalah"
        print(f"  {icon} config/{env_code}.ini : {status_text}")
        if res.get("dbname"):
            print(f"     - Target Database: {res['dbname']}")
            print(f"     - Log Level      : {res['log_level']}")
        if res["errors"]:
            all_ok = False
            for err in res["errors"]:
                print(f"     ⚠️ {err}")
        print()

    print("-" * 70)
    if all_ok:
        print("  🎉 Seluruh file konfigurasi environment terverifikasi BEST PRACTICE!")
    else:
        print("  ⚠️ Ditemukan kesalahan pada file konfigurasi.")
    print("=" * 70 + "\n")

def cmd_test_conn(user=None, pwd=None):
    active = get_active_env()
    specs = get_environment_specification()
    active_spec = specs[active]

    u = user if user else os.getenv("DEFAULT_USER", "admin.pusat")
    p = pwd if pwd else os.getenv("PASSWORD_ADMIN_PUSAT", "AdminPst#2026")

    print_header(f"UJI KONEKSI KE ENVIRONMENT AKTIF: [{active.upper()}]")
    print(f"  Target DB : {active_spec['dbname']} @ {active_spec['host']}:{active_spec['port']}")
    print(f"  Akun DB   : {u}@localhost")

    try:
        conn = get_connection(u, p, env=active)
        with conn.cursor() as cur:
            cur.execute("SELECT DATABASE() AS db, USER() AS usr, VERSION() AS ver")
            info = cur.fetchone()
        conn.close()
        print("\n  ✅ [BERHASIL] Terhubung ke basis data!")
        print(f"     - Database Terhubung : {info['db']}")
        print(f"     - User Authenticated : {info['usr']}")
        print(f"     - Server MariaDB     : {info['ver']}")
    except Exception as e:
        print(f"\n  ❌ [GAGAL] Tidak dapat terhubung ke basis data:\n     {e}")
    print("=" * 70 + "\n")

def main():
    if len(sys.argv) < 2:
        cmd_status()
        print("Petunjuk Penggunaan:")
        print("  python manage_env.py status          -> Lihat status environment aktif")
        print("  python manage_env.py set <env>       -> Ganti environment (dev | staging | prod)")
        print("  python manage_env.py validate        -> Validasi sintaks seluruh file config/*.ini")
        print("  python manage_env.py test-conn [u] [p] -> Uji koneksi basis data environment aktif")
        return

    action = sys.argv[1].lower().strip()
    if action == "status":
        cmd_status()
    elif action == "set":
        if len(sys.argv) < 3:
            print("❌ Parameter kurang. Contoh: python manage_env.py set staging")
            sys.exit(1)
        cmd_set(sys.argv[2])
    elif action == "validate":
        cmd_validate()
    elif action in ("test", "test-conn"):
        u = sys.argv[2] if len(sys.argv) > 2 else None
        p = sys.argv[3] if len(sys.argv) > 3 else None
        cmd_test_conn(u, p)
    else:
        print(f"Perintah tidak dikenal: {action}")
        print("Gunakan salah satu dari: status, set, validate, test-conn")

if __name__ == "__main__":
    main()
