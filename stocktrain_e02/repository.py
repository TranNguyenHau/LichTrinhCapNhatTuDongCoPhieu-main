"""PostgreSQL persistence using the original Vietnamese schema; additive metadata table."""
from __future__ import annotations
import json
import hashlib
from datetime import date
from decimal import Decimal
import pandas as pd
from psycopg2.extras import Json
from .config import BUNDLE_ROOT, MODEL_TO_ENUM, HORIZON


def target_day_estimate(as_of, sessions=HORIZON):
    # Holiday-unaware estimate: exchange calendar required for exact H5 maturity.
    return (pd.Timestamp(as_of) + pd.offsets.BDay(sessions)).date()


def save_one(cur, item):
    enum_name = MODEL_TO_ENUM[item['model']]
    rel = item['model_relative_path']
    file_name = item['config']['model_file']
    path = str((BUNDLE_ROOT / rel / file_name).resolve())
    _, sha = (item['experiment_id'], item['bundle_hash'])
    # Serialize writers for this symbol+model and avoid duplicate model registrations.
    key = f"stocktrain:model:{item['symbol']}:{item['model']}:{sha}"
    cur.execute('SELECT pg_advisory_xact_lock(hashtext(%s))', (key,))
    cur.execute('''SELECT ma_mo_hinh FROM mo_hinh_ml
                   WHERE ma_co_phieu=%s AND loai_mo_hinh=%s::loai_mo_hinh_enum
                     AND so_ngay_du_bao=%s AND duong_dan_mo_hinh=%s
                     AND sieu_tham_so->>'bundle_sha256'=%s
                   ORDER BY ma_mo_hinh DESC LIMIT 1''',
                (item['symbol_id'], enum_name, HORIZON, path, sha))
    row = cur.fetchone()
    if row:
        model_id = int(row[0])
    else:
        cur.execute('''INSERT INTO mo_hinh_ml
                       (ma_co_phieu, loai_mo_hinh, so_ngay_du_bao, hat_giong,
                        sieu_tham_so, danh_sach_dac_trung, ngay_ket_thuc_train,
                        duong_dan_mo_hinh, la_mo_hinh_tot_nhat)
                       VALUES (%s,%s::loai_mo_hinh_enum,%s,%s,%s,%s,%s,%s,FALSE)
                       RETURNING ma_mo_hinh''',
                    (item['symbol_id'], enum_name, HORIZON, int(item['config']['seed']),
                     Json({'bundle_sha256':sha, 'experiment_id':item['experiment_id'],
                           'model_name':item['model'], 'source':'stocktrain_e02_export'}),
                     Json(item['features']), item['trained_until'], path))
        model_id = int(cur.fetchone()[0])
    prediction_key = f"stocktrain:prediction:{model_id}:{item['as_of']}:{HORIZON}"
    cur.execute('SELECT pg_advisory_xact_lock(hashtext(%s))', (prediction_key,))
    cur.execute('''SELECT d.ma_du_doan, m.source_sha256
                   FROM du_doan d LEFT JOIN stocktrain_prediction_meta m
                     ON d.ma_du_doan=m.ma_du_doan
                   WHERE d.ma_mo_hinh=%s AND d.ma_co_phieu=%s
                     AND d.ngay_du_doan=%s AND d.so_ngay_du_bao=%s
                   ORDER BY d.ma_du_doan DESC LIMIT 1 FOR UPDATE OF d''',
                (model_id,item['symbol_id'],item['as_of'],HORIZON))
    row = cur.fetchone()
    if row:
        prediction_id, old_sig = row
        if old_sig is None:
            raise RuntimeError('Đã có dự báo không có metadata cho cùng model/ngày, từ chối ghi đè')
        if old_sig != item['source_hash']:
            raise RuntimeError('Dữ liệu lịch sử đã thay đổi cho ngày dự báo cũ; từ chối thay thế dự báo đã công bố')
        return int(prediction_id), 'unchanged'
    trend = {'UP':'UP','DOWN':'DOWN','HOLD':'SIDEWAYS'}[item['trend']]
    target = target_day_estimate(item['as_of'])
    cur.execute('''INSERT INTO du_doan (ma_mo_hinh,ma_co_phieu,ngay_du_doan,loai_chu_ky,
                       so_ngay_du_bao,ngay_muc_tieu,loi_nhuan_du_doan,xu_huong_du_doan,muc_rui_ro)
                   VALUES (%s,%s,%s,'SHORT_TERM'::loai_chu_ky_enum,%s,%s,%s,
                           %s::xu_huong_enum,%s::muc_rui_ro_enum) RETURNING ma_du_doan''',
                (model_id,item['symbol_id'],item['as_of'],HORIZON,target,
                 item['predicted_return'],trend,item['risk_level']))
    prediction_id = int(cur.fetchone()[0])
    cur.execute('''INSERT INTO stocktrain_prediction_meta
                   (ma_du_doan,source_sha256,bundle_sha256,experiment_id,model_name,
                    trained_until,warnings,descriptive_risk,target_date_estimated)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,TRUE)''',
                (prediction_id,item['source_hash'],sha,item['experiment_id'],item['model'],
                 item['trained_until'],Json(item['warnings']),Json(item['risk'])))
    return prediction_id, 'inserted'


def persist_batch(conn, items):
    """One transaction for all models of a symbol; no partial symbol outputs."""
    count = {'inserted': 0, 'unchanged': 0}
    try:
        with conn.cursor() as cur:
            for item in items:
                _, status = save_one(cur, item)
                count[status] += 1
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return count


def json_safe(value):
    if isinstance(value, (date,)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (list, tuple)):
        return [json_safe(x) for x in value]
    if isinstance(value, dict):
        return {k: json_safe(x) for k,x in value.items()}
    return value
