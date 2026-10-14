"""Apply ONLY the additive metadata DDL, preserving the existing schema."""
from .config import ROOT, connection

def main():
    sql = (ROOT/'migration_additive.sql').read_text(encoding='utf-8')
    conn = connection()
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
        conn.commit()
        print('OK: bảng stocktrain_prediction_meta đã sẵn sàng')
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

if __name__ == '__main__':
    main()
