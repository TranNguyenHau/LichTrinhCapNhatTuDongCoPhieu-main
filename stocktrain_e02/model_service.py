"""Load the supplied, trusted bundle (no retraining or alterations to model files)."""
from __future__ import annotations
import hashlib
import json
import math
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import numpy as np
import pandas as pd
from .config import BUNDLE_ROOT, HISTORY_ROWS, HORIZON, MIN_HISTORY_ROWS, MAX_PRICE_AGE_BDAYS, SYMBOLS, MODEL_NAMES


def manifest_info():
    mp = BUNDLE_ROOT / 'manifest.json'
    if not mp.is_file():
        raise FileNotFoundError(f'Thiếu manifest bundle: {mp}')
    data = json.loads(mp.read_text(encoding='utf-8'))
    if data.get('experiment_id') != 'E02_H5_F1_T0_S0_SEED42' or data.get('horizon') != HORIZON:
        raise RuntimeError('Bundle không phải E02/H5 đúng cấu hình, dừng trước khi dự báo')
    if set(data.get('symbols', [])) != set(SYMBOLS) or set(data.get('models', [])) != set(MODEL_NAMES):
        raise RuntimeError('Manifest khác 5 mã/5 model đã bàn giao')
    # Include model and scaler bytes, not only manifest; avoid treating an overwritten
    # artifact folder as the same deployment version.
    h = hashlib.sha256()
    for rel in ['manifest.json', 'predict_bundle.py', 'roundtrip_test.csv']:
        q = BUNDLE_ROOT / rel
        h.update(rel.encode('utf-8') + b'\0')
        h.update(q.read_bytes())
    for artifact in sorted(data['artifacts'], key=lambda x: (x['symbol'], x['model_name'])):
        directory = BUNDLE_ROOT / artifact['path']
        config = json.loads((directory/'config.json').read_text(encoding='utf-8'))
        for leaf in ['config.json', 'features.json', 'metrics.json',
                     'scaler_X.joblib', 'scaler_y.joblib', config['model_file']]:
            q = directory / leaf
            h.update((artifact['path']+'/'+leaf).encode('utf-8') + b'\0')
            h.update(q.read_bytes())
    fingerprint = h.hexdigest()
    return data, fingerprint


def read_price_history(conn, symbol):
    if symbol not in SYMBOLS:
        raise ValueError('Mã không được hỗ trợ: ' + symbol)
    with conn.cursor() as cur:
        cur.execute('SELECT ma_co_phieu FROM co_phieu WHERE ky_hieu=%s AND dang_hoat_dong=TRUE', (symbol,))
        row = cur.fetchone()
        if not row:
            raise RuntimeError(f'Mã {symbol} không có trong bảng co_phieu hoặc đã tắt')
        sid = int(row[0])
        cur.execute('''SELECT ngay_giao_dich, gia_mo_cua, gia_cao_nhat, gia_thap_nhat,
                              gia_dong_cua, khoi_luong FROM gia_co_phieu
                       WHERE ma_co_phieu=%s ORDER BY ngay_giao_dich DESC LIMIT %s''',
                    (sid, HISTORY_ROWS))
        rows = cur.fetchall()
    if len(rows) < MIN_HISTORY_ROWS:
        raise RuntimeError(f'{symbol}: chỉ có {len(rows)} phiên; yêu cầu ít nhất {MIN_HISTORY_ROWS}')
    rows = list(reversed(rows))
    frame = pd.DataFrame(rows, columns=['Date', 'Open', 'High', 'Low', 'Close', 'Volume'])
    frame['Date'] = pd.to_datetime(frame['Date'])
    frame = frame.set_index('Date')
    for col in ['Open','High','Low','Close','Volume']:
        frame[col] = pd.to_numeric(frame[col], errors='coerce')
    if frame.isna().any().any() or not np.isfinite(frame.to_numpy(dtype=float)).all():
        raise RuntimeError(f'{symbol}: dữ liệu OHLCV có NaN hoặc inf, ngừng suy luận')
    if (frame[['Open','High','Low','Close']] <= 0).any().any() or (frame['Volume'] < 0).any():
        raise RuntimeError(f'{symbol}: giá không dương hoặc khối lượng âm')
    if (frame['High'] < frame[['Open', 'Close', 'Low']].max(axis=1)).any() or (frame['Low'] > frame[['Open', 'Close', 'High']].min(axis=1)).any():
        raise RuntimeError(f'{symbol}: dữ liệu OHLC bất hợp lệ')
    last = frame.index[-1].date()
    today = datetime.now(ZoneInfo('Asia/Ho_Chi_Minh')).date()
    if last > today:
        raise RuntimeError(f'{symbol}: ngày dữ liệu {last} trong tương lai')
    age = int(np.busday_count(np.datetime64(last), np.datetime64(today)))
    if age > MAX_PRICE_AGE_BDAYS:
        raise RuntimeError(f'{symbol}: dữ liệu quá cũ {age} ngày làm việc (giới hạn {MAX_PRICE_AGE_BDAYS})')
    return sid, frame


