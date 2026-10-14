"""Read-only Flask API. Can be registered as a Blueprint in friend's Flask app."""
from __future__ import annotations
import json
from flask import Flask, Blueprint, jsonify, request
from flask_cors import CORS
from .config import BUNDLE_ROOT, connection, SYMBOLS, MODEL_NAMES
from .model_service import manifest_info
from .repository import json_safe

stocktrain_bp = Blueprint('stocktrain_api', __name__, url_prefix='/api')

@stocktrain_bp.get('/health')
def health():
    try:
        manifest, digest = manifest_info()
        conn = connection()
        try:
            with conn.cursor() as cur:
                cur.execute('SELECT 1')
        finally:
            conn.close()
        return jsonify({'status':'ok','database':'ok','bundle':'ok',
                        'experiment_id':manifest['experiment_id'], 'horizon':manifest['horizon'],
                        'bundle_sha256':digest})
    except Exception:
        return jsonify({'status':'unavailable','database_or_bundle':'check_server_logs'}), 503

@stocktrain_bp.get('/stocks')
def stocks():
    conn = connection()
    try:
        with conn.cursor() as cur:
            cur.execute('''SELECT ky_hieu, ten_cong_ty FROM co_phieu
                           WHERE dang_hoat_dong=TRUE AND ky_hieu=ANY(%s) ORDER BY ky_hieu''', (list(SYMBOLS),))
            vals = cur.fetchall()
        return jsonify({'stocks':[{'symbol':sym,'company':company} for sym,company in vals]})
    finally:
        conn.close()

@stocktrain_bp.get('/prices')
def prices():
    symbol = request.args.get('symbol', '').upper().strip()
    if symbol not in SYMBOLS:
        return jsonify({'error': 'symbol phải thuộc FPT, HPG, VCB, VNM, SSI'}), 400
    try:
        limit = max(1, min(1500, int(request.args.get('limit', '120'))))
    except ValueError:
        return jsonify({'error': 'limit phải là số nguyên'}), 400
    conn = connection()
    try:
        with conn.cursor() as cur:
            cur.execute('''SELECT g.ngay_giao_dich, g.gia_mo_cua, g.gia_cao_nhat,
                                  g.gia_thap_nhat, g.gia_dong_cua, g.khoi_luong
                           FROM gia_co_phieu g
                           JOIN co_phieu c ON c.ma_co_phieu=g.ma_co_phieu
                           WHERE c.ky_hieu=%s AND c.dang_hoat_dong=TRUE
                           ORDER BY g.ngay_giao_dich DESC LIMIT %s''', (symbol, limit))
            rows = list(reversed(cur.fetchall()))
        values = [dict(date=str(r[0]), open=float(r[1]), high=float(r[2]),
                       low=float(r[3]), close=float(r[4]), volume=int(r[5])) for r in rows]
        return jsonify({'symbol': symbol, 'count': len(values), 'prices': values})
    finally:
        conn.close()

@stocktrain_bp.get('/models')
def models():
    manifest, digest = manifest_info()
    return jsonify({'experiment_id':manifest['experiment_id'], 'models':MODEL_NAMES,
                    'symbols':manifest['symbols'],'horizon':manifest['horizon'],
                    'bundle_hash':digest, 'reliability_notice':manifest.get('reliability_notice')})


def _param_filters():
    symbol = request.args.get('symbol', '').upper().strip()
    model = request.args.get('model','').strip()
    if symbol and symbol not in SYMBOLS:
        return None,None,('Mã không hợp lệ',400)
    if model and model not in MODEL_NAMES:
        return None,None,('Model không hợp lệ',400)
    return symbol, model, None

