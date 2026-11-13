import streamlit as st
import pandas as pd
import time
import os
import html
from datetime import datetime
import pymysql
import importlib

# Reload modul internal agar Streamlit selalu menggunakan versi kode terbaru
import src.admin_dao
import src.obat_dao
import src.penjualan
importlib.reload(src.admin_dao)
importlib.reload(src.obat_dao)
importlib.reload(src.penjualan)

from src.koneksi import get_connection, get_config
from src.env_config import get_active_env, set_active_env, VALID_ENVIRONMENTS
from src.obat_dao import ObatDAO, cari_obat_linear, cari_obat_binary, quick_sort_obat
from src.admin_dao import AdminDAO
from src.penjualan import PenjualanService
from ui.styles import CUSTOM_CSS
from ui.format import format_rupiah, format_tanggal
from ui.components import render_header, render_kpi, get_badge_kategori

# ========================================================
# PENGATURAN HALAMAN
# ========================================================
st.set_page_config(
    page_title="Sistem Apotek Multi-Cabang | PT Sehat Bersama Farma",
    page_icon="💊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Terapkan Custom CSS Sistem Desain
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

# ========================================================
# HELPER BACKEND ROBUST (Anti-Cache / Anti-AttributeError)
# ========================================================
def get_auto_kode_cabang(dao_obj, conn_obj):
    if hasattr(dao_obj, "generate_kode_cabang"):
        try:
            return dao_obj.generate_kode_cabang()
        except Exception:
            pass
    try:
        with conn_obj.cursor() as cur:
            cur.execute("SELECT kode_cabang FROM cabang ORDER BY kode_cabang DESC LIMIT 1")
            row = cur.fetchone()
        if row:
            parts = row["kode_cabang"].split("-")
            return f"CBG-{int(parts[1]) + 1:02d}"
    except Exception:
        pass
    return "CBG-01"

def get_auto_kode_obat(dao_obj, conn_obj):
    if hasattr(dao_obj, "generate_kode_obat"):
        try:
            return dao_obj.generate_kode_obat()
        except Exception:
            pass
    try:
        with conn_obj.cursor() as cur:
            cur.execute("SELECT kode_obat FROM obat ORDER BY kode_obat DESC LIMIT 1")
            row = cur.fetchone()
        if row:
            parts = row["kode_obat"].split("-")
            return f"OBT-{int(parts[1]) + 1:03d}"
    except Exception:
        pass
    return "OBT-001"

def cek_nama_cabang_unik_safe(dao_obj, conn_obj, nama, exclude_kode=None):
    if hasattr(dao_obj, "cek_nama_cabang_unik"):
        try:
            return dao_obj.cek_nama_cabang_unik(nama, exclude_kode)
        except Exception:
            pass
    try:
        if exclude_kode:
            sql = "SELECT COUNT(*) as cnt FROM cabang WHERE LOWER(TRIM(nama_cabang)) = LOWER(TRIM(%s)) AND kode_cabang != %s"
            params = (nama, exclude_kode)
        else:
            sql = "SELECT COUNT(*) as cnt FROM cabang WHERE LOWER(TRIM(nama_cabang)) = LOWER(TRIM(%s))"
            params = (nama,)
        with conn_obj.cursor() as cur:
            cur.execute(sql, params)
            row = cur.fetchone()
        return row["cnt"] > 0
    except Exception:
        return False

def cek_relasi_cabang_safe(dao_obj, conn_obj, kode_cabang):
    if hasattr(dao_obj, "cek_relasi_cabang"):
        try:
            return dao_obj.cek_relasi_cabang(kode_cabang)
        except Exception:
            pass
    try:
        with conn_obj.cursor() as cur:
            cur.execute("SELECT COUNT(*) as cnt FROM stok WHERE kode_cabang = %s", (kode_cabang,))
            s = cur.fetchone()["cnt"]
            cur.execute("SELECT COUNT(*) as cnt FROM penjualan WHERE kode_cabang = %s", (kode_cabang,))
            p = cur.fetchone()["cnt"]
            cur.execute("SELECT COUNT(*) as cnt FROM pengguna WHERE kode_cabang = %s", (kode_cabang,))
            u = cur.fetchone()["cnt"]
        return s, p, u
    except Exception:
        return 0, 0, 0

def cek_relasi_obat_safe(dao_obj, conn_obj, kode_obat):
    if hasattr(dao_obj, "cek_relasi_obat"):
        try:
            return dao_obj.cek_relasi_obat(kode_obat)
        except Exception:
            pass
    try:
        with conn_obj.cursor() as cur:
            cur.execute("SELECT COUNT(*) as cnt FROM stok WHERE kode_obat = %s", (kode_obat,))
            s = cur.fetchone()["cnt"]
            cur.execute("SELECT COUNT(*) as cnt FROM detail_penjualan WHERE kode_obat = %s", (kode_obat,))
            d = cur.fetchone()["cnt"]
        return s, d
    except Exception:
        return 0, 0

def cek_relasi_pengguna_safe(dao_obj, conn_obj, id_pengguna):
    if hasattr(dao_obj, "cek_relasi_pengguna"):
        try:
            return dao_obj.cek_relasi_pengguna(id_pengguna)
        except Exception:
            pass
    try:
        with conn_obj.cursor() as cur:
            cur.execute("SELECT COUNT(*) as cnt FROM penjualan WHERE id_pengguna = %s", (id_pengguna,))
            return cur.fetchone()["cnt"]
    except Exception:
        return 0

# ========================================================
# SESSION STATE
# ========================================================
if "auth" not in st.session_state:
    st.session_state.auth = None
if "cart" not in st.session_state:
    st.session_state.cart = []
if "curr_faktur" not in st.session_state:
    st.session_state.curr_faktur = f"FKT-{datetime.now().strftime('%Y%m%d%H%M%S')}"
if "alert_crud" not in st.session_state:
    st.session_state.alert_crud = None
if "alert_cabang" not in st.session_state:
    st.session_state.alert_cabang = None
if "alert_user" not in st.session_state:
    st.session_state.alert_user = None
if "transaksi_sukses" not in st.session_state:
    st.session_state.transaksi_sukses = None

# ========================================================
# HALAMAN LOGIN (jika belum masuk)
# ========================================================
if not st.session_state.auth:
    _, col_tengah, _ = st.columns([1, 1.8, 1])
    with col_tengah:
        st.write("")
        st.markdown("""
        <div class="login-wrapper">
            <div class="login-icon">💊</div>
            <div style="text-align:center; margin-bottom: 20px;">
                <h3 style="margin:0 0 6px 0; color:#0F766E; font-weight:700;">PT Sehat Bersama Farma</h3>
                <p style="margin:0; color:#64748B; font-size:14px;">Sistem Basis Data Inventori &amp; Penjualan Apotek Multi-Cabang</p>
            </div>
        """, unsafe_allow_html=True)

        st.markdown("##### 🌐 Pilih Target Environment:")
        curr_env_btn = st.session_state.get("selected_login_env", get_active_env())
        be1, be2, be3 = st.columns(3)
        with be1:
            if st.button("🛠️ DEV", use_container_width=True, type="primary" if curr_env_btn == "dev" else "secondary", key="btn_login_dev"):
                set_active_env("dev")
                st.session_state.selected_login_env = "dev"
                st.rerun()
        with be2:
            if st.button("🧪 STAGING", use_container_width=True, type="primary" if curr_env_btn == "staging" else "secondary", key="btn_login_staging"):
                set_active_env("staging")
                st.session_state.selected_login_env = "staging"
                st.rerun()
        with be3:
            if st.button("🚀 PROD", use_container_width=True, type="primary" if curr_env_btn == "prod" else "secondary", key="btn_login_prod"):
                set_active_env("prod")
                st.session_state.selected_login_env = "prod"
                st.rerun()

        cfg_now = get_config(curr_env_btn)
        st.caption(f"📌 Mode Aktif: **{curr_env_btn.upper()}** | Basis Data: `{cfg_now.get('dbname', 'apotek')}` | Log: `{cfg_now.get('log_level', 'INFO')}`")

        with st.form("form_login"):
            st.markdown("##### 🔐 Masuk ke Sistem")
            st.caption("Autentikasi langsung ke MariaDB menggunakan akun peran Anda (*Least Privilege*).")
            input_user = st.text_input("Username:", placeholder="Contoh: kasir.depok / apoteker.depok / admin.pusat")
            input_pwd = st.text_input("Password:", type="password", placeholder="Masukkan kata sandi")
            input_env = curr_env_btn
            
            if st.form_submit_button("Masuk ke Sistem", use_container_width=True, type="primary"):
                if not input_user.strip() or not input_pwd.strip():
                    st.error("Username dan password wajib diisi!")
                else:
                    try:
                        conn_user = get_connection(input_user.strip(), input_pwd.strip(), env=input_env)
                        with conn_user.cursor() as cur:
                            cur.execute(
                                "SELECT id_pengguna, username, nama_lengkap, peran, kode_cabang FROM v_profil_saya"
                            )
                            ud = cur.fetchone()
                        
                        if not ud:
                            conn_user.close()
                            st.error("Profil tidak ditemukan di v_profil_saya. Pastikan akun terdaftar di sistem.")
                        else:
                            st.session_state.db_conn = conn_user
                            st.session_state.auth = {
                                "user": ud["username"],
                                "id_pengguna": ud["id_pengguna"],
                                "nama_lengkap": ud["nama_lengkap"],
                                "peran": ud["peran"],
                                "cabang": ud["kode_cabang"] if ud["kode_cabang"] else "ALL",
                                "env": input_env
                            }
                            st.session_state.cart = []
                            st.session_state.curr_faktur = f"FKT-{datetime.now().strftime('%Y%m%d%H%M%S')}"
                            st.session_state.transaksi_sukses = None
                            st.rerun()
                    except Exception as e:
                        st.error(f"❌ Login Gagal — Akses ditolak database:\n\n`{e}`")

        st.markdown("</div>", unsafe_allow_html=True)

        # Tampilkan akun demo hanya jika environment DEV dan DEMO_MODE aktif
        demo_mode_active = os.getenv("DEMO_MODE", "true").lower() == "true"
        if input_env == "dev" and demo_mode_active:
            with st.expander("ℹ️ Daftar Akun Demo untuk Pengujian (Hanya Tampil di Mode DEV)"):
                st.caption("Akun demo di bawah disediakan khusus untuk pengujian pada environment development.")
                st.markdown("""
| Peran | Username | Password Demo | Cabang | Hak Akses Utama |
|---|---|---|---|---|
| **Kasir Depok** | `kasir.depok` | `KasirDpk#2026` | CBG-01 | Transaksi penjualan, Pantau stok Depok |
| **Apoteker Depok** | `apoteker.depok` | `ApotDpk#2026` | CBG-01 | Jual semua obat termasuk Obat Keras, Pantau stok Depok |
| **Kasir Bekasi** | `kasir.bekasi` | `KasirBks#2026` | CBG-02 | Transaksi penjualan, Pantau stok Bekasi |
| **Admin Pusat** | `admin.pusat` | `AdminPst#2026` | SEMUA | **Pantau & CRUD Cabang, CRUD Obat, CRUD Pengguna** |
                """)
    st.stop()

# ========================================================
# HELPER KONEKSI
# ========================================================
def conn_aktif():
    conn = st.session_state.get("db_conn")
    if conn is None:
        st.error("Koneksi basis data tidak ditemukan. Silakan login kembali.")
        st.stop()
    try:
        conn.ping(reconnect=True)
    except Exception as e:
        st.error(f"Koneksi database terputus dan gagal reconnect: {e}")
        st.stop()
    return conn

PERAN = st.session_state.auth["peran"]
IS_ADMIN = (PERAN == "ADMIN_PUSAT")

LABEL = {
    "KASIR":       {"icon": "🧾", "sebutan": "Kasir"},
    "APOTEKER":    {"icon": "💊", "sebutan": "Apoteker"},
    "ADMIN_PUSAT": {"icon": "🏢", "sebutan": "Admin Pusat"},
}.get(PERAN, {"icon": "👤", "sebutan": PERAN})

# ========================================================
# SIDEBAR
# ========================================================
with st.sidebar:
    st.markdown("### 💊 PT Sehat Bersama Farma")
    st.caption("Sistem Basis Data Apotek Multi-Cabang")
    st.markdown("---")
    st.markdown("##### 👤 Profil Aktif")
    st.success(f"{LABEL['icon']} **{st.session_state.auth['nama_lengkap']}**")
    st.markdown(f"""
- **Peran:** `{PERAN}`
- **Cabang:** `{st.session_state.auth['cabang']}`
- **Akun DB:** `{st.session_state.auth['user']}@localhost`
- **Mode:** `{st.session_state.auth['env'].upper()}`
    """)

    st.markdown("---")
    st.markdown("##### 🌐 Ganti Environment (Action 10)")
    st.caption("Beralih target database secara instan:")
    curr_sess_env = st.session_state.auth.get("env", "dev")

    sb_c1, sb_c2, sb_c3 = st.columns(3)
    with sb_c1:
        if st.button("🛠️ DEV", use_container_width=True, type="primary" if curr_sess_env == "dev" else "secondary", key="sb_btn_dev"):
            set_active_env("dev")
            st.session_state.auth["env"] = "dev"
            st.rerun()
    with sb_c2:
        if st.button("🧪 STG", use_container_width=True, type="primary" if curr_sess_env == "staging" else "secondary", key="sb_btn_stg"):
            set_active_env("staging")
            st.session_state.auth["env"] = "staging"
            st.rerun()
    with sb_c3:
        if st.button("🚀 PROD", use_container_width=True, type="primary" if curr_sess_env == "prod" else "secondary", key="sb_btn_prd"):
            set_active_env("prod")
            st.session_state.auth["env"] = "prod"
            st.rerun()

    cfg_cur = get_config(curr_sess_env)
    st.caption(f"📁 Target DB: `{cfg_cur.get('dbname', 'apotek')}` | Log: `{cfg_cur.get('log_level', 'INFO')}`")

    st.markdown("---")
    if st.button("🚪 Keluar (Logout)", use_container_width=True):
        if "db_conn" in st.session_state and st.session_state.db_conn:
            try:
                st.session_state.db_conn.close()
            except Exception:
                pass
            st.session_state.db_conn = None
        st.session_state.auth = None
        st.session_state.cart = []
        st.session_state.transaksi_sukses = None
        st.rerun()
    st.markdown("---")
    st.caption("Koneksi langsung ke MariaDB dengan prinsip *Least Privilege*.")

# ========================================================
# HEADER UTAMA
# ========================================================
render_header(
    st.session_state.auth['nama_lengkap'],
    st.session_state.auth['peran'],
    st.session_state.auth['cabang'],
    LABEL['icon'],
    LABEL['sebutan'],
    st.session_state.auth.get('env', 'dev')
)

# ========================================================
# MAPPING SORT (fix bug: exact match agar tidak tertukar)
# ========================================================
SORT_MAP = {
    "Harga Jual: Termurah → Termahal":                ("harga_jual",   True),
    "Harga Jual: Termahal → Termurah":                ("harga_jual",   False),
    "Stok Minimum: Terkecil → Terbesar":              ("stok_minimum", True),
    "Obat Terlaris: Total Terjual Terbanyak → Terkecil": ("total_terjual", False),
}

# ========================================================
# ============================================================
# ADMIN PUSAT — 4 TAB
# (1. Pantau Cabang | 2. Manajemen Cabang | 3. Master Obat | 4. Manajemen Pengguna)
# ============================================================
# ========================================================
if IS_ADMIN:

    tab1, tab2, tab3, tab4 = st.tabs([
        "📈 1. Pantau Cabang",
        "🏪 2. Manajemen Cabang",
        "📦 3. Master Obat",
        "👥 4. Manajemen Pengguna",
    ])

    # ----------------------------------------------------------
    # ADMIN TAB 1 — MONITORING SELURUH CABANG
    # ----------------------------------------------------------
    with tab1:
        st.markdown("#### 📈 Monitoring Kinerja Seluruh Cabang")
        st.caption("Ringkasan omset penjualan, total transaksi, stok, dan stok kritis per cabang.")

        conn = conn_aktif()
        admin_dao = AdminDAO(conn)
        ringkasan_cbg = admin_dao.ringkasan_pantau_cabang()

        if ringkasan_cbg:
            df_ringkasan = pd.DataFrame(ringkasan_cbg)
            total_omset_semua  = df_ringkasan["total_omset"].sum()
            total_trx_semua    = df_ringkasan["total_transaksi"].sum()
            total_stok_semua   = df_ringkasan["total_stok"].sum()
            total_kritis_semua = df_ringkasan["stok_kritis"].sum()

            m1, m2, m3, m4 = st.columns(4)
            render_kpi(m1, "Total Cabang",         f"{len(df_ringkasan)} Cabang",      "Jabodetabek")
            render_kpi(m2, "Total Omset Gabungan", format_rupiah(total_omset_semua),   "Seluruh Cabang")
            render_kpi(m3, "Total Transaksi",      f"{int(total_trx_semua)} Faktur",   "Tercatat di Basis Data")
            render_kpi(m4, "Item Stok Kritis",     f"{int(total_kritis_semua)} Obat",  "Di Bawah Batas Minimum")

            st.markdown("**Rincian Kinerja per Cabang:**")
            st.dataframe(df_ringkasan[[
                "kode_cabang", "nama_cabang", "telepon",
                "total_transaksi", "total_omset", "total_stok", "stok_kritis"
            ]], use_container_width=True, hide_index=True)
        else:
            st.info("Belum ada data cabang.")

    # ----------------------------------------------------------
    # ADMIN TAB 2 — CRUD CABANG
    # ----------------------------------------------------------
    with tab2:
        st.markdown("#### 🏪 Manajemen Master Cabang")
        st.caption("CRUD data cabang: tambah, ubah, dan hapus cabang apotek. Kode cabang otomatis.")

        conn = conn_aktif()
        admin_dao = AdminDAO(conn)

        if st.session_state.alert_cabang:
            tipe_a, pesan_a = st.session_state.alert_cabang
            (st.success if tipe_a == "ok" else st.error)(pesan_a)
            st.session_state.alert_cabang = None

        daftar_cbg = admin_dao.ambil_semua_cabang()
        st.markdown(f"**Daftar Master Cabang ({len(daftar_cbg)} Cabang):**")
        if daftar_cbg:
            st.dataframe(pd.DataFrame(daftar_cbg)[["kode_cabang", "nama_cabang", "alamat", "telepon"]],
                         use_container_width=True, hide_index=True)

        st.markdown("---")
        cbg_col1, cbg_col2, cbg_col3 = st.columns(3, gap="medium")

        # ---- CREATE ----
        with cbg_col1:
            st.markdown("**➕ Tambah Cabang Baru:**")
            kode_cbg_otomatis = get_auto_kode_cabang(admin_dao, conn)
            with st.form("form_tambah_cbg"):
                st.text_input("Kode Cabang (Otomatis):", value=kode_cbg_otomatis, disabled=True,
                              help="Kode cabang di-generate otomatis berurutan dari database.")
                cbg_nama   = st.text_input("Nama Cabang:", placeholder="Contoh: Apotek Sehat Tangerang")
                cbg_alamat = st.text_input("Alamat:",     placeholder="Alamat lengkap cabang")
                cbg_telp   = st.text_input("Telepon:",    placeholder="021-xxxxxxx")
                if st.form_submit_button("➕ Tambah Cabang", use_container_width=True):
                    if not cbg_nama.strip():
                        st.error("Nama cabang wajib diisi!")
                    elif cek_nama_cabang_unik_safe(admin_dao, conn, cbg_nama.strip()):
                        st.error(f"⚠️ Nama cabang **\"{cbg_nama.strip()}\"** sudah digunakan. Pilih nama yang berbeda.")
                    else:
                        try:
                            admin_dao.tambah_cabang(kode_cbg_otomatis, cbg_nama.strip(), cbg_alamat.strip(), cbg_telp.strip())
                            st.session_state.alert_cabang = ("ok", f"✅ Cabang **{cbg_nama.strip()}** ({kode_cbg_otomatis}) berhasil ditambahkan!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Gagal tambah cabang: {e}")

        # ---- UPDATE ----
        with cbg_col2:
            st.markdown("**✏️ Ubah Info Cabang:**")
            if daftar_cbg:
                cbg_pilih = st.selectbox(
                    "Pilih Cabang:",
                    [c["kode_cabang"] for c in daftar_cbg],
                    format_func=lambda k: f"{k} — {next((c['nama_cabang'] for c in daftar_cbg if c['kode_cabang']==k), k)}",
                    key="sb_edit_cbg"
                )
                info_cbg = next((c for c in daftar_cbg if c["kode_cabang"] == cbg_pilih), {})
                with st.form("form_edit_cbg"):
                    edit_nama   = st.text_input("Nama Cabang:", value=info_cbg.get("nama_cabang", ""))
                    edit_alamat = st.text_input("Alamat:",      value=info_cbg.get("alamat", ""))
                    edit_telp   = st.text_input("Telepon:",     value=info_cbg.get("telepon", ""))
                    if st.form_submit_button("💾 Simpan Perubahan", use_container_width=True):
                        if not edit_nama.strip():
                            st.error("Nama cabang wajib diisi!")
                        elif cek_nama_cabang_unik_safe(admin_dao, conn, edit_nama.strip(), exclude_kode=cbg_pilih):
                            st.error(f"⚠️ Nama cabang **\"{edit_nama.strip()}\"** sudah digunakan oleh cabang lain.")
                        else:
                            try:
                                admin_dao.update_cabang(cbg_pilih, edit_nama.strip(), edit_alamat.strip(), edit_telp.strip())
                                st.session_state.alert_cabang = ("ok", f"✅ Cabang {cbg_pilih} berhasil diperbarui!")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Gagal ubah cabang: {e}")

        # ---- DELETE ----
        with cbg_col3:
            st.markdown("**🗑️ Drop Cabang:**")
            if daftar_cbg:
                del_cbg_kode = st.selectbox(
                    "Pilih Cabang:",
                    [c["kode_cabang"] for c in daftar_cbg],
                    format_func=lambda k: f"{k} — {next((c['nama_cabang'] for c in daftar_cbg if c['kode_cabang']==k), k)}",
                    key="sb_del_cbg"
                )
                with st.form("form_del_cbg"):
                    st.caption(f"Konfirmasi drop cabang **{del_cbg_kode}**. Pegawai di cabang ini otomatis dialihkan statusnya menjadi Nonaktif (Tanpa Cabang), dan riwayat transaksi masa lalu tetap tersimpan aman di database utama.")
                    if st.form_submit_button("🗑️ Drop Cabang", use_container_width=True, type="secondary"):
                        try:
                            admin_dao.hapus_cabang(del_cbg_kode)
                            st.session_state.alert_cabang = ("ok", f"🎉 Cabang **{del_cbg_kode}** berhasil di-drop! Staf cabang otomatis dialihkan menjadi Nonaktif, dan riwayat transaksi masa lalu tetap tersimpan di basis data.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Gagal drop cabang: {e}")

    # ----------------------------------------------------------
    # ADMIN TAB 3 — MASTER OBAT (CRUD + Searching/Sorting)
    # ----------------------------------------------------------
    with tab3:
        st.markdown("#### 📦 Master Obat — CRUD & Pencarian/Pengurutan")
        st.caption(
            f"Akun aktif: `{st.session_state.auth['user']}` (Peran: `{PERAN}`). "
            f"Hak INSERT, UPDATE, DELETE obat hanya dimiliki oleh **Admin Pusat**."
        )

        conn = conn_aktif()
        admin_dao = AdminDAO(conn)
        dao = ObatDAO(conn)
        daftar_obat = dao.ambil_semua()

        if st.session_state.alert_crud:
            tipe_a, pesan_a = st.session_state.alert_crud
            (st.success if tipe_a == "ok" else st.error)(pesan_a)
            st.session_state.alert_crud = None

        # ---- SEARCHING & SORTING ----
        st.markdown("##### 🔍 Pencarian & 🔀 Pengurutan Obat")
        algo_kiri, algo_kanan = st.columns([1, 1])
        with algo_kiri:
            tipe_cari = st.radio("Metode Pencarian:", ["Linear Search — O(N)", "Binary Search — O(log N)"], horizontal=True)
            keyword   = st.text_input("Kata Kunci:", placeholder="Ketik nama atau kode obat...")
            if "Binary" in tipe_cari:
                st.caption("💡 Binary Search mencari berdasarkan **kode obat tepat** (mis. OBT-001).")
        with algo_kanan:
            sort_key = st.selectbox("Urutkan Berdasarkan:", [
                "— Tanpa Urutan —",
                "Harga Jual: Termurah → Termahal",
                "Harga Jual: Termahal → Termurah",
                "Stok Minimum: Terkecil → Terbesar",
                "Obat Terlaris: Total Terjual Terbanyak → Terkecil",
            ])

        is_terlaris = (sort_key == "Obat Terlaris: Total Terjual Terbanyak → Terkecil")
        data_sumber = dao.ambil_laporan_obat_terlaris() if is_terlaris else daftar_obat

        if keyword.strip():
            if "Linear" in tipe_cari:
                hasil = cari_obat_linear(data_sumber, keyword)
                st.caption(f"🔍 Linear Search: memeriksa {len(data_sumber)} data → ditemukan **{len(hasil)} hasil**.")
            else:
                terurut = sorted(data_sumber, key=lambda x: x["kode_obat"])
                item    = cari_obat_binary(terurut, keyword.strip())
                hasil   = [item] if item else []
                st.caption(
                    f"🔍 Binary Search: "
                    f"{'✅ ditemukan 1 data.' if hasil else '❌ tidak ditemukan — masukkan kode obat tepat (OBT-XXX).'}"
                )
        else:
            hasil = list(data_sumber)

        if sort_key in SORT_MAP and hasil:
            sort_field, sort_asc = SORT_MAP[sort_key]
            if sort_field in hasil[0]:
                hasil = quick_sort_obat(hasil, key=sort_field, ascending=sort_asc)

        st.markdown(f"**Daftar Obat ({len(hasil)} data):**")
        if hasil:
            if is_terlaris:
                cols_show = ["kode_obat","nama_obat","nama_kategori","harga_jual","total_terjual","total_pendapatan"]
            else:
                cols_show = ["kode_obat","nama_obat","nama_kategori","satuan","harga_jual","stok_minimum"]
            cols_show = [c for c in cols_show if c in hasil[0]]
            st.dataframe(pd.DataFrame(hasil)[cols_show], use_container_width=True, hide_index=True)
        else:
            st.info("Tidak ada data obat yang sesuai pencarian/filter.")

        # ---- CRUD OBAT ----
        st.markdown("---")
        st.markdown("##### 🛠️ Operasi CRUD Master Obat")

        cr1, cr2, cr3 = st.columns(3, gap="medium")

        # ---- CREATE ----
        with cr1:
            st.markdown("**1. INSERT (Tambah Obat Baru):**")
            kode_obat_otomatis = get_auto_kode_obat(admin_dao, conn)
            daftar_kategori    = dao.ambil_kategori()
            kat_dict = {
                f"{k['kode_kategori']} — {k['nama_kategori']}": k['kode_kategori']
                for k in daftar_kategori
            }
            with st.form("form_insert_obat"):
                st.text_input("Kode Obat (Otomatis):", value=kode_obat_otomatis, disabled=True,
                              help="Kode obat di-generate otomatis berurutan dari database.")
                in_nama      = st.text_input("Nama Obat:",    placeholder="Contoh: Amoxicillin 250mg")
                in_kat_label = st.selectbox("Kategori:",      list(kat_dict.keys()))
                in_kat       = kat_dict[in_kat_label]
                in_satuan    = st.text_input("Satuan:",        placeholder="Strip / Botol / Pcs")
                in_harga     = st.number_input("Harga Jual (Rp):", value=10000, min_value=0, step=500)
                in_min       = st.number_input("Stok Minimum:", value=10, min_value=0)
                if st.form_submit_button("➕ Tambah Obat", use_container_width=True):
                    if not in_nama.strip():
                        st.error("Nama obat wajib diisi!")
                    else:
                        try:
                            dao.tambah_obat(kode_obat_otomatis, in_nama.strip(), in_kat, in_satuan.strip(), in_harga, in_min)
                            st.session_state.alert_crud = ("ok", f"🎉 Obat **{in_nama.strip()}** ({kode_obat_otomatis}) berhasil ditambahkan!")
                        except Exception as e:
                            st.session_state.alert_crud = ("err", f"⛔ Gagal tambah obat:\n`{e}`")
                        st.rerun()

        # ---- UPDATE ----
        with cr2:
            st.markdown("**2. UPDATE (Ubah Harga Obat):**")
            if daftar_obat:
                kode_ubah = st.selectbox(
                    "Pilih Obat:",
                    [o["kode_obat"] for o in daftar_obat],
                    format_func=lambda k: f"{k} — {next((o['nama_obat'] for o in daftar_obat if o['kode_obat']==k), k)}",
                    key="sb_upd_obat"
                )
                current_obat = next((o for o in daftar_obat if o["kode_obat"] == kode_ubah), {})
                with st.form("form_update_harga"):
                    harga_baru = st.number_input(
                        "Harga Baru (Rp):",
                        min_value=0,
                        value=int(float(current_obat.get("harga_jual", 25000))),
                        step=500
                    )
                    if st.form_submit_button("💾 Update Harga", use_container_width=True):
                        try:
                            dao.update_harga(kode_ubah, harga_baru)
                            st.session_state.alert_crud = ("ok", f"🎉 Harga **{kode_ubah}** berhasil diubah menjadi Rp {int(harga_baru):,}!")
                        except Exception as e:
                            st.session_state.alert_crud = ("err", f"⛔ Gagal update harga:\n`{e}`")
                        st.rerun()

        # ---- DELETE ----
        with cr3:
            st.markdown("**3. DELETE (Drop Obat):**")
            if daftar_obat:
                kode_hapus = st.selectbox(
                    "Pilih Obat:",
                    [o["kode_obat"] for o in daftar_obat],
                    format_func=lambda k: f"{k} — {next((o['nama_obat'] for o in daftar_obat if o['kode_obat']==k), k)}",
                    key="sb_del_obat"
                )
                with st.form("form_delete_obat"):
                    st.caption(f"Drop obat **{kode_hapus}** dari master obat (misal obat sudah tidak beredar/ditarik BPOM). Riwayat transaksi penjualan masa lalu tetap tersimpan di database untuk audit.")
                    if st.form_submit_button("🗑️ Drop Obat", use_container_width=True, type="secondary"):
                        try:
                            dao.hapus_obat(kode_hapus)
                            st.session_state.alert_crud = ("ok", f"🎉 Obat **{kode_hapus}** berhasil di-drop/dihapus dari master obat! Riwayat transaksi penjualan tetap aman di database.")
                        except Exception as e:
                            st.session_state.alert_crud = ("err", f"⛔ Gagal drop obat:\n`{e}`")
                        st.rerun()

    # ----------------------------------------------------------
    # ADMIN TAB 4 — MANAJEMEN PENGGUNA (CRUD)
    # ----------------------------------------------------------
    with tab4:
        st.markdown("#### 👥 Manajemen Akun Pengguna")
        st.caption("Admin Pusat mengelola akun pengguna: tambah, ubah data/reset password, dan hapus akun staf apotek.")

        conn = conn_aktif()
        admin_dao = AdminDAO(conn)

        if st.session_state.alert_user:
            tipe_a, pesan_a = st.session_state.alert_user
            (st.success if tipe_a == "ok" else st.error)(pesan_a)
            st.session_state.alert_user = None

        daftar_user = admin_dao.ambil_semua_pengguna()
        st.markdown(f"**Daftar Pengguna Sistem ({len(daftar_user)} Pengguna):**")
        if daftar_user:
            st.dataframe(
                pd.DataFrame(daftar_user)[["id_pengguna", "username", "nama_lengkap", "peran", "nama_cabang"]],
                use_container_width=True, hide_index=True
            )

        st.markdown("---")
        st.markdown("##### 🛠️ Operasi CRUD Pengguna:")

        daftar_cbg_all = admin_dao.ambil_semua_cabang()
        list_cbg_opsi  = ["NONE"] + [c["kode_cabang"] for c in daftar_cbg_all]

        usr_col1, usr_col2, usr_col3 = st.columns(3, gap="medium")

        # ---- CREATE ----
        with usr_col1:
            st.markdown("**1. Tambah Pengguna Baru:**")
            with st.form("form_tambah_user"):
                new_u    = st.text_input("Username:", placeholder="Contoh: kasir.bogor")
                new_p    = st.text_input("Password Awal:", type="password", placeholder="Kata sandi")
                new_nama = st.text_input("Nama Lengkap:", placeholder="Nama staf apotek")
                new_peran = st.selectbox("Peran:", ["KASIR", "APOTEKER", "ADMIN_PUSAT"])
                new_cbg  = st.selectbox(
                    "Cabang Penugasan:", list_cbg_opsi,
                    format_func=lambda k: "Pusat (Semua Cabang)" if k == "NONE"
                                 else f"{k} — {next((c['nama_cabang'] for c in daftar_cbg_all if c['kode_cabang']==k), k)}"
                )
                st.caption("🔒 Password otomatis di-hash dengan Bcrypt sebelum disimpan ke database.")
                if st.form_submit_button("➕ Tambah Pengguna", use_container_width=True):
                    if not new_u.strip() or not new_p.strip() or not new_nama.strip():
                        st.error("Semua field wajib diisi!")
                    else:
                        try:
                            admin_dao.tambah_pengguna(new_u.strip(), new_p.strip(), new_nama.strip(), new_peran, new_cbg)
                            st.session_state.alert_user = ("ok", f"✅ Pengguna `{new_u.strip()}` berhasil dibuat!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Gagal tambah pengguna: {e}")

        # ---- UPDATE ----
        with usr_col2:
            st.markdown("**2. Ubah Data / Reset Password:**")
            if daftar_user:
                user_target_id = st.selectbox(
                    "Pilih Pengguna:",
                    [u["id_pengguna"] for u in daftar_user],
                    format_func=lambda x: next(
                        (f"{u['username']} — {u['nama_lengkap']}" for u in daftar_user if u["id_pengguna"] == x), str(x)
                    ),
                    key="sb_edit_user"
                )
                target_data = next((u for u in daftar_user if u["id_pengguna"] == user_target_id), {})
                with st.form("form_edit_user"):
                    edit_u_nama = st.text_input("Nama Lengkap:", value=target_data.get("nama_lengkap", ""))
                    current_peran_idx = ["KASIR", "APOTEKER", "ADMIN_PUSAT"].index(target_data.get("peran", "KASIR"))
                    edit_u_peran = st.selectbox("Peran:", ["KASIR", "APOTEKER", "ADMIN_PUSAT"], index=current_peran_idx)
                    curr_cbg_val = target_data.get("kode_cabang") if target_data.get("kode_cabang") in list_cbg_opsi else "NONE"
                    edit_u_cbg = st.selectbox(
                        "Cabang:", list_cbg_opsi,
                        index=list_cbg_opsi.index(curr_cbg_val),
                        format_func=lambda k: "Pusat (Semua Cabang)" if k == "NONE"
                                     else f"{k} — {next((c['nama_cabang'] for c in daftar_cbg_all if c['kode_cabang']==k), k)}"
                    )
                    edit_u_pwd = st.text_input("Ganti Password (kosongkan jika tidak diubah):", type="password")
                    if st.form_submit_button("💾 Simpan Perubahan", use_container_width=True):
                        try:
                            admin_dao.update_pengguna(user_target_id, edit_u_nama, edit_u_peran, edit_u_cbg, edit_u_pwd)
                            st.session_state.alert_user = ("ok", "✅ Data pengguna berhasil diperbarui!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Gagal update pengguna: {e}")

        # ---- DELETE ----
        with usr_col3:
            st.markdown("**3. Drop Pengguna:**")
            if daftar_user:
                del_user_id = st.selectbox(
                    "Pilih Pengguna:",
                    [u["id_pengguna"] for u in daftar_user],
                    format_func=lambda x: next(
                        (f"{u['username']} ({u['nama_lengkap']})" for u in daftar_user if u["id_pengguna"] == x), str(x)
                    ),
                    key="sb_del_user"
                )
                with st.form("form_del_user"):
                    st.caption("Drop akun staf/pengguna. Data profil pengguna otomatis di-backup, dan riwayat transaksi masa lalu tetap tersimpan di basis data.")
                    if st.form_submit_button("🗑️ Drop Pengguna", use_container_width=True, type="secondary"):
                        if del_user_id == st.session_state.auth["id_pengguna"]:
                            st.error("❌ Tidak dapat menghapus akun Anda sendiri yang sedang aktif!")
                        else:
                            try:
                                admin_dao.hapus_pengguna(del_user_id)
                                st.session_state.alert_user = ("ok", "🎉 Pengguna berhasil di-drop! Profil pengguna telah di-backup dan riwayat transaksi tetap tersimpan aman di database.")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Gagal drop pengguna: {e}")


# ========================================================
# ============================================================
# KASIR / APOTEKER — 3 TAB
# (1. Transaksi Penjualan | 2. Stok Obat Cabang | 3. Riwayat Penjualan)
# ============================================================
# ========================================================
else:

    if PERAN == "KASIR":
        tab1_label   = "🧾 1. Transaksi Penjualan"
        tab1_caption = (
            "Kasir melayani transaksi penjualan obat. "
            "Catatan: Penjualan **Obat Keras (KTG-03)** hanya diizinkan untuk Apoteker. "
            "Jika Kasir menjual Obat Keras, transaksi akan otomatis ditolak dan di-ROLLBACK oleh database."
        )
    else:
        tab1_label   = "💊 1. Transaksi Penjualan"
        tab1_caption = (
            "Apoteker memiliki wewenang melayani penjualan **semua kategori obat** termasuk "
            "**Obat Keras (KTG-03)** sesuai aturan bisnis."
        )

    tab1, tab2, tab3 = st.tabs([
        tab1_label,
        "📦 2. Stok Obat Cabang",
        "📋 3. Riwayat Penjualan",
    ])

    # ----------------------------------------------------------
    # KASIR/APOTEKER TAB 1 — TRANSAKSI PENJUALAN
    # ----------------------------------------------------------
    with tab1:
        st.markdown(f"#### {LABEL['icon']} Transaksi Penjualan")
        st.caption(tab1_caption)

        conn = conn_aktif()
        svc  = PenjualanService(conn)
        dao  = ObatDAO(conn)

        # Notifikasi sukses setelah simpan transaksi (keranjang sudah kosong)
        if st.session_state.transaksi_sukses:
            ts = st.session_state.transaksi_sukses
            st.success(f"🎉 **Transaksi Berhasil!** Faktur `{ts['faktur']}` tersimpan, stok berkurang real-time!")
            c_dl, c_cls = st.columns([2, 1])
            with c_dl:
                st.download_button(
                    label="📥 Unduh Struk Transaksi (.txt)",
                    data=ts["struk"],
                    file_name=f"{ts['faktur']}.txt",
                    mime="text/plain",
                    key="btn_dl_struk"
                )
            with c_cls:
                if st.button("✖️ Tutup Notifikasi", key="btn_close_notif"):
                    st.session_state.transaksi_sukses = None
                    st.rerun()
            st.markdown("---")

        cabang_transaksi = st.session_state.auth["cabang"]

        kol_kiri, kol_kanan = st.columns([1, 1], gap="medium")

        with kol_kiri:
            st.markdown("**① Informasi Faktur**")
            col_f1, col_f2 = st.columns([3, 1])
            with col_f1:
                st.text_input("Nomor Faktur (Otomatis dari Sistem):", value=st.session_state.curr_faktur, disabled=True)
            with col_f2:
                st.write(""); st.write("")
                if st.button("🔄 Baru"):
                    st.session_state.curr_faktur = f"FKT-{datetime.now().strftime('%Y%m%d%H%M%S')}"
                    st.session_state.transaksi_sukses = None
                    st.rerun()

            st.info(f"📍 **Cabang Transaksi:** `{cabang_transaksi}` (sesuai akun `{st.session_state.auth['user']}`)")

            st.markdown("**② Tambah Obat ke Keranjang**")
            # QA 2 Point 1: Dropdown obat muncul SEMUA (tidak difilter).
            # Jika Kasir memilih Obat Keras, Stored Procedure MariaDB akan menolak & me-rollback.
            daftar_obat = dao.ambil_semua()

            if not daftar_obat:
                st.warning("Belum ada data obat di database.")
            else:
                pilihan_dict = {
                    f"{o['kode_obat']} - {o['nama_obat']} [{o['nama_kategori']}] Rp {int(o['harga_jual']):,}": o
                    for o in daftar_obat
                }
                obat_terpilih = st.selectbox("Pilih Obat:", list(pilihan_dict.keys()))
                obj_obat      = pilihan_dict[obat_terpilih]

                if PERAN == "KASIR" and obj_obat.get("nama_kategori") == "Obat Keras":
                    st.warning("⚠️ **Perhatian:** Obat ini berkategori **Obat Keras (KTG-03)**. Kasir dilarang menjual Obat Keras — jika dimasukkan dan disimpan, transaksi akan ditolak & di-ROLLBACK oleh database.")

                col_j, col_t = st.columns([1, 1])
                with col_j:
                    jumlah_beli = st.number_input("Jumlah:", min_value=1, max_value=100, value=1)
                with col_t:
                    st.write(""); st.write("")
                    if st.button("➕ Masukkan Keranjang", use_container_width=True):
                        st.session_state.transaksi_sukses = None
                        item_ada = False
                        for item in st.session_state.cart:
                            if item["kode_obat"] == obj_obat["kode_obat"]:
                                item["jumlah"]   += int(jumlah_beli)
                                item["subtotal"]  = item["jumlah"] * item["harga"]
                                item_ada = True
                                break
                        if not item_ada:
                            st.session_state.cart.append({
                                "kode_obat": obj_obat["kode_obat"],
                                "nama_obat": obj_obat["nama_obat"],
                                "kategori":  obj_obat["nama_kategori"],
                                "harga":     float(obj_obat["harga_jual"]),
                                "jumlah":    int(jumlah_beli),
                                "subtotal":  float(obj_obat["harga_jual"]) * int(jumlah_beli)
                            })
                        st.rerun()

        with kol_kanan:
            st.markdown("**③ Keranjang Belanja**")
            if not st.session_state.cart:
                st.info("Keranjang kosong. Tambahkan obat dari sisi kiri.")
            else:
                df_cart = pd.DataFrame(st.session_state.cart)[
                    ["kode_obat","nama_obat","kategori","jumlah","harga","subtotal"]
                ]
                st.dataframe(df_cart, use_container_width=True, hide_index=True)
                total = sum(x["subtotal"] for x in st.session_state.cart)
                st.markdown(f"### Total: **Rp {int(total):,}**")
                cs1, cs2 = st.columns(2)
                with cs1:
                    if st.button("✅ Simpan Transaksi", type="primary", use_container_width=True):
                        ok, pesan = svc.simpan_transaksi(
                            st.session_state.curr_faktur,
                            cabang_transaksi,
                            st.session_state.cart
                        )
                        if ok:
                            # Struk digital
                            struk_text  = f"========================================\n"
                            struk_text += f"       PT SEHAT BERSAMA FARMA           \n"
                            struk_text += f"   Apotek Multi-Cabang ({cabang_transaksi})\n"
                            struk_text += f"========================================\n"
                            struk_text += f"No Faktur : {st.session_state.curr_faktur}\n"
                            struk_text += f"Waktu     : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                            struk_text += f"Petugas   : {st.session_state.auth['nama_lengkap']} ({st.session_state.auth['user']})\n"
                            struk_text += f"----------------------------------------\n"
                            for it in st.session_state.cart:
                                struk_text += f"{it['nama_obat']} x{it['jumlah']} @Rp {int(it['harga']):,} = Rp {int(it['subtotal']):,}\n"
                            struk_text += f"----------------------------------------\n"
                            struk_text += f"TOTAL     : Rp {int(total):,}\n"
                            struk_text += f"========================================\n"
                            struk_text += f"   Terima Kasih Atas Kunjungan Anda!   \n"

                            # QA 2 Point 2: Langsung kosongkan keranjang dan rerun
                            st.session_state.transaksi_sukses = {
                                "faktur": st.session_state.curr_faktur,
                                "struk": struk_text
                            }
                            st.session_state.cart = []
                            st.session_state.curr_faktur = f"FKT-{datetime.now().strftime('%Y%m%d%H%M%S')}"
                            st.rerun()
                        else:
                            # Jika ditolak SP (mis. Kasir jual Obat Keras atau stok kurang)
                            st.error(f"❌ Transaksi Dibatalkan (ROLLBACK):\n\n`{pesan}`")
                with cs2:
                    if st.button("🗑️ Kosongkan", use_container_width=True):
                        st.session_state.cart = []
                        st.session_state.transaksi_sukses = None
                        st.rerun()

    # ----------------------------------------------------------
    # KASIR/APOTEKER TAB 2 — STOK OBAT CABANG
    # ----------------------------------------------------------
    with tab2:
        st.markdown(f"#### 📦 Stok Obat — Cabang `{st.session_state.auth['cabang']}`")
        st.caption(
            "Data difilter otomatis oleh database (`v_stok_cabang`). "
            "Anda hanya dapat melihat stok cabang penugasan Anda sendiri."
        )

        conn = conn_aktif()
        svc  = PenjualanService(conn)

        if st.button("🔄 Refresh Stok"):
            st.rerun()

        stok = svc.ambil_stok_cabang()
        if stok:
            df_stok = pd.DataFrame(stok)

            df_kritis = df_stok[df_stok["jumlah_stok"] <= df_stok["stok_minimum"]]
            if not df_kritis.empty:
                st.error(f"🚨 **{len(df_kritis)} obat** memiliki stok di bawah atau sama dengan batas minimum!")
                st.dataframe(
                    df_kritis[["kode_obat","nama_obat","jumlah_stok","stok_minimum"]],
                    use_container_width=True, hide_index=True
                )
                st.markdown("---")

            st.markdown("**Semua Stok Obat Cabang:**")
            st.dataframe(
                df_stok[["kode_cabang","nama_cabang","kode_obat","nama_obat","jumlah_stok","stok_minimum"]],
                use_container_width=True, hide_index=True
            )
        else:
            st.info("Tidak ada data stok untuk cabang Anda.")

    # ----------------------------------------------------------
    # KASIR/APOTEKER TAB 3 — RIWAYAT PENJUALAN
    # (QA 2 Point 4: Menyertakan kolom kode_obat dan nama_obat)
    # ----------------------------------------------------------
    with tab3:
        st.markdown(f"#### 📋 Riwayat Penjualan — Cabang `{st.session_state.auth['cabang']}`")
        st.caption(
            "Riwayat transaksi penjualan cabang Anda beserta rincian kode obat dan nama obat yang terjual."
        )

        conn = conn_aktif()
        svc  = PenjualanService(conn)

        if st.button("🔄 Refresh Riwayat"):
            st.rerun()

        cabang_saya = st.session_state.auth["cabang"]
        riwayat = svc.ambil_riwayat_penjualan(kode_cabang=cabang_saya)
        if riwayat:
            df_riwayat = pd.DataFrame(riwayat)

            # Hitung total omset unik per faktur
            total_omset_cabang = df_riwayat.drop_duplicates(subset=["nomor_faktur"])["total"].sum()
            total_faktur_cabang = df_riwayat["nomor_faktur"].nunique()

            r1, r2, r3 = st.columns(3)
            render_kpi(r1, "Total Transaksi",    f"{total_faktur_cabang} Faktur",      f"Cabang {cabang_saya}")
            render_kpi(r2, "Total Item Terjual", f"{len(df_riwayat)} Baris Item",      "Rincian Obat")
            render_kpi(r3, "Total Omset Cabang", format_rupiah(total_omset_cabang),     "Semua Periode")

            st.markdown("---")
            st.markdown(f"**Rincian Transaksi Penjualan Cabang {cabang_saya}:**")
            
            # Kolom wajib: kode_obat dan nama_obat
            cols_riwayat = [
                "nomor_faktur", "tanggal_jam", "kode_cabang",
                "kode_obat", "nama_obat", "jumlah", "harga_satuan", "subtotal", "total"
            ]
            cols_show = [c for c in cols_riwayat if c in df_riwayat.columns]
            st.dataframe(
                df_riwayat[cols_show],
                use_container_width=True, hide_index=True
            )
        else:
            st.info("Belum ada riwayat penjualan untuk cabang Anda.")
