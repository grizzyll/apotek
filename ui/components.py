import streamlit as st
import html
from ui.format import format_rupiah

def render_header(nama_lengkap, peran, cabang, label_icon, label_sebutan, env="DEV"):
    """Merender banner header atas aplikasi yang modern dan aman dari XSS"""
    nama_esc = html.escape(str(nama_lengkap))
    peran_esc = html.escape(str(label_sebutan))
    cabang_esc = html.escape(str(cabang))
    env_str = str(env).upper()
    env_badge = f'<span style="background:rgba(255,255,255,0.2); padding:3px 10px; border-radius:12px; font-size:12px; font-weight:600;">🌐 {env_str}</span>'
    
    st.markdown(f"""
    <div class="app-header">
        <h2>💊 PT Sehat Bersama Farma</h2>
        <p>Sistem Basis Data & Inventori Apotek Multi-Cabang &nbsp;•&nbsp; 
           {label_icon} Masuk sebagai: <strong>{nama_esc}</strong> ({peran_esc}) &nbsp;•&nbsp; 
           📍 Cabang Penugasan: <strong>{cabang_esc}</strong> &nbsp;•&nbsp;
           {env_badge}
        </p>
    </div>
    """, unsafe_allow_html=True)

def render_kpi(col, label, value, subtext=""):
    """Merender kartu KPI metric dengan visual card bersih"""
    with col:
        st.markdown(f"""
        <div class="kpi-container">
            <div class="kpi-label">{html.escape(label)}</div>
            <div class="kpi-value">{html.escape(str(value))}</div>
            {f'<div class="kpi-sub">{html.escape(subtext)}</div>' if subtext else ''}
        </div>
        """, unsafe_allow_html=True)

def get_badge_kategori(nama_kategori):
    """Mengembalikan HTML badge styling sesuai kategori obat"""
    kat = str(nama_kategori).strip().lower()
    if "keras" in kat:
        return f'<span class="badge-keras">🔒 {html.escape(nama_kategori)}</span>'
    elif "terbatas" in kat:
        return f'<span class="badge-bebas-terbatas">⚠️ {html.escape(nama_kategori)}</span>'
    elif "bebas" in kat:
        return f'<span class="badge-bebas">✅ {html.escape(nama_kategori)}</span>'
    else:
        return f'<span class="badge-alkes">🩹 {html.escape(nama_kategori)}</span>'
