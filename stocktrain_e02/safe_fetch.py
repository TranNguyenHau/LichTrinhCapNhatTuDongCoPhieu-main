"""Safe adapter around the user's existing fetch_stock_data.py, with NO edits to it.

Legacy main() logs errors but does not raise; this adapter invokes its existing
functions and returns nonzero to Task Scheduler if any of the five symbols fails.
"""
from __future__ import annotations
import logging
from datetime import datetime, timedelta
from pathlib import Path
from .config import connection, SYMBOLS

log = logging.getLogger('stocktrain.safe_fetch')

def main():
    legacy_path = Path(__file__).resolve().parent.parent / 'fetch_stock_data.py'
    if not legacy_path.is_file():
        raise FileNotFoundError(f'Đặt thư mục stocktrain_e02 cạnh fetch_stock_data.py cũ: {legacy_path}')
    # Running python -m stocktrain_e02.daily_pipeline from app root makes legacy importable.
    from fetch_stock_data import (get_stocks, fetch_prices, upsert_prices,
                                  load_recent_prices, compute_indicators, upsert_indicators,
                                  LOOKBACK_DAYS_FOR_FETCH, LOOKBACK_DAYS_FOR_INDICATOR)
    end_date = datetime.now().strftime('%Y-%m-%d')
    start_date = (datetime.now() - timedelta(days=LOOKBACK_DAYS_FOR_FETCH)).strftime('%Y-%m-%d')
    conn = connection()  # .env credentials, not the hardcoded DB_CONFIG in the old file
    errors = []
    try:
        current = {str(s): int(k) for k,s in get_stocks(conn) if str(s) in SYMBOLS}
        missing = set(SYMBOLS)-set(current)
        if missing:
            raise RuntimeError('Thiếu mã hoạt động trong DB: '+', '.join(sorted(missing)))
        for sym in SYMBOLS:
            sid = current[sym]
            try:
                df_new = fetch_prices(sym, start_date, end_date)
                if df_new is None or df_new.empty:
                    raise RuntimeError('Nguồn giá trả về 0 dòng; không cập nhật và không dự báo')
                n_prices = upsert_prices(conn, sid, df_new)
                df_recent = load_recent_prices(conn, sid, LOOKBACK_DAYS_FOR_INDICATOR)
                indicators = compute_indicators(df_recent)
                n_ind = upsert_indicators(conn, sid, indicators,
                                         only_new_days=LOOKBACK_DAYS_FOR_FETCH+5)
                log.info('%s: %s phiên giá, %s phiên chỉ báo',sym,n_prices,n_ind)
            except Exception:
                conn.rollback()
                log.exception('Lỗi cập nhật mã %s',sym)
                errors.append(sym)
    finally:
        conn.close()
    if errors:
        raise RuntimeError('Cập nhật không hoàn tất; KHÔNG chạy dự báo: '+', '.join(errors))
    log.info('Cập nhật 5 mã thành công')
