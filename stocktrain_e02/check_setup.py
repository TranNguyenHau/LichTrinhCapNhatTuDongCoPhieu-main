"""Confirm actual PostgreSQL schema / local stock history without writing anything."""
from __future__ import annotations
from .config import connection, SYMBOLS, MODEL_TO_ENUM
from .model_service import manifest_info

def main():
    manifest, digest = manifest_info()
    print('OK bundle:', manifest['experiment_id'], digest[:16])
    conn = connection()
    try:
        with conn.cursor() as cur:
            for table in ['co_phieu','gia_co_phieu','chi_bao_ky_thuat',
                          'mo_hinh_ml','du_doan','stocktrain_prediction_meta']:
                cur.execute('SELECT to_regclass(%s)',('public.'+table,))
                if cur.fetchone()[0] is None:
                    raise RuntimeError('Thiếu bảng '+table+'; chạy migrate.py cho bảng metadata')
            for enum in ['loai_mo_hinh_enum','loai_chu_ky_enum','xu_huong_enum','muc_rui_ro_enum']:
                cur.execute('SELECT enumlabel FROM pg_enum WHERE enumtypid=%s::regtype', (enum,))
                print(enum, [r[0] for r in cur.fetchall()])
            cur.execute('SELECT enumlabel FROM pg_enum WHERE enumtypid=%s::regtype', ('loai_mo_hinh_enum',))
            present = {r[0] for r in cur.fetchall()}
            if not set(MODEL_TO_ENUM.values()).issubset(present):
                raise RuntimeError('Enum model trong DB không đủ tên cho bundle: ' + str(set(MODEL_TO_ENUM.values())-present))
            cur.execute('''SELECT c.ky_hieu, COUNT(g.ma_gia),MAX(g.ngay_giao_dich)
                           FROM co_phieu c LEFT JOIN gia_co_phieu g ON c.ma_co_phieu=g.ma_co_phieu
                           WHERE c.ky_hieu=ANY(%s) AND c.dang_hoat_dong=TRUE
                           GROUP BY c.ky_hieu ORDER BY c.ky_hieu''',(list(SYMBOLS),))
            vals=cur.fetchall()
            for r in vals:print('HISTORY:', *r)
            if {v[0] for v in vals} != set(SYMBOLS):
                raise RuntimeError('Chưa có đủ 5 mã trong bảng co_phieu')
        print('OK: schema và 5 mã kiểm tra được; chưa có kiểm thử inference thực')
    finally:
        conn.close()

if __name__=='__main__':
    main()
