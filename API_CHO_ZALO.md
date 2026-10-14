# Hợp đồng API phục vụ Zalo Agent

API chạy bằng lệnh `python -m stocktrain_e02.api`; không tự chạy trong GitHub.

| Endpoint | Ý nghĩa |
| --- | --- |
| `GET /api/health` | Kiểm tra DB và bundle |
| `GET /api/stocks` | Danh sách 5 mã |
| `GET /api/models` | Tên model, horizon |
| `GET /api/prices?symbol=FPT&limit=120` | OHLCV lịch sử |
| `GET /api/predictions/latest?symbol=FPT&model=LinearRegression` | Dự báo gần nhất |
| `GET /api/predictions/history?symbol=FPT&limit=20` | Lịch sử dự báo |

## Cấu trúc response thực tế của `/api/predictions/latest`

```json
{
  "count": 1,
  "predictions": [{
    "symbol": "FPT",
    "model": "LinearRegression",
    "as_of": "2026-10-14",
    "predicted_return": 0.012,
    "predicted_return_percent": 1.2,
    "trend": "UP",
    "risk_level": "LOW",
    "target_date_estimated": true,
    "trained_until": "2025-08-19"
  }]
}
```

**JSON trên chỉ minh hoạ schema (không phải số dự báo thực tế).** Response thật có thêm các trường `target_date`, `warnings`, `descriptive_risk`, `experiment_id`, `bundle_sha256`, `risk_notice`, `target_notice`.

`predicted_return` là lợi suất dạng thập phân, `predicted_return_percent` là phần trăm; không nhân 100 hai lần. `risk_level` là phân vị biến động quá khứ, không phải E10. `target_date` chỉ là ngày ước tính theo thứ Hai–thứ Sáu (chưa trừ ngày nghỉ thị trường).

Zalo agent chỉ nên thực hiện GET đối với API hiện có; không cần quyền truy cập database. API mặc định ở `127.0.0.1:5001` và **không thể dùng từ server Zalo ở máy khác** nếu chưa có HTTPS reverse proxy/host. Cần xác thực và giới hạn tốc độ trước khi công khai.
