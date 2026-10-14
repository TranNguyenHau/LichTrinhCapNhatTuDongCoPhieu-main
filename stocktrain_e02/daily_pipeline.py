"""Task Scheduler entrypoint: fetch -> verify -> predict -> store; no training."""
from __future__ import annotations
import logging
import sys
from datetime import datetime
from pathlib import Path
from .config import connection, ENABLE_MODELS, SYMBOLS
from .model_service import run_symbol, manifest_info
from .repository import persist_batch

LOG_DIR = Path(__file__).resolve().parent / 'logs'
LOG_DIR.mkdir(exist_ok=True)
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s',
    handlers=[logging.StreamHandler(), logging.FileHandler(LOG_DIR/f'daily_{datetime.now():%Y%m%d}.log', encoding='utf-8')])
log = logging.getLogger('stocktrain.daily')


def main():
    manifest, digest = manifest_info()
    log.info('Bundle %s hash %s, models: %s', manifest['experiment_id'], digest[:12], ENABLE_MODELS)
    # import fetch only here, to avoid requiring vnstock for API requests
    from .safe_fetch import main as fetch_main
    log.info('Bắt đầu cập nhật thị trường qua script đã có')
    fetch_main()  # Reuses legacy fetch functions; raises on any symbol failure.
    log.info('Cập nhật hoàn tất, bắt đầu dự báo từ PostgreSQL')
    conn = connection()
    failed = []
    try:
        for symbol in SYMBOLS:
            try:
                batch = run_symbol(conn, symbol, ENABLE_MODELS)
                counts = persist_batch(conn, batch)
                log.info('%s: %s; ngày %s', symbol, counts, batch[0]['as_of'])
            except Exception as exc:
                conn.rollback()
                failed.append(symbol)
                log.exception('Dừng dự báo mã %s: %s', symbol, exc)
    finally:
        conn.close()
    if failed:
        raise RuntimeError('Có mã lỗi, job chưa hoàn thành: '+', '.join(failed))
    log.info('DỰ BÁO HOÀN THÀNH 5 MÃ; không train lại bất cứ model nào')

if __name__ == '__main__':
    try:
        main()
    except Exception:
        log.exception('DAILY PIPELINE FAILED')
        sys.exit(1)
