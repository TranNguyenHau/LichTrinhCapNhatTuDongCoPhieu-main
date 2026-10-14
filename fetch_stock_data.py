"""
fetch_stock_data.py — Cập nhật dữ liệu giá + chỉ báo kỹ thuật cho CSDL klcn284.
Dùng tên bảng/cột theo CoPhieu_KLCN.sql.
Chạy độc lập (không phụ thuộc framework backend nào) — lên lịch chạy hàng ngày
bằng Windows Task Scheduler (xem hướng dẫn kèm theo).
"""
import logging
from datetime import datetime, timedelta

import pandas as pd
import psycopg2
from psycopg2.extras import execute_values
from vnstock import Quote
from ta.trend import SMAIndicator, EMAIndicator, MACD
from ta.momentum import RSIIndicator
from ta.volatility import BollingerBands, AverageTrueRange
from ta.volume import OnBalanceVolumeIndicator, MFIIndicator

# Repo công khai: nạp kết nối DB từ .env, không lưu mật khẩu trong source.
import os
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent / 'stocktrain_e02' / '.env')
DB_CONFIG = dict(
    host=os.getenv('DB_HOST', 'localhost'),
    port=int(os.getenv('DB_PORT', '5432')),
    dbname=os.getenv('DB_NAME', 'klcn284'),
    user=os.getenv('DB_USER', 'postgres'),
    password=os.getenv('DB_PASSWORD'),
)
LOOKBACK_DAYS_FOR_FETCH = 10        # lấy dư vài ngày để bắt kịp dữ liệu điều chỉnh
LOOKBACK_DAYS_FOR_INDICATOR = 120   # đủ để tính sma_50 chính xác cho các phiên mới

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler(f"fetch_log_{datetime.now():%Y%m%d_%H%M%S}.txt", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger(__name__)


def get_stocks(conn):
    with conn.cursor() as cur:
        cur.execute("SELECT ma_co_phieu, ky_hieu FROM co_phieu WHERE dang_hoat_dong = TRUE")
        return cur.fetchall()


def fetch_prices(symbol, start_date, end_date):
    quote = Quote(symbol=symbol, source="KBS")
    df = quote.history(start=start_date, end=end_date, interval="1D")
    return df.rename(columns={"time": "ngay_giao_dich"})


def upsert_prices(conn, ma_co_phieu, df):
    rows = [
        (ma_co_phieu, r.ngay_giao_dich, r.open, r.high, r.low, r.close, int(r.volume))
        for r in df.itertuples()
    ]
    with conn.cursor() as cur:
        execute_values(cur, """
            INSERT INTO gia_co_phieu
                (ma_co_phieu, ngay_giao_dich, gia_mo_cua, gia_cao_nhat, gia_thap_nhat,
                 gia_dong_cua, khoi_luong)
            VALUES %s
            ON CONFLICT (ma_co_phieu, ngay_giao_dich) DO UPDATE SET
                gia_mo_cua=EXCLUDED.gia_mo_cua, gia_cao_nhat=EXCLUDED.gia_cao_nhat,
                gia_thap_nhat=EXCLUDED.gia_thap_nhat, gia_dong_cua=EXCLUDED.gia_dong_cua,
                khoi_luong=EXCLUDED.khoi_luong
        """, rows)
    conn.commit()
    return len(rows)


def load_recent_prices(conn, ma_co_phieu, days):
    q = """
        SELECT ngay_giao_dich AS trade_date, gia_mo_cua AS open, gia_cao_nhat AS high,
               gia_thap_nhat AS low, gia_dong_cua AS close, khoi_luong AS volume
        FROM gia_co_phieu WHERE ma_co_phieu = %s
        ORDER BY ngay_giao_dich DESC LIMIT %s
    """
    df = pd.read_sql(q, conn, params=(ma_co_phieu, days))
    return df.sort_values("trade_date").reset_index(drop=True)


def compute_indicators(df):
    high, low, close, vol = df["high"], df["low"], df["close"], df["volume"]
    out = pd.DataFrame({"ngay_giao_dich": df["trade_date"]})
    out["ma_20"] = SMAIndicator(close, 20).sma_indicator()
    out["sma_50"] = SMAIndicator(close, 50).sma_indicator()
    out["ema_20"] = EMAIndicator(close, 20).ema_indicator()
    out["rsi_14"] = RSIIndicator(close, 14).rsi()
    macd = MACD(close)
    out["macd"] = macd.macd()
    out["macd_signal"] = macd.macd_signal()
    bb = BollingerBands(close, 20)
    out["bb_upper"] = bb.bollinger_hband()
    out["bb_lower"] = bb.bollinger_lband()
    out["bb_width"] = out["bb_upper"] - out["bb_lower"]
    atr = AverageTrueRange(high, low, close, 14)
    out["atr_14"] = atr.average_true_range()
    out["atr_pct"] = out["atr_14"] / close
    out["obv"] = OnBalanceVolumeIndicator(close, vol).on_balance_volume()
    out["do_lech_chuan_20"] = close.rolling(20).std()
    out["gia_so_voi_sma50"] = close / out["sma_50"] - 1
    out["mfi_14"] = MFIIndicator(high, low, close, vol, 14).money_flow_index()
    return out


def upsert_indicators(conn, ma_co_phieu, df, only_new_days):
    df = df.tail(only_new_days)
    rows = [
        (ma_co_phieu, r.ngay_giao_dich, r.ma_20, r.sma_50, r.ema_20, r.rsi_14,
         r.macd, r.macd_signal, r.bb_upper, r.bb_lower, r.bb_width,
         r.atr_14, r.atr_pct, r.obv, r.do_lech_chuan_20, r.gia_so_voi_sma50, r.mfi_14)
        for r in df.itertuples() if pd.notna(r.sma_50)
    ]
    if not rows:
        return 0
    with conn.cursor() as cur:
        execute_values(cur, """
            INSERT INTO chi_bao_ky_thuat
                (ma_co_phieu, ngay_giao_dich, ma_20, sma_50, ema_20, rsi_14, macd, macd_signal,
                 bb_upper, bb_lower, bb_width, atr_14, atr_pct, obv, do_lech_chuan_20,
                 gia_so_voi_sma50, mfi_14)
            VALUES %s
            ON CONFLICT (ma_co_phieu, ngay_giao_dich) DO UPDATE SET
                ma_20=EXCLUDED.ma_20, sma_50=EXCLUDED.sma_50, ema_20=EXCLUDED.ema_20,
                rsi_14=EXCLUDED.rsi_14, macd=EXCLUDED.macd, macd_signal=EXCLUDED.macd_signal,
                bb_upper=EXCLUDED.bb_upper, bb_lower=EXCLUDED.bb_lower, bb_width=EXCLUDED.bb_width,
                atr_14=EXCLUDED.atr_14, atr_pct=EXCLUDED.atr_pct, obv=EXCLUDED.obv,
                do_lech_chuan_20=EXCLUDED.do_lech_chuan_20, gia_so_voi_sma50=EXCLUDED.gia_so_voi_sma50,
                mfi_14=EXCLUDED.mfi_14
        """, rows)
    conn.commit()
    return len(rows)


def main():
    end_date = datetime.now().strftime("%Y-%m-%d")
    fetch_start = (datetime.now() - timedelta(days=LOOKBACK_DAYS_FOR_FETCH)).strftime("%Y-%m-%d")

    conn = psycopg2.connect(**DB_CONFIG)
    stocks = get_stocks(conn)
    log.info(f"Bắt đầu cập nhật {len(stocks)} mã: {[s[1] for s in stocks]}")

    for ma_co_phieu, symbol in stocks:
        try:
            df_new = fetch_prices(symbol, fetch_start, end_date)
            n_price = upsert_prices(conn, ma_co_phieu, df_new)

            df_recent = load_recent_prices(conn, ma_co_phieu, LOOKBACK_DAYS_FOR_INDICATOR)
            df_ind = compute_indicators(df_recent)
            n_ind = upsert_indicators(conn, ma_co_phieu, df_ind, only_new_days=LOOKBACK_DAYS_FOR_FETCH + 5)

            log.info(f"{symbol}: cập nhật {n_price} phiên giá, {n_ind} phiên chỉ báo")
        except Exception as e:
            log.error(f"{symbol}: LỖI — {e}")

    conn.close()
    log.info("Hoàn tất.")


if __name__ == "__main__":
    main()
