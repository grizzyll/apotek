from datetime import datetime

def format_rupiah(nilai):
    """Memformat angka menjadi representasi Rupiah Indonesia, misal Rp 1.250.000"""
    try:
        val = float(nilai)
        return f"Rp {val:,.0f}".replace(",", ".")
    except (ValueError, TypeError):
        return str(nilai)

def format_tanggal(dt):
    """Memformat datetime objek atau string menjadi format tanggal Indonesia"""
    if not dt:
        return "-"
    if isinstance(dt, str):
        try:
            dt = datetime.strptime(dt[:19], "%Y-%m-%d %H:%M:%S")
        except Exception:
            return dt
    
    bulan = [
        "", "Jan", "Feb", "Mar", "Apr", "Mei", "Jun",
        "Jul", "Agu", "Sep", "Okt", "Nov", "Des"
    ]
    try:
        return f"{dt.day:02d} {bulan[dt.month]} {dt.year} {dt.hour:02d}:{dt.minute:02d}"
    except Exception:
        return str(dt)
