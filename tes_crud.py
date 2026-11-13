import sys
from src.koneksi import get_connection
from src.obat_dao import ObatDAO

print("="*50)
print("PENGUJIAN ACTION 6: CRUD & KEAMANAN AKSES PER PERAN")
print("="*50)

# 1. Login sebagai Kasir (Hanya boleh baca/jual, TIDAK BOLEH ubah master obat)
print("\n[UJI 1] Kasir mencoba mengubah harga obat master:")
try:
    conn_kasir = get_connection("kasir.depok", "KasirDpk#2026", env="dev")
    dao_kasir = ObatDAO(conn_kasir)
    dao_kasir.update_harga("OBT-001", 999999)
    print("-> BAHAYA: Kasir berhasil ubah data! (Hak akses belum aman)")
    conn_kasir.close()
except Exception as e:
    print(f"-> [SUKSES TERPROTEKSI] Aksi Kasir DITOLAK database:\n   {e}")

# 2. Login sebagai Admin Pusat (Harus memiliki izin penuh untuk CRUD obat)
admin_user = sys.argv[1] if len(sys.argv) > 1 else "admin.pusat"
admin_pwd = sys.argv[2] if len(sys.argv) > 2 else "AdminPst#2026"

print(f"\n[UJI 2] Admin Pusat ({admin_user}) melakukan operasi CRUD:")
try:
    conn_admin = get_connection(admin_user, admin_pwd, env="dev")
    dao_admin = ObatDAO(conn_admin)
    
    # READ
    daftar = dao_admin.ambil_semua()
    print(f"-> [READ] Berhasil membaca {len(daftar)} data obat dari database.")
    if daftar:
        print(f"   Contoh obat pertama: {daftar[0]['kode_obat']} - {daftar[0]['nama_obat']} (Rp {int(daftar[0]['harga_jual']):,})")
    
    conn_admin.close()
except Exception as e:
    print(f"-> [GAGAL ADMIN] Error: {e}")
