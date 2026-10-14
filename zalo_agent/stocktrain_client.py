"""Ví dụ phía Zalo Agent: chỉ ĐỌC API E02, không có mã/tokens Zalo OA.

Bot phải tự triển khai webhook/Zalo OA và truyền câu trả lời vào API gửi tin nhắn.
"""
from __future__ import annotations
import os
import requests
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(Path(__file__).resolve().parent / '.env')
SYMBOLS = {'FPT', 'HPG', 'VCB', 'VNM', 'SSI'}
MODELS = {'LinearRegression', 'RandomForest', 'XGBoost', 'SVM (SVR)', 'LSTM'}


def get_prediction_text(symbol: str, model: str = 'LinearRegression') -> str:
    symbol = symbol.upper().strip()
    if symbol not in SYMBOLS:
        raise ValueError('Chỉ hỗ trợ 5 mã: FPT, HPG, VCB, VNM, SSI')
    if model not in MODELS:
        raise ValueError(f'Model không được hỗ trợ: {model}')
    base = os.getenv('STOCKTRAIN_API_URL', 'http://127.0.0.1:5001').rstrip('/')
    headers = {}
    # Chỉ dùng token nếu lớp proxy/API do nhóm triển khai thực sự kiểm tra token.
    api_token = os.getenv('STOCKTRAIN_API_TOKEN')
    if api_token:
        headers['Authorization'] = f'Bearer {api_token}'
    response = requests.get(
        f'{base}/api/predictions/latest',
        params={'symbol': symbol, 'model': model},
        headers=headers,
        timeout=(5, 15),
    )
    response.raise_for_status()
    rows = response.json().get('predictions') or []
    match = next((r for r in rows if r.get('symbol') == symbol and r.get('model') == model), None)
    if not match:
        return f'Chưa có dự báo {model} cho {symbol}.'
    pct = match.get('predicted_return_percent')
    if not isinstance(pct, (int, float)):
        raise ValueError('API trả về predicted_return_percent không hợp lệ')
    as_of = match.get('as_of') or 'không rõ'
    trend = {'UP': 'tăng', 'DOWN': 'giảm', 'SIDEWAYS': 'đi ngang'}.get(match.get('trend'), 'chưa xác định')
    return (f'{symbol} — {model} (5 phiên)\n'
            f'Ngày dữ liệu: {as_of}\n'
            f'Lợi suất dự báo: {pct:+.2f}%\n'
            f'Xu hướng dự báo: {trend}\n'
            'Ngày mục tiêu chỉ ước lượng (chưa trừ ngày nghỉ sàn).\n'
            'Rủi ro trên API là mô tả lịch sử, không phải dự báo E10.\n'
            'Chỉ phục vụ tham khảo, không phải khuyến nghị đầu tư.')


if __name__ == '__main__':
    import sys
    print(get_prediction_text(sys.argv[1] if len(sys.argv) > 1 else 'FPT'))