def _source_signature(frame):
    """Digest historical prices actually passed to inference (revision-sensitive)."""
    h = hashlib.sha256()
    h.update(pd.util.hash_pandas_object(frame, index=True).values.tobytes())
    h.update('|'.join(map(str, frame.columns)).encode('utf-8'))
    return h.hexdigest()


def run_symbol(conn, symbol, models):
    manifest, bundle_hash = manifest_info()
    sid, frame = read_price_history(conn, symbol)
    source_hash = _source_signature(frame)
    if str(BUNDLE_ROOT) not in sys.path:
        sys.path.insert(0, str(BUNDLE_ROOT))
    from predict_bundle import predict  # original unchanged exported helper
    date_str = frame.index[-1].date().isoformat()
    results = []
    for model_name in models:
        model = next((m for m in manifest['artifacts'] if m['symbol']==symbol and m['model_name']==model_name), None)
        if not model:
            raise RuntimeError(f'{symbol}/{model_name}: thiếu artifact trong manifest')
        rel_dir = Path(model['path'])
        if rel_dir.is_absolute() or '..' in rel_dir.parts:
            raise RuntimeError('Đường dẫn artifact không hợp lệ')
        model_dir = BUNDLE_ROOT / rel_dir
        config = json.loads((model_dir / 'config.json').read_text(encoding='utf-8'))
        if config.get('experiment_id') != manifest['experiment_id'] or config.get('target_mode') != 'T0_raw_return' or int(config.get('horizon',0)) != HORIZON:
            raise RuntimeError(f'{symbol}/{model_name}: config artifact không phải T0/H5 E02')
        prediction = predict(symbol, model_name, frame)
        val = prediction.get('predicted_return')
        if val is None or not math.isfinite(float(val)):
            raise RuntimeError(f'{symbol}/{model_name}: dự báo không hợp lệ: {prediction.get("warnings")}')
        if abs(float(val)) >= 1:
            raise RuntimeError(f'{symbol}/{model_name}: lợi nhuận dự báo có độ lớn >=100%; cần kiểm tra nguồn giá')
        percentile = prediction.get('risk',{}).get('historical_percentile')
        if percentile is None or not math.isfinite(float(percentile)):
            raise RuntimeError(f'{symbol}/{model_name}: chưa đủ dữ liệu phân vị biến động')
        risk_level = 'LOW' if percentile < 100/3 else 'HIGH' if percentile >= 200/3 else 'MEDIUM'
        results.append(dict(symbol=symbol, symbol_id=sid, as_of=date_str, model=model_name,
                            model_relative_path=rel_dir.as_posix(), config=config,
                            features=json.loads((model_dir/'features.json').read_text(encoding='utf-8'))['features'],
                            experiment_id=manifest['experiment_id'], bundle_hash=bundle_hash,
                            source_hash=source_hash, predicted_return=float(val),
                            trend=prediction['trend'], risk_level=risk_level, risk=prediction['risk'],
                            trained_until=config.get('trained_until'), warnings=prediction.get('warnings',[])))
    return results