_BASE_QUERY = '''SELECT c.ky_hieu, m2.model_name, d.ngay_du_doan,
        d.ngay_muc_tieu,d.loi_nhuan_du_doan,d.xu_huong_du_doan::text,
        d.muc_rui_ro::text, m2.trained_until, m2.warnings, m2.descriptive_risk,
        m2.target_date_estimated, m2.experiment_id, m2.bundle_sha256
    FROM du_doan d JOIN co_phieu c ON c.ma_co_phieu=d.ma_co_phieu
    JOIN stocktrain_prediction_meta m2 ON m2.ma_du_doan=d.ma_du_doan
    WHERE c.ky_hieu=ANY(%s) AND (%s='' OR c.ky_hieu=%s)
        AND (%s='' OR m2.model_name=%s)'''

def _to_output(row):
    row = json_safe(row)
    return dict(symbol=row[0], model=row[1], as_of=row[2], target_date=row[3],
                target_date_estimated=row[10], predicted_return=row[4],
                predicted_return_percent=round(100*row[4],4), trend=row[5], risk_level=row[6],
                trained_until=row[7], warnings=row[8], descriptive_risk=row[9],
                experiment_id=row[11], bundle_sha256=row[12],
                risk_notice='Mức rủi ro chỉ dựa trên phân vị biến động lịch sử, không phải dự báo E10.',
                target_notice='Ngày mục tiêu chỉ ước lượng theo thứ Hai–thứ Sáu, chưa trừ ngày nghỉ sàn.')

@stocktrain_bp.get('/predictions/latest')
def latest():
    symbol, model, err = _param_filters()
    if err:
        return jsonify({'error':err[0]}), err[1]
    conn = connection()
    try:
        q = '''SELECT DISTINCT ON (c.ky_hieu, m2.model_name) c.ky_hieu,m2.model_name,
               d.ngay_du_doan,d.ngay_muc_tieu,d.loi_nhuan_du_doan,d.xu_huong_du_doan::text,
               d.muc_rui_ro::text,m2.trained_until,m2.warnings,m2.descriptive_risk,
               m2.target_date_estimated,m2.experiment_id,m2.bundle_sha256
               FROM du_doan d JOIN co_phieu c ON c.ma_co_phieu=d.ma_co_phieu
               JOIN stocktrain_prediction_meta m2 ON m2.ma_du_doan=d.ma_du_doan
               WHERE c.ky_hieu=ANY(%s) AND (%s='' OR c.ky_hieu=%s)
                     AND (%s='' OR m2.model_name=%s)
               ORDER BY c.ky_hieu,m2.model_name,d.ngay_du_doan DESC,d.ma_du_doan DESC'''
        with conn.cursor() as cur:
            cur.execute(q,(list(SYMBOLS),symbol,symbol,model,model))
            rows=cur.fetchall()
        return jsonify({'count':len(rows),'predictions':[_to_output(x) for x in rows]})
    finally:
        conn.close()

@stocktrain_bp.get('/predictions/history')
def history():
    symbol, model, err = _param_filters()
    if err:
        return jsonify({'error':err[0]}), err[1]
    try:
        limit = max(1,min(500,int(request.args.get('limit','50'))))
    except ValueError:
        return jsonify({'error':'limit phải là số nguyên'}),400
    conn=connection()
    try:
        with conn.cursor() as cur:
            cur.execute(_BASE_QUERY+' ORDER BY d.ngay_du_doan DESC, d.ma_du_doan DESC LIMIT %s',
                        (list(SYMBOLS),symbol,symbol,model,model,limit))
            vals=cur.fetchall()
        return jsonify({'count':len(vals),'predictions':[_to_output(x) for x in vals]})
    finally:
        conn.close()


def create_app():
    import os
    app=Flask(__name__)
    app.register_blueprint(stocktrain_bp)
    origins=[o.strip() for o in os.getenv('ALLOWED_ORIGINS','http://localhost:3000,http://localhost:5173').split(',') if o.strip()]
    CORS(app, resources={r'/api/*': {'origins':origins}})
    return app

app = create_app()

if __name__=='__main__':
    import os
    app.run(host=os.getenv('API_HOST','127.0.0.1'),port=int(os.getenv('API_PORT','5001')),debug=False)
