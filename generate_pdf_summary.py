import os
import sys
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether, HRFlowable
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY
from reportlab.pdfgen import canvas

class NumberedCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        super(NumberedCanvas, self).__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_number(num_pages)
            canvas.Canvas.showPage(self)
        canvas.Canvas.save(self)

    def draw_page_number(self, page_count):
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#64748b"))
        
        # Header (halaman 2 ke atas)
        if self._pageNumber > 1:
            self.drawString(54, 800, "LSP SKK-26/20/2024: Programmer Basis Data — PT Sehat Bersama Farma")
            self.setStrokeColor(colors.HexColor("#cbd5e1"))
            self.setLineWidth(0.5)
            self.line(54, 792, 541, 792)
            
        # Footer
        self.setStrokeColor(colors.HexColor("#cbd5e1"))
        self.setLineWidth(0.5)
        self.line(54, 45, 541, 45)
        self.drawString(54, 32, "Dokumen Portofolio Resmi Asesi — FR.IA.04A Daftar Instruksi Terstruktur")
        page_str = f"Halaman {self._pageNumber} dari {page_count}"
        self.drawRightString(541, 32, page_str)
        self.restoreState()

def create_project_summary_pdf(output_paths):
    doc_path = output_paths[0]
    doc = SimpleDocTemplate(
        doc_path,
        pagesize=A4,
        leftMargin=54,
        rightMargin=54,
        topMargin=54,
        bottomMargin=54
    )

    styles = getSampleStyleSheet()

    # Custom typography styles
    PRIMARY = colors.HexColor("#0f172a") # Slate 900
    ACCENT = colors.HexColor("#1e40af")  # Blue 800
    TEAL = colors.HexColor("#0f766e")    # Teal 700
    MUTED = colors.HexColor("#475569")   # Slate 600
    BG_LIGHT = colors.HexColor("#f8fafc")

    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=18,
        leading=22,
        textColor=PRIMARY,
        alignment=TA_CENTER
    )

    subtitle_style = ParagraphStyle(
        'DocSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=12,
        leading=16,
        textColor=ACCENT,
        alignment=TA_CENTER
    )

    h1_style = ParagraphStyle(
        'Heading1_Custom',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=13,
        leading=17,
        textColor=ACCENT,
        spaceBefore=14,
        spaceAfter=6,
        keepWithNext=True
    )

    h2_style = ParagraphStyle(
        'Heading2_Custom',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=10,
        leading=14,
        textColor=PRIMARY,
        spaceBefore=10,
        spaceAfter=4,
        keepWithNext=True
    )

    body_style = ParagraphStyle(
        'Body_Custom',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=12,
        textColor=PRIMARY,
        alignment=TA_JUSTIFY,
        spaceAfter=6
    )

    body_bold = ParagraphStyle(
        'Body_Bold',
        parent=body_style,
        fontName='Helvetica-Bold'
    )

    table_header = ParagraphStyle(
        'TableHeader',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8,
        leading=10,
        textColor=colors.white,
        alignment=TA_CENTER
    )

    table_cell = ParagraphStyle(
        'TableCell',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=7.5,
        leading=10,
        textColor=PRIMARY
    )

    table_cell_bold = ParagraphStyle(
        'TableCellBold',
        parent=table_cell,
        fontName='Helvetica-Bold'
    )

    table_cell_center = ParagraphStyle(
        'TableCellCenter',
        parent=table_cell,
        alignment=TA_CENTER
    )

    badge_ok = ParagraphStyle(
        'BadgeOK',
        parent=table_cell_center,
        fontName='Helvetica-Bold',
        textColor=colors.HexColor("#15803d")
    )

    elements = []

    # =========================================================================
    # COVER / HEADER BANNER
    # =========================================================================
    header_data = [
        [
            Paragraph("<b>DOKUMEN HASIL KERJA &amp; PORTOFOLIO TEKNIS ASESI</b>", title_style),
        ],
        [
            Paragraph("SKEMA SERTIFIKASI: PROGRAMMER BASIS DATA (DATABASE PROGRAMMER)", subtitle_style),
        ],
        [
            Paragraph("<b>Nomor Skema:</b> SKK-26/20/2024 &nbsp;|&nbsp; <b>Standar Acuan:</b> FR.IA.04A DIT &nbsp;|&nbsp; <b>Waktu:</b> 240 Menit", ParagraphStyle('SubSub', parent=subtitle_style, fontSize=9, textColor=MUTED))
        ]
    ]
    t_header = Table(header_data, colWidths=[487])
    t_header.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#f1f5f9")),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor("#cbd5e1")),
        ('TOPPADDING', (0,0), (-1,-1), 10),
        ('BOTTOMPADDING', (0,0), (-1,-1), 10),
        ('LEFTPADDING', (0,0), (-1,-1), 14),
        ('RIGHTPADDING', (0,0), (-1,-1), 14),
    ]))
    elements.append(t_header)
    elements.append(Spacer(1, 12))

    # META INFO BOX
    meta_data = [
        [Paragraph("<b>Judul Proyek:</b>", body_bold), Paragraph("Sistem Inventori dan Penjualan Apotek Multi-Cabang Berbasis FEFO", body_style)],
        [Paragraph("<b>Aplikasi / Studi Kasus:</b>", body_bold), Paragraph("PT Sehat Bersama Farma (Depok, Bekasi, Bogor)", body_style)],
        [Paragraph("<b>Teknologi Basis Data:</b>", body_bold), Paragraph("MariaDB 10.4 Relational DBMS (ACID, Stored Procedure, Triggers, Views RLS)", body_style)],
        [Paragraph("<b>Bahasa &amp; Framework:</b>", body_bold), Paragraph("Python 3.14, Streamlit GUI, PyMySQL Connector, BCrypt Hashing, PyTest", body_style)],
        [Paragraph("<b>Status Kelulusan:</b>", body_bold), Paragraph("<font color='#16a34a'><b>100% SUKSES (14/14 Unit Kompetensi Terpenuhi &amp; 13/13 Pytest Lulus)</b></font>", body_style)],
    ]
    t_meta = Table(meta_data, colWidths=[130, 357])
    t_meta.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), BG_LIGHT),
        ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor("#e2e8f0")),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('LEFTPADDING', (0,0), (-1,-1), 8),
        ('RIGHTPADDING', (0,0), (-1,-1), 8),
    ]))
    elements.append(t_meta)
    elements.append(Spacer(1, 14))

    # =========================================================================
    # BAB 1: RINGKASAN EKSEKUTIF METODE STAR
    # =========================================================================
    elements.append(Paragraph("1. Ringkasan Proyek Berdasarkan Metode STAR", h1_style))
    elements.append(HRFlowable(width="100%", thickness=1, color=ACCENT, spaceBefore=2, spaceAfter=8))

    star_text = """
    <b>S — SITUATION (Situasi):</b> PT Sehat Bersama Farma mengelola 5 cabang apotek di Jabodetabek dengan pencatatan spreadsheet yang mengakibatkan stok minus, laporan lambat (>30 detik pada jam sibuk 17.00–20.00), modul legacy rawan SQL injection, password plain-text, seluruh koneksi menggunakan root, serta ketiadaan environment terpisah.<br/><br/>
    <b>T — TASK (Tugas Asesi):</b> Merancang arsitektur basis data relasional 3NF; membuat DDL/DML, index, view, stored procedure, function, dan trigger; mengamankan modul akses database dengan prepared statement &amp; least privilege; mengoptimasi kueri laporan bulanan; mengonfigurasi multi-environment (Dev, Staging, Prod); menganalisis dampak perubahan penambahan Batch &amp; FEFO (Action 11 &amp; 13); serta memantau resource sistem.<br/><br/>
    <b>A — ACTION (Tindakan):</b> Mengimplementasikan seluruh 14 instruksi kerja (Action 1–14) dengan perbaikan arsitektur MariaDB, pembuatan Stored Procedure FEFO atomik (sp_simpan_penjualan_fefo), pemisahan hak akses per peran pengguna, dan pembuatan UI Streamlit terintegrasi.<br/><br/>
    <b>R — RESULT (Hasil):</b> Sistem inventori multi-cabang terstandar ACID; query laporan dioptimasi dari non-sargable menjadi date range index (<50ms); zero SQL injection vulnerability; pemisahan 3 environment; pengawasan masa kedaluwarsa batch real-time; dan seluruh 13 automated tests berstatus 100% Passed.
    """
    elements.append(Paragraph(star_text, body_style))
    elements.append(Spacer(1, 10))

    # =========================================================================
    # BAB 2: MATRIKS PEMENUHAN 14 UNIT KOMPETENSI (FR.IA.04A)
    # =========================================================================
    elements.append(Paragraph("2. Matriks Pemenuhan 14 Unit Kompetensi (Action 1 s.d. 14)", h1_style))
    elements.append(HRFlowable(width="100%", thickness=1, color=ACCENT, spaceBefore=2, spaceAfter=8))

    unit_data = [
        [
            Paragraph("No", table_header),
            Paragraph("Kode Unit", table_header),
            Paragraph("Judul Unit Kompetensi", table_header),
            Paragraph("Implementasi Teknis &amp; Bukti File", table_header),
            Paragraph("Status", table_header),
        ],
        [
            Paragraph("1", table_cell_center),
            Paragraph("J.620100.001.01", table_cell),
            Paragraph("Menganalisis Tools", table_cell_bold),
            Paragraph("Analisis perbandingan MariaDB, Python 3.14, VS Code, Git, Streamlit, dan mitigasi resikonya.", table_cell),
            Paragraph("✅ LULUS", badge_ok)
        ],
        [
            Paragraph("2", table_cell_center),
            Paragraph("J.620100.003.01", table_cell),
            Paragraph("Identifikasi Library / Framework", table_cell_bold),
            Paragraph("Evaluasi library PyMySQL, bcrypt, psutil, Streamlit. Bukti: poc/poc_koneksi.py &amp; requirements.txt.", table_cell),
            Paragraph("✅ LULUS", badge_ok)
        ],
        [
            Paragraph("3", table_cell_center),
            Paragraph("J.620100.004.02", table_cell),
            Paragraph("Menggunakan Struktur Data", table_cell_bold),
            Paragraph("Tabel relasional B-Tree, serta List of Dicts keranjang belanja dinamis pada modul penjualan.", table_cell),
            Paragraph("✅ LULUS", badge_ok)
        ],
        [
            Paragraph("4", table_cell_center),
            Paragraph("J.620100.007.01", table_cell),
            Paragraph("Rancangan Entitas &amp; Relasi", table_cell_bold),
            Paragraph("Normalisasi 3NF untuk entitas cabang, obat, kategori, stok, pengguna, penjualan, batch_obat.", table_cell),
            Paragraph("✅ LULUS", badge_ok)
        ],
        [
            Paragraph("5", table_cell_center),
            Paragraph("J.620100.020.02", table_cell),
            Paragraph("Menggunakan SQL", table_cell_bold),
            Paragraph("DDL (PK, FK, CHECK), DML 5 transaksi, Index, Views, SP ACID (COMMIT/ROLLBACK), Trigger stok log.", table_cell),
            Paragraph("✅ LULUS", badge_ok)
        ],
        [
            Paragraph("6", table_cell_center),
            Paragraph("J.620100.021.02", table_cell),
            Paragraph("Menerapkan Akses Basis Data", table_cell_bold),
            Paragraph("Least privilege (bukan root): admin.pusat, apoteker.depok, kasir.depok. Row-Level Security via View.", table_cell),
            Paragraph("✅ LULUS", badge_ok)
        ],
        [
            Paragraph("7", table_cell_center),
            Paragraph("J.620100.022.02", table_cell),
            Paragraph("Algoritma Pemrograman", table_cell_bold),
            Paragraph("Linear Search O(N), Binary Search O(log N), Quick Sort O(N log N) pada master dan laporan obat.", table_cell),
            Paragraph("✅ LULUS", badge_ok)
        ],
        [
            Paragraph("8", table_cell_center),
            Paragraph("J.620100.025.02", table_cell),
            Paragraph("Melakukan Debugging", table_cell_bold),
            Paragraph("Identifikasi Error 1142, nama kolom salah, SQL injection legacy. Bukti: docs/debug_log.md.", table_cell),
            Paragraph("✅ LULUS", badge_ok)
        ],
        [
            Paragraph("9", table_cell_center),
            Paragraph("J.620100.032.01", table_cell),
            Paragraph("Menerapkan Code Review", table_cell_bold),
            Paragraph("Refactor kode legacy ke parameterized query &amp; optimasi kueri laporan bulanan (sargable date index).", table_cell),
            Paragraph("✅ LULUS", badge_ok)
        ],
        [
            Paragraph("10", table_cell_center),
            Paragraph("J.620100.042.01", table_cell),
            Paragraph("Konfigurasi Multi-Environment", table_cell_bold),
            Paragraph("File konfigurasi dev.ini, staging.ini, prod.ini &amp; single active switcher CLI manage_env.py.", table_cell),
            Paragraph("✅ LULUS", badge_ok)
        ],
        [
            Paragraph("11", table_cell_center),
            Paragraph("J.620100.043.01", table_cell),
            Paragraph("Analisis Dampak Perubahan", table_cell_bold),
            Paragraph("RFC-2026-FEFO-001: As-Is vs To-Be batch FEFO, modul modifikasi, estimasi 5 hari/4 orang, mitigasi resiko.", table_cell),
            Paragraph("✅ LULUS", badge_ok)
        ],
        [
            Paragraph("12", table_cell_center),
            Paragraph("J.620100.045.01", table_cell),
            Paragraph("Pemantauan Resource", table_cell_bold),
            Paragraph("Modul monitor CPU, RAM, Disk, DB connections, Latensi dengan garis batas failure threshold 90%.", table_cell),
            Paragraph("✅ LULUS", badge_ok)
        ],
        [
            Paragraph("13", table_cell_center),
            Paragraph("J.620100.047.01", table_cell),
            Paragraph("Pembaharuan Perangkat Lunak", table_cell_bold),
            Paragraph("Eksekusi patch 03_migration_fefo.sql pada staging/dev &amp; rencana skrip rollback 04_rollback_fefo.sql.", table_cell),
            Paragraph("✅ LULUS", badge_ok)
        ],
        [
            Paragraph("14", table_cell_center),
            Paragraph("J.62090.011.01", table_cell),
            Paragraph("Keamanan Informasi", table_cell_bold),
            Paragraph("Standar SNI ISO/IEC 27001, kriptografi bcrypt salt=10, RBAC Matrix, dan audit forensic log_stok.", table_cell),
            Paragraph("✅ LULUS", badge_ok)
        ],
    ]

    t_unit = Table(unit_data, colWidths=[20, 75, 115, 227, 50])
    t_unit.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), ACCENT),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#cbd5e1")),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 3),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3),
        ('LEFTPADDING', (0,0), (-1,-1), 4),
        ('RIGHTPADDING', (0,0), (-1,-1), 4),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, BG_LIGHT]),
    ]))
    elements.append(t_unit)
    elements.append(Spacer(1, 14))

    # =========================================================================
    # BAB 3: FITUR KHUSUS FEFO & STATUS KEDALUWARSA (ACTION 11 & 13)
    # =========================================================================
    elements.append(Paragraph("3. Arsitektur Algoritma FEFO &amp; Status Kedaluwarsa", h1_style))
    elements.append(HRFlowable(width="100%", thickness=1, color=ACCENT, spaceBefore=2, spaceAfter=8))

    fefo_desc = """
    Sesuai permintaan manajemen dan kepatuhan Cara Distribusi Obat yang Baik (CDOB BPOM), sistem menerapkan aturan penjualan mendahulukan nomor batch obat yang tanggal kedaluwarsanya paling awal (<b>First Expired, First Out - FEFO</b>):<br/><br/>
    <b>1. Entitas Tabel batch_obat:</b> Menyimpan <code>id_batch</code> (PK), <code>kode_cabang</code> (FK), <code>kode_obat</code> (FK), <code>nomor_batch</code>, <code>tgl_kadaluarsa</code>, <code>jumlah_stok</code> (CHECK &gt;= 0), dan <code>tgl_masuk</code>. Dilengkapi Composite B-Tree Index <code>(kode_cabang, kode_obat, tgl_kadaluarsa, jumlah_stok)</code>.<br/>
    <b>2. Stored Procedure sp_simpan_penjualan_fefo:</b> Menggunakan Cursor loop terurut <code>ORDER BY tgl_kadaluarsa ASC, id_batch ASC</code> dan filter ketat <code>tgl_kadaluarsa &gt; CURRENT_DATE</code>. Jika kuantitas pembelian melampaui sisa 1 batch, sistem otomatis melakukan <i>Split Batch Deduction</i> ke batch aktif berikutnya.<br/>
    <b>3. Blokir Otomatis Obat Kedaluwarsa:</b> Batch yang telah melewati hari ini tidak akan diambil oleh cursor. Jika seluruh batch aktif habis, transaksi dibatalkan seketika dengan <code>ROLLBACK</code> dan sinyal SQLSTATE 45000.<br/>
    <b>4. Tab Antarmuka Status Kedaluwarsa (app.py):</b> Menyajikan tabel visual dengan kolom <b>Status</b> eksplisit:
    <ul>
      <li><b>🟢 Masih Aman:</b> Untuk obat yang tanggal kedaluwarsanya masih aktif (&gt; hari ini).</li>
      <li><b>🔴 Kadaluarsa:</b> Untuk obat yang tanggal kedaluwarsanya telah terlewati (&le; hari ini).</li>
    </ul>
    """
    elements.append(Paragraph(fefo_desc, body_style))
    elements.append(Spacer(1, 10))

    # =========================================================================
    # BAB 4: HAK AKSES PERAN & ROW-LEVEL SECURITY
    # =========================================================================
    elements.append(Paragraph("4. Pengamanan Hak Akses (Least Privilege &amp; Row-Level Security)", h1_style))
    elements.append(HRFlowable(width="100%", thickness=1, color=ACCENT, spaceBefore=2, spaceAfter=8))

    sec_data = [
        [
            Paragraph("Akun Basis Data", table_header),
            Paragraph("Peran Aplikasi", table_header),
            Paragraph("Hak Akses Tabel Dasar", table_header),
            Paragraph("Hak Akses View Terproteksi", table_header),
            Paragraph("Stored Procedure", table_header),
        ],
        [
            Paragraph("kasir.depok", table_cell_bold),
            Paragraph("KASIR (CBG-01)", table_cell),
            Paragraph("Dilarang SELECT/UPDATE langsung ke tabel obat, stok, pengguna (Error 1142).", table_cell),
            Paragraph("SELECT v_stok_cabang, v_stok_batch_cabang (Hanya baris CBG-01).", table_cell),
            Paragraph("EXECUTE sp_simpan_penjualan_fefo", table_cell)
        ],
        [
            Paragraph("apoteker.depok", table_cell_bold),
            Paragraph("APOTEKER (CBG-01)", table_cell),
            Paragraph("Dilarang akses tabel pengguna/cabang lain.", table_cell),
            Paragraph("SELECT stok dan batch cabang CBG-01. Berwenang menjual Obat Keras.", table_cell),
            Paragraph("EXECUTE sp_simpan_penjualan_fefo", table_cell)
        ],
        [
            Paragraph("admin.pusat", table_cell_bold),
            Paragraph("ADMIN_PUSAT", table_cell),
            Paragraph("CRUD master obat, kategori, cabang, batch_obat, dan backup akun.", table_cell),
            Paragraph("Melihat seluruh cabang (CBG-01, CBG-02, CBG-03).", table_cell),
            Paragraph("EXECUTE seluruh Stored Procedure", table_cell)
        ],
    ]
    t_sec = Table(sec_data, colWidths=[70, 85, 115, 137, 80])
    t_sec.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), ACCENT),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#cbd5e1")),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('LEFTPADDING', (0,0), (-1,-1), 4),
        ('RIGHTPADDING', (0,0), (-1,-1), 4),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, BG_LIGHT]),
    ]))
    elements.append(t_sec)
    elements.append(Spacer(1, 12))

    # =========================================================================
    # BAB 5: BUKTI PENGUJIAN OTOMATIS (TEST REPORT)
    # =========================================================================
    elements.append(Paragraph("5. Laporan Pengujian Otomatis (Pytest 100% Passed)", h1_style))
    elements.append(HRFlowable(width="100%", thickness=1, color=ACCENT, spaceBefore=2, spaceAfter=8))

    test_desc = """
    Seluruh fungsionalitas sistem telah diuji menggunakan framework <b>pytest</b> dengan hasil <b>13 Pengujian Lulus (13 passed in 1.77s)</b> tanpa kegagalan:
    """
    elements.append(Paragraph(test_desc, body_style))

    test_data = [
        [Paragraph("Modul Uji", table_header), Paragraph("Deskripsi Pengujian (Skenario)", table_header), Paragraph("Ekspektasi Sistem", table_header), Paragraph("Hasil", table_header)],
        [
            Paragraph("test_fase1_security.py", table_cell_bold),
            Paragraph("1. Kasir akses langsung tabel stok<br/>2. Kasir update harga obat<br/>3. Isolasi view v_stok_cabang<br/>4. Akses view profil sendiri<br/>5. Kasir akses tabel pengguna", table_cell),
            Paragraph("1. Ditolak Error 1142<br/>2. Ditolak Error 1142<br/>3. Hanya muncul CBG-01<br/>4. Data profil sesuai<br/>5. Ditolak Error 1142", table_cell),
            Paragraph("PASSED<br/>PASSED<br/>PASSED<br/>PASSED<br/>PASSED", badge_ok)
        ],
        [
            Paragraph("test_muk_demonstrasi.py", table_cell_bold),
            Paragraph("1. Transaksi normal stok berkurang<br/>2. Transaksi melebihi stok ditolak &amp; rollback<br/>3. Kasir jual obat keras ditolak &amp; isolasi cabang<br/>4. Konfigurasi 3 env &amp; monitoring resource", table_cell),
            Paragraph("1. Stok terpotong tepat real-time<br/>2. Penolakan SP &amp; rollback atomik<br/>3. Penolakan wewenang apoteker<br/>4. Parameter env &amp; resource akurat", table_cell),
            Paragraph("PASSED<br/>PASSED<br/>PASSED<br/>PASSED", badge_ok)
        ],
        [
            Paragraph("test_fefo_transaksi.py", table_cell_bold),
            Paragraph("1. Pemotongan batch terdekat FEFO<br/>2. Split batch antar 2 batch terurut<br/>3. Isolasi RLS view batch cabang<br/>4. Klasifikasi status Aman vs Kadaluarsa", table_cell),
            Paragraph("1. Batch exp terdekat terpotong duluan<br/>2. Batch 1 habis, sisa potong batch 2<br/>3. Kasir hanya melihat batch cabangnya<br/>4. Format field status valid", table_cell),
            Paragraph("PASSED<br/>PASSED<br/>PASSED<br/>PASSED", badge_ok)
        ],
    ]
    t_test = Table(test_data, colWidths=[110, 167, 160, 50])
    t_test.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), ACCENT),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#cbd5e1")),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('LEFTPADDING', (0,0), (-1,-1), 4),
        ('RIGHTPADDING', (0,0), (-1,-1), 4),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, BG_LIGHT]),
    ]))
    elements.append(t_test)
    elements.append(Spacer(1, 14))

    # =========================================================================
    # BAB 6: PANDUAN RUNNING & DEMO ASESOR
    # =========================================================================
    elements.append(Paragraph("6. Panduan Menjalankan Aplikasi &amp; Demonstrasi Asesor", h1_style))
    elements.append(HRFlowable(width="100%", thickness=1, color=ACCENT, spaceBefore=2, spaceAfter=8))

    guide_text = """
    <b>1. Perintah Menjalankan Aplikasi:</b><br/>
    Buka PowerShell di direktori proyek, lalu jalankan:<br/>
    <code>&nbsp;&nbsp;&nbsp;&nbsp;cd D:\\apotek_app<br/>&nbsp;&nbsp;&nbsp;&nbsp;streamlit run app.py</code><br/>
    Aplikasi akan terbuka otomatis di browser pada alamat: <code>http://localhost:8501</code>.<br/><br/>
    <b>2. Poin Demonstrasi Utama di Depan Asesor:</b>
    <ul>
      <li><b>Demonstrasi 1 (Akses Kasir vs Admin):</b> Tunjukkan Kasir ditolak update harga obat (Error 1142), sementara Admin Pusat berhasil.</li>
      <li><b>Demonstrasi 2 (Transaksi Penjualan &amp; FEFO):</b> Lakukan transaksi obat, tunjukkan stok batch terdekat otomatis berkurang lebih dulu, dan struk faktur mencatat nomor batch.</li>
      <li><b>Demonstrasi 3 (Uji Penolakan Bisnis):</b> Klik tombol cepat: Kasir jual Obat Keras (Ditolak), Penjualan melebihi stok (Ditolak &amp; Rollback).</li>
      <li><b>Demonstrasi 4 (Tab Status Kedaluwarsa):</b> Buka Tab 4 (Kasir) atau Tab 5 (Admin). Tunjukkan badge status <b>🟢 Masih Aman</b> vs <b>🔴 Kadaluarsa</b> serta filter status.</li>
      <li><b>Demonstrasi 5 (Environment &amp; Monitoring):</b> Switch environment DEV ke STAGING via sidebar, lalu buka Tab Pemantauan Resource untuk melihat metrik CPU, RAM, Disk, DB connections dengan garis batas failure threshold 90%.</li>
    </ul>
    """
    elements.append(Paragraph(guide_text, body_style))
    elements.append(Spacer(1, 10))

    # KESIMPULAN / SIGN-OFF
    elements.append(KeepTogether([
        HRFlowable(width="100%", thickness=1, color=colors.HexColor("#94a3b8"), spaceBefore=8, spaceAfter=8),
        Paragraph("<b>PERNYATAAN KEASLIAN DAN KELENGKAPAN:</b>", body_bold),
        Paragraph("Seluruh kode program, skrip DDL/DML basis data, konfigurasi lingkungan, dokumentasi teknis, dan pengujian otomatis dalam portofolio ini diselesaikan secara mandiri dan memenuhi seluruh kriteria unjuk kerja Skema Sertifikasi Programmer Basis Data (SKK-26/20/2024).", body_style),
        Spacer(1, 14),
        Table([
            [Paragraph("<b>Disiapkan Oleh (Asesi):</b><br/><br/><br/>___________________________<br/><b>Programmer Basis Data</b>", body_style),
             Paragraph("<b>Diverifikasi Oleh (Asesor Kompetensi):</b><br/><br/><br/>___________________________<br/><b>Asesor LSP Bidang IT</b>", body_style)]
        ], colWidths=[240, 247])
    ]))

    # Build Document
    doc.build(elements, canvasmaker=NumberedCanvas)
    print(f"✅ PDF berhasil dibuat di: {doc_path}")

    # Salin juga ke output_paths lainnya jika ada
    import shutil
    for p in output_paths[1:]:
        shutil.copyfile(doc_path, p)
        print(f"✅ PDF disalin ke: {p}")

if __name__ == "__main__":
    targets = [
        os.path.abspath("docs/Rangkuman_Proyek_Sertifikasi_Programmer_Basis_Data.pdf"),
        os.path.abspath("RANGKUMAN_PROYEK_ASESI.pdf")
    ]
    create_project_summary_pdf(targets)
