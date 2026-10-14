"""Optional one-time history backfill. Requires --execute; never retrains models."""
import argparse
from datetime import datetime
from .config import SYMBOLS, connection
from fetch_stock_data import fetch_prices, get_stocks, upsert_prices


def main():
    parser=argparse.ArgumentParser(description='Nạp OHLCV lịch sử từ KBS vào gia_co_phieu')
    parser.add_argument('--start',default='2019-01-01', help='YYYY-MM-DD; notebook train lấy ~7 năm lịch sử')
    parser.add_argument('--execute',action='store_true', help='Thực sự ghi giá vào DB')
    args=parser.parse_args()
    datetime.strptime(args.start,'%Y-%m-%d')
    end=datetime.now().strftime('%Y-%m-%d')
    print(f'Backfill 5 mã từ {args.start} đến {end} trên nguồn KBS')
    if not args.execute:
        print('DRY RUN: không ghi gì. Thêm --execute để nạp dữ liệu sau khi đã backup PostgreSQL.')
        return
    conn=connection()
    errors=[]
    try:
        stocks=[(sid,sym) for sid,sym in get_stocks(conn) if sym in SYMBOLS]
        if {sym for _,sym in stocks}!=set(SYMBOLS):
            raise RuntimeError('CSDL thiếu mã, không thể backfill đủ năm mã')
        for sid,sym in stocks:
            try:
                df=fetch_prices(sym,args.start,end)
                if df is None or df.empty or len(df)<120:
                    raise RuntimeError(f'{sym}: lịch sử KBS không đủ 120 phiên')
                count=upsert_prices(conn,sid,df)
                print(f'OK {sym}: {count} phiên OHLCV; chạy daily_pipeline.py để cập nhật chỉ báo gần nhất')
            except Exception as e:
                conn.rollback()
                errors.append(sym)
                print(f'ERROR {sym}: {e}')
    finally:
        conn.close()
    if errors:
        raise RuntimeError('Backfill chưa xong các mã: '+', '.join(errors))

if __name__=='__main__':
    main()
