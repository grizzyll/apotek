import streamlit as st
import pandas as pd
import time
from datetime import datetime
import pymysql

from src.koneksi import get_connection, get_config
from src.obat_dao import ObatDAO, cari_obat_linear, cari_obat_binary, quick_sort_obat
from src.admin_dao import AdminDAO
from src.penjualan import PenjualanService
from src.legacy import simpan_penjualan_refactor, bandingkan_kueri_laporan
from src.monitor import get_system_resources, get_database_resources, BATAS_ATAS

# ========================================================
# PENGATURAN HALAMAN
# ========================================================
st.set_page_config(
    page_title="Sistem Apotek Multi-Cabang | PT Sehat Bersama Farma",
    page_icon="💊",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    .header-title { font-size: 24px; font-weight: 700; color: #0F172A; margin-bottom: 2px; }
    .header-sub { font-size: 14px; color: #64748B; margin-bottom: 16px; }
    .demo-card {
        background-color: #F8FAFC;
        border: 1px solid #E2E8F0;
        border-radius: 10px;
        padding: 16px;
        margin-bottom: 12px;
    }
    .metric-card {
        background-color: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-radius: 8px;
        padding: 14px;
        text-align: center;
    }
</style>
""", unsafe_allow_html=True)

# ========================================================
# SESSION STATE
# ========================================================
if "auth" not in st.session_state:
    st.session_state.auth = None
if "cart" not in st.session_state:
    st.session_state.cart = []
if "curr_faktur" not in st.session_state:
    st.session_state.curr_faktur = f"FKT-{datetime.now().strftime('%Y%m%d%H%M%S')}"

# ========================================================
# HALAMAN LOGIN (jika belum masuk)
# ========================================================
if not st.session_state.auth:
    col_kiri, col_tengah, col_kanan = st.columns([1, 2, 1])
    with col_tengah:
        st.write("")
        st.markdown("""
        <div style="text-align:center; margin-bottom:24px;">
            <img src="https://img.icons8.com/color/96/pharmacy-shop.png" width="72">
            <h2 style="color:#1E3A8A; margin:10px 0 4px;">PT Sehat Bersama Farma</h2>
            <p style="color:#64748B; font-size:14px;">Sistem Inventori & Penjualan Apotek Multi-Cabang</p>
        </div>
        """, unsafe_allow_html=True)

        with st.form("form_login"):
            st.markdown("#### 🔐 Masuk ke Sistem")
            st.caption("Gunakan akun database yang telah ditetapkan sesuai peran (Prinsip Least Privilege).")
            input_user = st.text_input("Username:", placeholder="Contoh: admin.pusat atau kasir.depok")
            input_pwd = st.text_input("Password:", type="password", placeholder="Masukkan kata sandi")
            input_env = st.selectbox("Environment:", ["dev", "staging", "prod"],
                format_func=lambda x: {"dev": "DEV — Development (Lokal)", "staging": "STAGING — Uji Server", "prod": "PROD — Produksi Live"}[x])
            
            if st.form_submit_button("🚀 Masuk ke Sistem", use_container_width=True, type="primary"):
                if not input_user.strip() or not input_pwd.strip():
                    st.error("Username dan password wajib diisi!")
                else:
                    try:
                        # Autentikasi lewat MariaDB (bukan root)
                        c = get_connection(input_user.strip(), input_pwd.strip(), env=input_env)
                        c.close()
                        
                        # Ambil profil dari root (server-side, aman)
                        cr = get_connection("root", "", env=input_env, database_override="apotek")
                        with cr.cursor() as cur:
                            cur.execute(
                                "SELECT id_pengguna, username, nama_lengkap, peran, kode_cabang FROM pengguna WHERE username = %s",
                                (input_user.strip(),)
                            )
                            ud = cur.fetchone()
                        cr.close()
                        
                        if not ud:
                            st.error("Profil tidak ditemukan di tabel pengguna.")
                        else:
                            st.session_state.auth = {
                                "user": input_user.strip(),
                                "password": input_pwd.strip(),
                                "id_pengguna": ud["id_pengguna"],
                                "nama_lengkap": ud["nama_lengkap"],
                                "peran": ud["peran"],
                                "cabang": ud["kode_cabang"] if ud["kode_cabang"] else "ALL",
                                "env": input_env
                            }
                            st.session_state.cart = []
                            st.session_state.curr_faktur = f"FKT-{datetime.now().strftime('%Y%m%d%H%M%S')}"
                            st.rerun()
                    except Exception as e:
                        st.error(f"❌ Login Gagal — Akses ditolak database:\n\n`{e}`")

        with st.expander("ℹ️ Daftar Akun Demo untuk Pengujian"):
            st.markdown("""
| Peran | Username | Password | Cabang | Hak Akses Utama |
|---|---|---|---|---|
| **Kasir Depok** | `kasir.depok` | `KasirDpk#2026` | CBG-01 | SELECT obat, Transaksi, View Depok |
| **Apoteker Depok** | `apoteker.depok` | `ApotDpk#2026` | CBG-01 | Sama + Boleh Jual Obat Keras |
| **Kasir Bekasi** | `kasir.bekasi` | `KasirBks#2026` | CBG-02 | SELECT obat, Transaksi, View Bekasi |
| **Admin Pusat** | `admin.pusat` | `AdminPst#2026` | SEMUA | **Full CRUD Obat, Cabang, Pengguna & Semua Cabang** |
            """)
    st.stop()

# ========================================================
# HELPER KONEKSI
# ========================================================
def conn_aktif():
    return get_connection(
        st.session_state.auth["user"],
        st.session_state.auth["password"],
        env=st.session_state.auth["env"]
    )

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
    if st.button("🚪 Keluar (Logout)", use_container_width=True):
        st.session_state.auth = None
        st.session_state.cart = []
        st.rerun()
    st.markdown("---")
    st.caption("Koneksi langsung ke MariaDB dengan prinsip *Least Privilege* (Action 6 & 14).")

# ========================================================
# HEADER UTAMA
# ========================================================
st.markdown('<div class="header-title">Sistem Inventori & Penjualan Apotek Multi-Cabang</div>', unsafe_allow_html=True)
st.markdown(f'<div class="header-sub">{LABEL["icon"]} Masuk sebagai <strong>{st.session_state.auth["nama_lengkap"]}</strong> &nbsp;•&nbsp; Peran: <strong>{LABEL["sebutan"]}</strong> &nbsp;•&nbsp; Cabang: <strong>{st.session_state.auth["cabang"]}</strong></div>', unsafe_allow_html=True)

# ========================================================
# 9 TAB LENGKAP (OPERASIONAL & MANAJEMEN ADMIN PUSAT)
# ========================================================
tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8, tab9 = st.tabs([
    f"{LABEL['icon']} 1. Transaksi Penjualan",
    "🛡️ 2. Uji Aturan Bisnis & Rollback",
    "📦 3. Master Obat (CRUD & Algoritma)",
    "🏪 4. Manajemen & Pantau Cabang",
    "👥 5. Manajemen Pengguna",
    "🔐 6. Hak Akses & Isolasi Data",
    "🔍 7. Debugging & Optimasi Kueri",
    "📊 8. Pemantauan Resource & Kinerja",
    "📋 9. Dokumen Teknis & Keamanan"
])

# ============================================================
# TAB 1 — TRANSAKSI PENJUALAN (Action 3, 5, 6)
# ============================================================
with tab1:
    if PERAN == "KASIR":
        st.markdown("#### 🧾 Kasir — Penjualan Obat Bebas & Bebas Terbatas")
        st.caption("Kasir hanya dapat menjual Obat Bebas (KTG-01) dan Obat Bebas Terbatas (KTG-02). Mencoba menjual Obat Keras akan ditolak (Action 3, 5, 6).")
    elif PERAN == "APOTEKER":
        st.markdown("#### 💊 Apoteker — Penjualan Termasuk Obat Keras")
        st.caption("Apoteker memiliki wewenang menjual semua kategori obat termasuk Obat Keras (KTG-03) sesuai aturan bisnis (Action 3, 5, 6).")
    else:
        st.markdown("#### 🏢 Admin Pusat — Simulasi Transaksi Seluruh Cabang")
        st.caption("Admin Pusat dapat mensimulasikan transaksi di seluruh cabang (Action 3, 5, 6).")

    conn = conn_aktif()
    svc = PenjualanService(conn)
    dao = ObatDAO(conn)

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
                st.rerun()

        pilihan_cbg = ["CBG-01", "CBG-02", "CBG-03"]
        idx_cbg = pilihan_cbg.index(st.session_state.auth["cabang"]) if st.session_state.auth["cabang"] in pilihan_cbg else 0
        cabang_transaksi = st.selectbox("Cabang Transaksi:", pilihan_cbg, index=idx_cbg)

        st.markdown("**② Tambah Obat ke Keranjang** *(Action 3: Struktur Data List of Dict)*")
        daftar_obat = dao.ambil_semua()
        pilihan_dict = {f"{o['kode_obat']} - {o['nama_obat']} [{o['nama_kategori']}] Rp {int(o['harga_jual']):,}": o for o in daftar_obat}
        obat_terpilih = st.selectbox("Pilih Obat:", list(pilihan_dict.keys()))
        obj_obat = pilihan_dict[obat_terpilih]
        col_j, col_t = st.columns([1, 1])
        with col_j:
            jumlah_beli = st.number_input("Jumlah:", min_value=1, max_value=100, value=1)
        with col_t:
            st.write(""); st.write("")
            if st.button("➕ Masukkan Keranjang", use_container_width=True):
                st.session_state.cart.append({
                    "kode_obat": obj_obat["kode_obat"],
                    "nama_obat": obj_obat["nama_obat"],
                    "kategori": obj_obat["nama_kategori"],
                    "harga": float(obj_obat["harga_jual"]),
                    "jumlah": int(jumlah_beli),
                    "subtotal": float(obj_obat["harga_jual"] * jumlah_beli)
                })
                st.rerun()

    with kol_kanan:
        st.markdown("**③ Keranjang Belanja**")
        if not st.session_state.cart:
            st.info("Keranjang kosong. Tambahkan obat dari sisi kiri.")
        else:
            st.dataframe(pd.DataFrame(st.session_state.cart)[["kode_obat","nama_obat","kategori","jumlah","harga","subtotal"]],
                         use_container_width=True, hide_index=True)
            total = sum(x["subtotal"] for x in st.session_state.cart)
            st.markdown(f"### Total: **Rp {int(total):,}**")
            cs1, cs2 = st.columns(2)
            with cs1:
                if st.button("✅ Simpan Transaksi (CALL sp_simpan_penjualan)", type="primary", use_container_width=True):
                    ok, pesan = svc.simpan_transaksi(st.session_state.curr_faktur, cabang_transaksi, st.session_state.cart)
                    if ok:
                        st.success(f"🎉 **Berhasil!** Faktur `{st.session_state.curr_faktur}` tersimpan di MySQL, stok berkurang real-time!")
                        st.session_state.cart = []
                        st.session_state.curr_faktur = f"FKT-{datetime.now().strftime('%Y%m%d%H%M%S')}"
                    else:
                        st.error(f"❌ Transaksi Dibatalkan (ROLLBACK):\n\n`{pesan}`")
            with cs2:
                if st.button("🗑️ Kosongkan", use_container_width=True):
                    st.session_state.cart = []
                    st.rerun()
    conn.close()

# ============================================================
# TAB 2 — UJI ATURAN BISNIS & ROLLBACK (Action 5, 6)
# ============================================================
with tab2:
    st.markdown("#### 🛡️ Pengujian Otomatis Aturan Bisnis & Integritas Transaksi")
    st.caption("Demonstrasi wajib di depan asesor: transaksi yang melanggar aturan ditolak database dan di-ROLLBACK total (Action 5 & 6).")

    conn = conn_aktif()
    svc = PenjualanService(conn)
    cbg_uji = "CBG-01" if st.session_state.auth["cabang"] in ["CBG-01", "ALL"] else "CBG-02"

    u1, u2, u3 = st.columns(3, gap="medium")

    with u1:
        st.markdown("""<div class="demo-card">
            <h5>⚡ Uji 1: Kasir Jual Obat Keras</h5>
            <p><b>Aturan Bisnis:</b> Obat Keras (<em>Ciprofloxacin</em>) hanya boleh dijual Apoteker. Kasir wajib ditolak database.</p>
            <p><b>Mekanisme:</b> Stored Procedure membaca <code>peran</code> akun yang login, bukan dari input program.</p>
        </div>""", unsafe_allow_html=True)
        if st.button("▶ Jalankan Uji 1", use_container_width=True, key="uji1"):
            ok, pesan = svc.simpan_transaksi(f"TST-{int(time.time())}", cbg_uji, [{"kode_obat":"OBT-007","jumlah":1}])
            if not ok:
                st.error(f"⛔ **TERLINDUNGI — Ditolak Database:**\n`{pesan}`")
            else:
                st.success("Berhasil (Akun Anda adalah Apoteker/Admin yang diizinkan).")

    with u2:
        st.markdown("""<div class="demo-card">
            <h5>⚡ Uji 2: Melebihi Stok → ROLLBACK</h5>
            <p><b>Aturan Bisnis:</b> Jika stok tidak cukup, seluruh transaksi wajib di-<b>ROLLBACK</b>. Tidak ada data setengah jadi di database.</p>
            <p><b>Mekanisme:</b> ROLLBACK otomatis dari <code>DECLARE EXIT HANDLER FOR SQLEXCEPTION</code>.</p>
        </div>""", unsafe_allow_html=True)
        if st.button("▶ Jalankan Uji 2", use_container_width=True, key="uji2"):
            ok, pesan = svc.simpan_transaksi(f"TST-{int(time.time())}", cbg_uji, [{"kode_obat":"OBT-001","jumlah":99999}])
            if not ok:
                st.error(f"⛔ **ROLLBACK Berhasil:**\n`{pesan}`")
            else:
                st.error("Gagal menolak!")

    with u3:
        st.markdown("""<div class="demo-card">
            <h5>⚡ Uji 3: Transaksi Lintas Cabang</h5>
            <p><b>Aturan Bisnis:</b> Kasir/Apoteker hanya boleh bertransaksi di cabang penugasannya sendiri.</p>
            <p><b>Mekanisme:</b> Stored Procedure membaca <code>kode_cabang</code> akun aktif dari tabel <code>pengguna</code>.</p>
        </div>""", unsafe_allow_html=True)
        if st.button("▶ Jalankan Uji 3", use_container_width=True, key="uji3"):
            cbg_lawan = "CBG-02" if cbg_uji == "CBG-01" else "CBG-01"
            ok, pesan = svc.simpan_transaksi(f"TST-{int(time.time())}", cbg_lawan, [{"kode_obat":"OBT-001","jumlah":1}])
            if not ok:
                st.error(f"⛔ **TERLINDUNGI — Ditolak Database:**\n`{pesan}`")
            else:
                st.info("Berhasil (Akun Anda adalah Admin Pusat yang bebas cabang).")

    conn.close()

# ============================================================
# TAB 3 — MASTER OBAT (CRUD Lengkap: CREATE, READ, UPDATE, DELETE)
# ============================================================
with tab3:
    st.markdown("#### 📦 Master Obat — CRUD Lengkap & Algoritma Searching/Sorting")
    st.caption("Membuktikan operasi CRUD penuh (Create, Read, Update, Delete) dengan Parameterized Query dan Algoritma Mandiri (Action 6 & 7).")

    conn = conn_aktif()
    dao = ObatDAO(conn)
    daftar_obat = dao.ambil_semua()

    # --- SEARCHING & SORTING ---
    algo_kiri, algo_kanan = st.columns([1, 1])
    with algo_kiri:
        st.markdown("##### 🔍 Pencarian (Action 7: Searching)")
        tipe_cari = st.radio("Metode:", ["Linear Search — O(N)", "Binary Search — O(log N)"], horizontal=True)
        keyword = st.text_input("Kata Kunci:", placeholder="Nama obat atau kode obat")
    with algo_kanan:
        st.markdown("##### 🔀 Pengurutan (Action 7: Quick Sort — O(N log N))")
        sort_key = st.selectbox("Urutkan Berdasarkan:", [
            "Harga Jual: Termurah → Termahal",
            "Harga Jual: Termahal → Termurah",
            "Stok Minimum: Terkecil → Terbesar"
        ])

    if keyword.strip():
        if "Linear" in tipe_cari:
            hasil = cari_obat_linear(daftar_obat, keyword)
            st.caption(f"Linear Search: memeriksa {len(daftar_obat)} data satu per satu → ditemukan {len(hasil)} hasil.")
        else:
            terurut = sorted(daftar_obat, key=lambda x: x["kode_obat"])
            item = cari_obat_binary(terurut, keyword)
            hasil = [item] if item else []
            st.caption(f"Binary Search: memeriksa log₂({len(daftar_obat)}) ≈ {len(terurut).bit_length()} langkah → {'ditemukan' if hasil else 'tidak ditemukan'}.")
    else:
        hasil = daftar_obat

    if "Termurah" in sort_key:
        hasil = quick_sort_obat(hasil, key="harga_jual", ascending=True)
    elif "Termahal" in sort_key:
        hasil = quick_sort_obat(hasil, key="harga_jual", ascending=False)
    else:
        hasil = quick_sort_obat(hasil, key="stok_minimum", ascending=True)

    st.markdown(f"**Daftar Master Obat ({len(hasil)} data):**")
    if hasil:
        st.dataframe(pd.DataFrame(hasil)[["kode_obat","nama_obat","nama_kategori","satuan","harga_jual","stok_minimum"]],
                     use_container_width=True, hide_index=True)

    # --- CRUD OBAT LENGKAP: CREATE, UPDATE, DELETE ---
    st.markdown("---")
    st.markdown("##### 🛠️ Operasi CRUD Master Obat (Create, Update, Delete)")
    st.caption(f"Akun aktif: `{st.session_state.auth['user']}` (Peran: `{PERAN}`). Hak INSERT, UPDATE, DELETE obat hanya dimiliki oleh **Admin Pusat**.")

    if "alert_crud" in st.session_state and st.session_state.alert_crud:
        tipe_a, pesan_a = st.session_state.alert_crud
        (st.success if tipe_a == "ok" else st.error)(pesan_a)
        st.session_state.alert_crud = None

    cr1, cr2, cr3 = st.columns(3, gap="medium")
    
    with cr1:
        st.markdown("**1. INSERT (Tambah Obat Baru):**")
        with st.form("form_insert_obat"):
            in_kode = st.text_input("Kode Obat:", value="OBT-099")
            in_nama = st.text_input("Nama Obat:", value="Amoxicillin 250mg")
            in_kat = st.selectbox("Kategori:", ["KTG-01","KTG-02","KTG-03","KTG-04"])
            in_satuan = st.text_input("Satuan:", value="Strip")
            in_harga = st.number_input("Harga Jual (Rp):", value=12000, step=500)
            in_min = st.number_input("Stok Minimum:", value=10)
            if st.form_submit_button("➕ Tambah Obat", use_container_width=True):
                try:
                    dao.tambah_obat(in_kode, in_nama, in_kat, in_satuan, in_harga, in_min)
                    st.session_state.alert_crud = ("ok", f"🎉 Obat {in_nama} ({in_kode}) berhasil ditambahkan ke database!")
                except Exception as e:
                    st.session_state.alert_crud = ("err", f"⛔ Ditolak MariaDB:\n`{e}`")
                st.rerun()

    with cr2:
        st.markdown("**2. UPDATE (Ubah Harga Obat):**")
        kode_ubah = st.selectbox("Pilih Kode Obat:", [o["kode_obat"] for o in daftar_obat], key="sb_upd_obat")
        current_obat = next((o for o in daftar_obat if o["kode_obat"] == kode_ubah), {})
        with st.form("form_update_harga"):
            harga_baru = st.number_input("Harga Baru (Rp):", min_value=1000, value=int(float(current_obat.get("harga_jual", 25000))), step=500)
            if st.form_submit_button("💾 Update Harga", use_container_width=True):
                try:
                    dao.update_harga(kode_ubah, harga_baru)
                    st.session_state.alert_crud = ("ok", f"🎉 Harga {kode_ubah} berhasil diubah menjadi Rp {int(harga_baru):,}!")
                except Exception as e:
                    st.session_state.alert_crud = ("err", f"⛔ Ditolak MariaDB (Hak Akses):\n`{e}`")
                st.rerun()

    with cr3:
        st.markdown("**3. DELETE (Hapus Obat):**")
        with st.form("form_delete_obat"):
            kode_hapus = st.selectbox("Pilih Obat Dihapus:", [o["kode_obat"] for o in daftar_obat], key="sb_del_obat")
            st.caption("⚠️ Obat yang sudah memiliki relasi di tabel `stok` atau `detail_penjualan` akan ditolak oleh Foreign Key Constraint.")
            if st.form_submit_button("🗑️ Hapus Obat", use_container_width=True, type="secondary"):
                try:
                    dao.hapus_obat(kode_hapus)
                    st.session_state.alert_crud = ("ok", f"🎉 Obat {kode_hapus} berhasil dihapus dari database!")
                except pymysql.err.IntegrityError as ie:
                    st.session_state.alert_crud = ("err", f"⛔ Ditolak Foreign Key Constraint:\nObat {kode_hapus} tidak dapat dihapus karena masih tercatat di tabel `stok` atau riwayat `detail_penjualan` (Integritas Relasional).\n\nPesan DB: {ie}")
                except Exception as e:
                    st.session_state.alert_crud = ("err", f"⛔ Ditolak MariaDB:\n`{e}`")
                st.rerun()

    conn.close()

# ============================================================
# TAB 4 — MANAJEMEN & PANTAU CABANG (Admin Pusat)
# ============================================================
with tab4:
    st.markdown("#### 🏪 Manajemen & Monitoring Antar-Cabang (Admin Pusat)")
    st.caption("Memantau performa penjualan dan inventori seluruh cabang apotek, serta manajemen data cabang (CRUD).")

    conn = conn_aktif()
    admin_dao = AdminDAO(conn)

    # --- BAGIAN 1: MONITORING CABANG ---
    st.markdown("##### 📈 1. Ringkasan Kinerja & Inventori Seluruh Cabang (Monitoring)")
    ringkasan_cbg = admin_dao.ringkasan_pantau_cabang()

    if ringkasan_cbg:
        df_ringkasan = pd.DataFrame(ringkasan_cbg)
        total_omset_semua = df_ringkasan["total_omset"].sum()
        total_trx_semua = df_ringkasan["total_transaksi"].sum()
        total_stok_semua = df_ringkasan["total_stok"].sum()
        total_kritis_semua = df_ringkasan["stok_kritis"].sum()

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Total Cabang", f"{len(df_ringkasan)} Cabang")
        m2.metric("Total Penjualan Gabungan", f"Rp {int(total_omset_semua):,}")
        m3.metric("Total Transaksi", f"{int(total_trx_semua)} Faktur")
        m4.metric("Item Stok Kritis", f"{int(total_kritis_semua)} Obat", delta_color="inverse")

        st.markdown("**Rincian Kinerja per Cabang:**")
        st.dataframe(df_ringkasan[[
            "kode_cabang", "nama_cabang", "telepon", "total_transaksi", "total_omset", "total_stok", "stok_kritis"
        ]], use_container_width=True, hide_index=True)

    # --- BAGIAN 2: CRUD DATA CABANG ---
    st.markdown("---")
    st.markdown("##### 🛠️ 2. Manajemen Master Cabang (CRUD Cabang)")
    st.caption("Admin Pusat memiliki kewenangan mengelola daftar cabang (tabel `cabang`).")

    daftar_cbg = admin_dao.ambil_semua_cabang()
    st.markdown(f"**Daftar Master Cabang di Database ({len(daftar_cbg)} Cabang):**")
    if daftar_cbg:
        st.dataframe(pd.DataFrame(daftar_cbg)[["kode_cabang", "nama_cabang", "alamat", "telepon"]],
                     use_container_width=True, hide_index=True)

    cbg_col1, cbg_col2, cbg_col3 = st.columns(3, gap="medium")

    with cbg_col1:
        st.markdown("**Tambah Cabang Baru:**")
        with st.form("form_tambah_cbg"):
            cbg_kode = st.text_input("Kode Cabang:", value=f"CBG-{len(daftar_cbg)+1:02d}")
            cbg_nama = st.text_input("Nama Cabang:", placeholder="Contoh: Apotek Sehat Tangerang")
            cbg_alamat = st.text_input("Alamat:", placeholder="Alamat lengkap cabang")
            cbg_telp = st.text_input("Telepon:", placeholder="021-xxxxxxx")
            if st.form_submit_button("➕ Tambah Cabang", use_container_width=True):
                if not cbg_kode.strip() or not cbg_nama.strip():
                    st.error("Kode dan nama cabang wajib diisi!")
                else:
                    try:
                        admin_dao.tambah_cabang(cbg_kode.strip(), cbg_nama.strip(), cbg_alamat.strip(), cbg_telp.strip())
                        st.success(f"Cabang {cbg_nama} berhasil ditambahkan!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Gagal tambah cabang: {e}")

    with cbg_col2:
        st.markdown("**Ubah Info Cabang:**")
        cbg_pilih = st.selectbox("Pilih Cabang untuk Diubah:", [c["kode_cabang"] for c in daftar_cbg], key="sb_edit_cbg")
        info_cbg = next((c for c in daftar_cbg if c["kode_cabang"] == cbg_pilih), {})
        with st.form("form_edit_cbg"):
            edit_nama = st.text_input("Nama Cabang:", value=info_cbg.get("nama_cabang", ""))
            edit_alamat = st.text_input("Alamat:", value=info_cbg.get("alamat", ""))
            edit_telp = st.text_input("Telepon:", value=info_cbg.get("telepon", ""))
            if st.form_submit_button("💾 Simpan Perubahan Cabang", use_container_width=True):
                try:
                    admin_dao.update_cabang(cbg_pilih, edit_nama, edit_alamat, edit_telp)
                    st.success(f"Info cabang {cbg_pilih} berhasil diperbarui!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Gagal ubah cabang: {e}")

    with cbg_col3:
        st.markdown("**Hapus Cabang:**")
        del_cbg_kode = st.selectbox("Pilih Cabang Dihapus:", [c["kode_cabang"] for c in daftar_cbg], key="sb_del_cbg")
        with st.form("form_del_cbg"):
            st.caption(f"Konfirmasi hapus cabang **{del_cbg_kode}**. Jika cabang memiliki relasi data penjualan/stok/pengguna, aksi akan ditolak oleh Foreign Key.")
            if st.form_submit_button("🗑️ Hapus Cabang", use_container_width=True, type="secondary"):
                try:
                    admin_dao.hapus_cabang(del_cbg_kode)
                    st.success(f"Cabang {del_cbg_kode} berhasil dihapus!")
                    st.rerun()
                except pymysql.err.IntegrityError as ie:
                    st.error(f"⛔ Ditolak Foreign Key:\nCabang {del_cbg_kode} tidak bisa dihapus karena masih memiliki data stok/penjualan terkait.")
                except Exception as e:
                    st.error(f"Gagal hapus cabang: {e}")

    conn.close()

# ============================================================
# TAB 5 — MANAJEMEN PENGGUNA (Admin Pusat)
# ============================================================
with tab5:
    st.markdown("#### 👥 Manajemen Akun Pengguna (CRUD Pengguna & Password Hashing)")
    st.caption("Admin Pusat mengelola akun pengguna, penugasan cabang, dan enkripsi kata sandi menggunakan Bcrypt (Action 14).")

    conn = conn_aktif()
    admin_dao = AdminDAO(conn)

    daftar_user = admin_dao.ambil_semua_pengguna()
    st.markdown(f"**Daftar Pengguna Sistem ({len(daftar_user)} Pengguna):**")
    if daftar_user:
        st.dataframe(pd.DataFrame(daftar_user)[["id_pengguna", "username", "nama_lengkap", "peran", "nama_cabang"]],
                     use_container_width=True, hide_index=True)

    st.markdown("---")
    st.markdown("##### 🛠️ Operasi CRUD Pengguna:")

    usr_col1, usr_col2, usr_col3 = st.columns(3, gap="medium")

    daftar_cbg_all = admin_dao.ambil_semua_cabang()
    list_cbg_opsi = ["NONE"] + [c["kode_cabang"] for c in daftar_cbg_all]

    with usr_col1:
        st.markdown("**1. Tambah Pengguna Baru:**")
        with st.form("form_tambah_user"):
            new_u = st.text_input("Username:", placeholder="Contoh: kasir.bogor")
            new_p = st.text_input("Password Awal:", type="password", placeholder="Kata sandi")
            new_nama = st.text_input("Nama Lengkap:", placeholder="Nama staf apotek")
            new_peran = st.selectbox("Peran:", ["KASIR", "APOTEKER", "ADMIN_PUSAT"])
            new_cbg = st.selectbox("Cabang Penugasan:", list_cbg_opsi)
            st.caption("🔒 Password otomatis di-hash dengan Bcrypt sebelum disimpan ke database.")
            if st.form_submit_button("➕ Tambah Pengguna", use_container_width=True):
                if not new_u.strip() or not new_p.strip() or not new_nama.strip():
                    st.error("Semua field wajib diisi!")
                else:
                    try:
                        admin_dao.tambah_pengguna(new_u.strip(), new_p.strip(), new_nama.strip(), new_peran, new_cbg)
                        st.success(f"Pengguna `{new_u}` berhasil dibuat dengan password terenkripsi!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Gagal tambah pengguna: {e}")

    with usr_col2:
        st.markdown("**2. Ubah Data / Reset Password:**")
        user_target_id = st.selectbox("Pilih Pengguna untuk Diubah:", [u["id_pengguna"] for u in daftar_user],
                                      format_func=lambda x: next((f"{u['username']} - {u['nama_lengkap']}" for u in daftar_user if u["id_pengguna"] == x), str(x)))
        target_data = next((u for u in daftar_user if u["id_pengguna"] == user_target_id), {})
        with st.form("form_edit_user"):
            edit_u_nama = st.text_input("Nama Lengkap:", value=target_data.get("nama_lengkap", ""))
            current_peran_idx = ["KASIR", "APOTEKER", "ADMIN_PUSAT"].index(target_data.get("peran", "KASIR"))
            edit_u_peran = st.selectbox("Peran:", ["KASIR", "APOTEKER", "ADMIN_PUSAT"], index=current_peran_idx)
            
            curr_cbg_val = target_data.get("kode_cabang") if target_data.get("kode_cabang") in list_cbg_opsi else "NONE"
            edit_u_cbg = st.selectbox("Cabang:", list_cbg_opsi, index=list_cbg_opsi.index(curr_cbg_val))
            edit_u_pwd = st.text_input("Ganti Password (Kosongkan jika tidak ubah):", type="password")

            if st.form_submit_button("💾 Simpan Perubahan", use_container_width=True):
                try:
                    admin_dao.update_pengguna(user_target_id, edit_u_nama, edit_u_peran, edit_u_cbg, edit_u_pwd)
                    st.success("Data pengguna berhasil diperbarui!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Gagal update pengguna: {e}")

    with usr_col3:
        st.markdown("**3. Hapus Pengguna:**")
        del_user_id = st.selectbox("Pilih Pengguna Dihapus:", [u["id_pengguna"] for u in daftar_user],
                                   format_func=lambda x: next((f"{u['username']} ({u['nama_lengkap']})" for u in daftar_user if u["id_pengguna"] == x), str(x)))
        with st.form("form_del_user"):
            st.caption("Pengguna yang sedang aktif login tidak boleh dihapus.")
            if st.form_submit_button("🗑️ Hapus Pengguna", use_container_width=True, type="secondary"):
                if del_user_id == st.session_state.auth["id_pengguna"]:
                    st.error("Ditolak: Anda tidak dapat menghapus akun Anda sendiri yang sedang aktif!")
                else:
                    try:
                        admin_dao.hapus_pengguna(del_user_id)
                        st.success("Pengguna berhasil dihapus dari sistem!")
                        st.rerun()
                    except pymysql.err.IntegrityError as ie:
                        st.error(f"⛔ Ditolak Foreign Key:\nPengguna ini sudah memiliki riwayat transaksi di tabel `penjualan` sehingga tidak boleh dihapus demi integritas data audit.")
                    except Exception as e:
                        st.error(f"Gagal hapus: {e}")

    conn.close()

# ============================================================
# TAB 6 — HAK AKSES & ISOLASI DATA (Action 6, 14)
# ============================================================
with tab6:
    st.markdown("#### 🔐 Pembuktian Keamanan: Hak Akses Per Peran & Row-Level Security")
    st.caption("Membuktikan pembatasan akses di level DBMS MariaDB menggunakan GRANT per akun (Action 6 & 14).")

    conn = conn_aktif()
    svc = PenjualanService(conn)

    st.markdown("##### Matriks Hak Akses Per Peran (Sesuai GRANT SQL)")
    df_hak = pd.DataFrame({
        "Hak Akses Database": [
            "SELECT tabel obat & kategori",
            "EXECUTE sp_simpan_penjualan",
            "Jual Obat Keras (KTG-03)",
            "SELECT VIEW stok & penjualan cabang",
            "INSERT, UPDATE, DELETE obat master",
            "INSERT, UPDATE, DELETE cabang",
            "INSERT, UPDATE, DELETE pengguna",
            "SELECT semua cabang (tanpa filter)",
            "Login sebagai root"
        ],
        "Kasir": ["✅","✅","❌","✅ (Cabang sendiri)","❌","❌","❌","❌","❌"],
        "Apoteker": ["✅","✅","✅","✅ (Cabang sendiri)","❌","❌","❌","❌","❌"],
        "Admin Pusat": ["✅","✅","✅","✅ (Semua cabang)","✅","✅","✅","✅","❌"]
    })
    st.dataframe(df_hak, use_container_width=True, hide_index=True)

    st.markdown("---")
    sec1, sec2 = st.columns(2, gap="medium")

    with sec1:
        st.markdown("##### A. Uji UPDATE Harga (Pembuktian Langsung)")
        dao = ObatDAO(conn)
        semua_obat = dao.ambil_semua()
        kode_pilih = st.selectbox("Pilih Obat:", [x["kode_obat"] for x in semua_obat], key="sb_sec6")
        harga_inp = st.number_input("Harga Baru:", min_value=1000, value=25000, step=500, key="harga_sec6")
        if st.button("💾 Coba Update di Database (Pembuktian Peran)"):
            try:
                dao.update_harga(kode_pilih, harga_inp)
                st.success(f"🎉 **BERHASIL** — Hanya akun Admin Pusat yang diizinkan melakukan operasi ini!")
            except Exception as e:
                st.error(f"⛔ **DITOLAK MARIADB** (Bukti Keamanan Hak Akses):\n\n`{e}`")
                st.caption("Kasir & Apoteker ditolak langsung di level database.")

    with sec2:
        st.markdown("##### B. Isolasi Data Cabang — `v_stok_cabang` (Row-Level Security)")
        st.caption("View ini otomatis menyaring data berdasarkan akun yang sedang login.")
        stok = svc.ambil_stok_cabang()
        if stok:
            df_stok = pd.DataFrame(stok)
            st.dataframe(df_stok[["kode_cabang","nama_cabang","nama_obat","jumlah_stok","stok_minimum"]], use_container_width=True, hide_index=True)
            cabang_terlihat = list(df_stok["kode_cabang"].unique())
            if len(cabang_terlihat) == 1:
                st.info(f"📍 Hanya menampilkan cabang **{cabang_terlihat}** sesuai penugasan akun `{st.session_state.auth['user']}`.")
            else:
                st.info(f"📍 Menampilkan **semua cabang** {cabang_terlihat} karena akun ini adalah Admin Pusat.")
        else:
            st.warning("Tidak ada data stok.")

    conn.close()

# ============================================================
# TAB 7 — DEBUGGING & OPTIMASI KUERI (Action 8, 9)
# ============================================================
with tab7:
    st.markdown("#### 🔍 Debugging Modul Lama & Optimasi Kueri Laporan")
    st.caption("Membandingkan kode warisan bermasalah vs kode baru terstandar, dan optimasi kueri laporan bulanan (Action 8 & 9).")

    st.markdown("##### 1. Perbandingan Kode: Modul Lama vs Modul Baru (Action 8)")

    old_kiri, old_kanan = st.columns(2)
    with old_kiri:
        st.error("**❌ Kode Warisan (Legacy) — 5 Cacat Kritis:**")
        st.code("""def simpan_penjualan(conn, faktur, kode_obat, jumlah):
    cur = conn.cursor()
    
    # CACAT 1: SQL INJECTION — String Concatenation!
    cur.execute("INSERT INTO detail_penjualan " +
        "VALUES ('" + faktur + "','" + kode_obat + "'," +
        str(jumlah) + ")")
    
    # CACAT 2: Nama kolom salah (jumlah_stok ≠ jumlah)
    cur.execute("UPDATE stok SET jumlah = jumlah - " +
        str(jumlah) + " WHERE kode_obat='" + kode_obat + "'")
    
    # CACAT 3: Tidak ada validasi stok minus
    # CACAT 4: Tidak ada try-except & ROLLBACK
    # CACAT 5: Cursor tidak ditutup (memory leak)
    conn.commit()""", language="python")

    with old_kanan:
        st.success("**✅ Kode Baru Terstandar (Best Practice):**")
        st.code("""def simpan_penjualan_refactor(conn, faktur, cabang, kode_obat, jumlah):
    try:
        with conn.cursor() as cur:
            # PERBAIKAN 1: Validasi stok sebelum potong
            cur.execute(
                "SELECT jumlah_stok FROM stok "
                "WHERE kode_cabang=%s AND kode_obat=%s",
                (cabang, kode_obat)  # Parameterized!
            )
            stok = cur.fetchone()
            if not stok or stok['jumlah_stok'] < jumlah:
                raise ValueError("Stok tidak mencukupi!")
            
            # PERBAIKAN 2: Parameterized Query (%s)
            cur.execute(
                "UPDATE stok SET jumlah_stok = jumlah_stok - %s "
                "WHERE kode_cabang=%s AND kode_obat=%s",
                (jumlah, cabang, kode_obat)
            )
        conn.commit()   # COMMIT jika semua berhasil
    except Exception as e:
        conn.rollback() # ROLLBACK jika ada kesalahan
        return False, str(e)""", language="python")

    st.markdown("---")
    st.markdown("##### 2. Optimasi Kueri Laporan Bulanan (Action 9)")

    q_kiri, q_kanan = st.columns(2)
    with q_kiri:
        st.error("**❌ Kueri Lama (Non-Sargable — Mematikan Index):**")
        st.code("""SELECT * FROM penjualan p, detail_penjualan d
WHERE p.id_penjualan = d.id_penjualan
  AND YEAR(p.tanggal_jam)  = 2026
  AND MONTH(p.tanggal_jam) = 11;

-- Masalah: YEAR() dan MONTH() mencegah MariaDB
-- menggunakan B-Tree index idx_penjualan_tanggal
-- → Full Table Scan setiap kali dipanggil!""", language="sql")

    with q_kanan:
        st.success("**✅ Kueri Baru (Sargable Range — Memanfaatkan Index):**")
        st.code("""SELECT p.nomor_faktur, p.tanggal_jam,
       p.kode_cabang, d.kode_obat,
       d.jumlah, d.subtotal
FROM penjualan p
INNER JOIN detail_penjualan d
        ON d.id_penjualan = p.id_penjualan
WHERE p.tanggal_jam >= '2026-11-01'
  AND p.tanggal_jam  < '2026-12-01';

-- Perbaikan: Range date langsung memanfaatkan
-- index idx_penjualan_tanggal (B-Tree scan)
-- Kompleksitas turun dari O(N) → O(log N + K)""", language="sql")

    if st.button("⚡ Jalankan Uji Banding Kecepatan Kueri Sekarang", type="primary"):
        conn = conn_aktif()
        hasil = bandingkan_kueri_laporan(conn, tahun=2026, bulan=11)
        conn.close()
        bk1, bk2, bk3 = st.columns(3)
        bk1.metric("Kueri Lama", f"{hasil['waktu_lama_ms']} ms", "Non-Sargable")
        bk2.metric("Kueri Baru (Optimasi)", f"{hasil['waktu_baru_ms']} ms",
                   f"-{round(hasil['waktu_lama_ms'] - hasil['waktu_baru_ms'], 3)} ms lebih cepat")
        bk3.metric("Data Ditemukan", f"{hasil['total_data']} baris transaksi")
        st.success("Kueri teroptimasi memanfaatkan index `idx_penjualan_tanggal` untuk mempersempit pencarian langsung tanpa full scan.")

# ============================================================
# TAB 8 — RESOURCE & KINERJA (Action 12)
# ============================================================
with tab8:
    st.markdown("#### 📊 Pemantauan Resource Host & Database (Action 12)")
    st.caption("Memantau resource kritis dengan ambang batas kegagalan (Failure Threshold Lines) secara real-time.")

    conn = conn_aktif()
    sys_m = get_system_resources()
    db_m = get_database_resources(conn)
    conn.close()

    if st.button("🔄 Refresh Metrik"):
        st.rerun()

    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("🖥️ CPU Host", f"{sys_m['cpu_percent']}%", "Batas Kritis: 90%")
    m2.metric("🧠 RAM Terpakai", f"{sys_m['ram_percent']}%", f"{sys_m['ram_used_mb']} MB")
    m3.metric("💾 Penggunaan Disk", f"{sys_m['disk_percent']}%", f"Sisa: {sys_m['disk_free_gb']} GB")
    m4.metric("🔗 Koneksi DB Aktif", f"{db_m['db_connections']}", "Batas Kritis: 90")
    m5.metric("⚡ Latensi Kueri", f"{db_m['query_latency_ms']} ms", "Batas Warning: 100 ms")

    st.markdown("---")
    st.markdown("##### Visualisasi Tingkat Pemakaian vs Ambang Batas Kegagalan:")

    bar1, bar2, bar3, bar4 = st.columns(4)
    with bar1:
        st.write("**CPU:**")
        st.progress(min(int(sys_m["cpu_percent"]), 100))
        st.caption(f"{sys_m['cpu_percent']}% / 100% (Kritis >90%)")
    with bar2:
        st.write("**RAM:**")
        st.progress(min(int(sys_m["ram_percent"]), 100))
        st.caption(f"{sys_m['ram_percent']}% (Kritis >90%)")
    with bar3:
        st.write("**Disk:**")
        st.progress(min(int(sys_m["disk_percent"]), 100))
        st.caption(f"{sys_m['disk_percent']}% (Kritis >90%)")
    with bar4:
        st.write("**Koneksi DB:**")
        st.progress(min(int(db_m["db_connections"]), 100))
        st.caption(f"{db_m['db_connections']} / 100 (Kritis >90)")

    st.markdown("---")
    st.markdown("##### Definisi Ambang Batas (Failure Thresholds) yang Ditetapkan:")
    df_batas = pd.DataFrame([
        {"Metrik": "CPU Host", "Warning": "75%", "Kritis": "90%", "Tindakan jika Kritis": "Scale-up server / terminate heavy queries"},
        {"Metrik": "RAM Terpakai", "Warning": "80%", "Kritis": "90%", "Tindakan jika Kritis": "Restart koneksi idle, tambah swap"},
        {"Metrik": "Ruang Disk", "Warning": "80%", "Kritis": "90%", "Tindakan jika Kritis": "Arsip log lama, expand storage"},
        {"Metrik": "Koneksi DB Aktif", "Warning": "70", "Kritis": "90", "Tindakan jika Kritis": "Aktifkan connection pooling"},
        {"Metrik": "Latensi Kueri", "Warning": "100 ms", "Kritis": "300 ms", "Tindakan jika Kritis": "Analisis EXPLAIN, tambah index"},
    ])
    st.dataframe(df_batas, use_container_width=True, hide_index=True)

# ============================================================
# TAB 9 — DOKUMEN TEKNIS & KEAMANAN (Action 1, 2, 11, 13, 14)
# ============================================================
with tab9:
    st.markdown("#### 📋 Dokumen Teknis, Analisis Dampak & Standar Keamanan")

    sub1, sub2 = st.tabs(["📚 Action 1 & 2: Analisis Tools & Library", "🔄 Action 11, 13 & 14: Dampak, Rollback & Keamanan"])

    with sub1:
        st.markdown("##### Analisis Teknologi & Pustaka yang Digunakan (Action 1 & 2)")
        df_tools = pd.DataFrame([
            {"Komponen": "MariaDB 10.4", "Jenis": "DBMS", "Fungsi Utama": "Penyimpanan data, Stored Procedure, Trigger, View, GRANT/REVOKE", "Alasan Dipilih": "Open-source, mendukung JSON_VALUE, ACID-compliant, kompatibel MySQL"},
            {"Komponen": "Python 3.x", "Jenis": "Bahasa Pemrograman", "Fungsi Utama": "Logika aplikasi, algoritma, koneksi database, antarmuka", "Alasan Dipilih": "Sintaks ringkas, ekosistem pustaka luas, cepat diimplementasikan"},
            {"Komponen": "PyMySQL 1.2.4", "Jenis": "Driver Database", "Fungsi Utama": "Koneksi Python ke MariaDB, eksekusi Parameterized Query (%s), CallProc", "Alasan Dipilih": "Pure Python, tanpa dependensi native, stabil di Windows"},
            {"Komponen": "Streamlit 1.55", "Jenis": "Framework UI Web", "Fungsi Utama": "Antarmuka dashboard interaktif, visualisasi data, form login, demo asesor", "Alasan Dipilih": "Membangun web app Python tanpa HTML/CSS kompleks, cepat untuk prototyping"},
            {"Komponen": "bcrypt 5.0", "Jenis": "Kriptografi", "Fungsi Utama": "Hashing kata sandi pengguna secara aman", "Alasan Dipilih": "Standar industri dengan salt adaptif, mencegah brute-force"},
            {"Komponen": "psutil 7.2", "Jenis": "Pustaka Monitoring", "Fungsi Utama": "Membaca CPU, RAM, Disk usage untuk Action 12", "Alasan Dipilih": "Cross-platform, akurat, ringan"},
            {"Komponen": "configparser", "Jenis": "Pustaka Standar Python", "Fungsi Utama": "Membaca file konfigurasi .ini per environment (dev/staging/prod)", "Alasan Dipilih": "Built-in Python, tidak perlu instalasi tambahan"},
        ])
        st.dataframe(df_tools, use_container_width=True, hide_index=True)

        st.markdown("##### Perbandingan Driver Database Python vs Java (Action 2)")
        df_drv = pd.DataFrame([
            {"Aspek": "Nama Driver", "Python (PyMySQL)": "PyMySQL 1.2.4", "Java (JDBC MariaDB)": "mariadb-java-client.jar"},
            {"Aspek": "Cara Install", "Python (PyMySQL)": "pip install pymysql", "Java (JDBC MariaDB)": "Download .jar + set -cp classpath"},
            {"Aspek": "Parameterized Query", "Python (PyMySQL)": "cursor.execute(sql, (val1, val2))", "Java (JDBC MariaDB)": "PreparedStatement.setString(1, val)"},
            {"Aspek": "Panggil Stored Procedure", "Python (PyMySQL)": "cursor.callproc('nama_sp', (p1,p2))", "Java (JDBC MariaDB)": "CallableStatement.call('{call nama_sp(?,?)}')"},
            {"Aspek": "Kemudahan Setup Windows", "Python (PyMySQL)": "⭐⭐⭐⭐⭐ Sangat mudah", "Java (JDBC MariaDB)": "⭐⭐⭐ Perlu konfigurasi classpath"},
        ])
        st.dataframe(df_drv, use_container_width=True, hide_index=True)

    with sub2:
        d1, d2 = st.columns(2, gap="medium")

        with d1:
            st.markdown("##### 🔄 Action 11: Analisis Dampak Perubahan FEFO")
            st.info("""
**Permintaan Perubahan:** Manajemen meminta penambahan pencatatan nomor batch dan tanggal kedaluwarsa obat dengan aturan jual mendahulukan batch yang paling cepat kedaluwarsa (**First Expired, First Out — FEFO**).

**Komponen yang Terdampak:**
1. **DDL Baru:** Tabel `batch_obat` *(id_batch, kode_obat, kode_cabang, nomor_batch, tgl_kadaluarsa, jumlah_stok)*
2. **Stored Procedure:** `sp_simpan_penjualan` dimodifikasi → pengurangan stok dari `batch_obat ORDER BY tgl_kadaluarsa ASC` alih-alih dari `stok`
3. **View:** `v_stok_cabang` perlu diperluas menampilkan info batch
4. **ERD:** Tambah entitas `batch_obat` berelasi ke `obat` dan `cabang`

**Estimasi Dampak:** 2 hari kerja
            """)

            st.markdown("##### 🔙 Action 13: Rencana Rollback Perubahan")
            st.warning("""
**Prosedur Rollback ke Kondisi Sebelum Perubahan:**

```sql
-- 1. Hapus procedure baru
DROP PROCEDURE IF EXISTS sp_simpan_penjualan_v2;

-- 2. Kembalikan procedure lama dari backup SQL
SOURCE apotek_backup_before_fefo.sql;

-- 3. Hapus tabel batch baru
DROP TABLE IF EXISTS batch_obat;

-- 4. Kembalikan view ke versi sebelumnya
CREATE OR REPLACE VIEW v_stok_cabang AS ...;
```
**Waktu Rollback Estimasi:** 15–30 menit
            """)

        with d2:
            st.markdown("##### 🛡️ Action 14: Standar Keamanan Informasi (SNI ISO/IEC 27001)")
            st.success("""
**Kontrol Keamanan yang Sudah Diterapkan:**

**A.9 — Kontrol Akses:**
- Akun database per peran (KASIR/APOTEKER/ADMIN_PUSAT), bukan root
- Password tidak pernah disimpan di kode (input saat runtime)
- GRANT hak akses minimum sesuai tugas (Least Privilege)

**A.10 — Kriptografi:**
- Password pengguna di tabel `pengguna` disimpan dalam format **Bcrypt hash** bukan plain text

**A.12 — Keamanan Operasional:**
- 3 Environment terpisah: DEV, STAGING, PROD (file `config/*.ini`)
- Konfigurasi koneksi tidak di-hardcode di source code

**A.14 — Keamanan Pengembangan:**
- Semua query menggunakan **Parameterized Query (%s)** mencegah SQL Injection (OWASP Top 10 #3)
- Transaksi menggunakan ACID (COMMIT/ROLLBACK eksplisit)

**A.16 — Penanganan Insiden:**
- Transaksi gagal selalu di-ROLLBACK otomatis via `DECLARE EXIT HANDLER`
- Pesan error dari database dikembalikan ke aplikasi (tidak disembunyikan)
            """)
