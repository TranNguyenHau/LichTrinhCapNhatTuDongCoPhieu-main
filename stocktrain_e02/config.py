"""Shared configuration. Secrets are read only from .env / environment."""
from __future__ import annotations
import os
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / '.env', override=False)
BUNDLE_ROOT = Path(os.getenv('STOCKTRAIN_BUNDLE_ROOT', str(ROOT / 'bundle_v1_profit_export_only_NEW'))).resolve()
os.environ['STOCKTRAIN_BUNDLE_ROOT'] = str(BUNDLE_ROOT)
SYMBOLS = ('FPT', 'HPG', 'VCB', 'VNM', 'SSI')
MODEL_NAMES = ('LinearRegression', 'RandomForest', 'XGBoost', 'SVM (SVR)', 'LSTM')
MODEL_TO_ENUM = {
    'LinearRegression': 'LINEAR_REGRESSION', 'RandomForest': 'RANDOM_FOREST',
    'XGBoost': 'XGBOOST', 'SVM (SVR)': 'SVR', 'LSTM': 'LSTM'
}
HORIZON = 5
MIN_HISTORY_ROWS = int(os.getenv('MIN_HISTORY_ROWS', '120'))
HISTORY_ROWS = int(os.getenv('HISTORY_ROWS', '1500'))
MAX_PRICE_AGE_BDAYS = int(os.getenv('MAX_PRICE_AGE_BDAYS', '5'))
ENABLE_MODELS = [x.strip() for x in os.getenv('ENABLE_MODELS', ','.join(MODEL_NAMES)).split(',') if x.strip()]
if not ENABLE_MODELS or any(x not in MODEL_NAMES for x in ENABLE_MODELS):
    raise ValueError('ENABLE_MODELS phải là tên model nằm trong manifest, phân tách bởi dấu phẩy')

def db_kwargs():
    password = os.getenv('DB_PASSWORD')
    if not password:
        raise RuntimeError('Chưa có DB_PASSWORD trong .env, không dùng mật khẩu ghi cứng trong code')
    return dict(host=os.getenv('DB_HOST', 'localhost'), port=int(os.getenv('DB_PORT', '5432')),
                dbname=os.getenv('DB_NAME', 'klcn284'), user=os.getenv('DB_USER', 'postgres'),
                password=password, connect_timeout=10)


def connection():
    import psycopg2
    return psycopg2.connect(**db_kwargs())
