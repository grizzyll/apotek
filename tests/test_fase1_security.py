import pytest
import pymysql
import os
from src.koneksi import get_connection

def test_kasir_select_stok_denied():
    """Kasir dilarang SELECT langsung ke tabel stok (Error 1142)"""
    conn = get_connection("kasir.depok", "KasirDpk#2026", env="dev")
    try:
        with conn.cursor() as cur:
            with pytest.raises(pymysql.err.OperationalError) as exc_info:
                cur.execute("SELECT * FROM stok")
            # Kode error 1142: SELECT command denied to user
            assert exc_info.value.args[0] == 1142
            assert "SELECT command denied" in str(exc_info.value)
    finally:
        conn.close()

def test_kasir_update_obat_denied():
    """Kasir dilarang UPDATE ke tabel obat (Error 1142)"""
    conn = get_connection("kasir.depok", "KasirDpk#2026", env="dev")
    try:
        with conn.cursor() as cur:
            with pytest.raises(pymysql.err.OperationalError) as exc_info:
                cur.execute("UPDATE obat SET harga_jual = 999999 WHERE kode_obat = 'OBT-001'")
            # Kode error 1142: UPDATE command denied to user
            assert exc_info.value.args[0] == 1142
            assert "UPDATE command denied" in str(exc_info.value)
    finally:
        conn.close()

def test_kasir_select_v_stok_cabang_isolated():
    """Kasir Depok hanya boleh melihat stok cabangnya sendiri (CBG-01) via view v_stok_cabang"""
    conn = get_connection("kasir.depok", "KasirDpk#2026", env="dev")
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT DISTINCT kode_cabang FROM v_stok_cabang")
            cabang_list = [row["kode_cabang"] for row in cur.fetchall()]
            assert cabang_list == ["CBG-01"], f"Ekspektasi hanya CBG-01, didapat: {cabang_list}"
    finally:
        conn.close()

def test_kasir_select_profil_saya():
    """Kasir membaca profilnya sendiri via view v_profil_saya tanpa akses root"""
    conn = get_connection("kasir.depok", "KasirDpk#2026", env="dev")
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT username, peran, kode_cabang FROM v_profil_saya")
            profil = cur.fetchone()
            assert profil is not None
            assert profil["username"] == "kasir.depok"
            assert profil["peran"] == "KASIR"
            assert profil["kode_cabang"] == "CBG-01"
    finally:
        conn.close()

def test_kasir_select_pengguna_denied():
    """Kasir dilarang SELECT langsung ke tabel pengguna (Error 1142)"""
    conn = get_connection("kasir.depok", "KasirDpk#2026", env="dev")
    try:
        with conn.cursor() as cur:
            with pytest.raises(pymysql.err.OperationalError) as exc_info:
                cur.execute("SELECT * FROM pengguna")
            assert exc_info.value.args[0] == 1142
    finally:
        conn.close()
