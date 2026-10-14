# Tích hợp Zalo Agent (phía consumer)

Mã này **không** gửi tin nhắn qua Zalo OA và **không** tạo webhook. Bạn của bạn cần tích hợp vào chatbot Zalo đang có.

```powershell
python -m pip install -r requirements-zalo.txt
Copy-Item .\zalo_agent\.env.example .\zalo_agent\.env
python -m zalo_agent.stocktrain_client FPT
```

Hàm `get_prediction_text(symbol, model)` gọi API đọc dự báo đã lưu tại `/api/predictions/latest` và trả văn bản tiếng Việt. Ví dụ trong xử lý tin nhắn Zalo OA:

```python
from zalo_agent.stocktrain_client import get_prediction_text
response_text = get_prediction_text('FPT', 'LinearRegression')
# Hãy dùng hàm send_message() theo SDK/webhook Zalo OA mà nhóm bạn tự cấu hình.
```

Nếu chạy từ máy khác: phải triển khai API dưới domain HTTPS có xác thực. `127.0.0.1` chỉ hoạt động trên cùng máy. Cấu hình `STOCKTRAIN_API_TOKEN` trong client tự nó **không thêm xác thực vào Flask API**; cần proxy/gateway hoặc middleware kiểm tra token thực sự.

Tránh gửi tên người dùng, mật khẩu DB, API key, dữ liệu nội bộ vào prompt của chatbot. Chỉ lấy thông tin từ endpoint GET đã giới hạn. Không có module E10 ở repo này.
