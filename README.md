# LichTrinhTuDong — Cập nhật giá, dự báo E02 và Flask API

Mục đích: source để nhóm chia sẻ trên GitHub, phục vụ website và Zalo Agent.

**Trạng thái thực tế:** `daily_pipeline.py` đã được người phát triển chạy trên Windows ngày 14/10/2026: cập nhật 5 cổ phiếu, mỗi mã 5 dự báo mới, dùng bundle E02, không train lại. Bản source chia sẻ này **chưa được kiểm thử toàn bộ trên máy khác**.

## Cấu trúc

- `fetch_stock_data.py`: lấy dữ liệu vnstock + chỉ báo kỹ thuật; bản chia sẻ đã chuyển mật khẩu sang `.env`.
- `stocktrain_e02/daily_pipeline.py`: dùng lại fetch rồi dự báo, ghi PostgreSQL.
- `stocktrain_e02/api.py`: Flask API chỉ đọc dữ liệu.
- `stocktrain_e02/migrate.py`, `migration_additive.sql`: tạo bảng metadata nếu chưa có.
- `stocktrain_e02/model_service.py`: dùng model bundle **có sẵn**, không train lại.
- `zalo_agent/stocktrain_client.py`: ví dụ bot Zalo lấy câu trả lời từ API.
- `requirements.txt`: thư viện để chạy backend/model.
- `requirements-zalo.txt`: thư viện tối thiểu cho máy chỉ làm Zalo Agent.

## Cách ghép với ứng dụng hiện tại của người phát triển

1. Sao lưu folder `LichTrinhTuDong` đang hoạt động và Task Scheduler trước khi chép bất kỳ file nào.
2. **Không chép đè code đang chạy chỉ để chia sẻ với bạn học.** ZIP repo này nên đưa lên GitHub như một bản phân phối độc lập.
3. Người chạy backend cần tự đặt bundle đã được kiểm thử ở `stocktrain_e02/bundle_v1_profit_export_only_NEW/`, gồm manifest, `predict_bundle.py` đã hỗ trợ `model.ubj` và 25 artifact model. Bundle **không có trong Git**.
4. Tạo `stocktrain_e02/.env` từ `.env.example`, cấu hình PostgreSQL. KHÔNG đưa `.env` lên GitHub.
5. Cài requirements; mở PostgreSQL đã tạo từ schema riêng của dự án; nếu thiếu metadata, xem `migrate.py`.

```powershell
python -m venv .venv-1
.\.venv-1\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .\stocktrain_e02\.env.example .\stocktrain_e02\.env
.\.venv-1\Scripts\python.exe -m stocktrain_e02.check_setup
.\.venv-1\Scripts\python.exe -m stocktrain_e02.predict_preview --symbol FPT --model LinearRegression
```

Nếu bundle và DB sẵn sàng:

```powershell
.\.venv-1\Scripts\python.exe -m stocktrain_e02.api
# Trên terminal khác, chỉ khi muốn cập nhật + ghi dự báo:
.\.venv-1\Scripts\python.exe -m stocktrain_e02.daily_pipeline
```

API local (chỉ cùng máy):
- `GET /api/health`
- `GET /api/stocks`
- `GET /api/models`
- `GET /api/prices?symbol=FPT`
- `GET /api/predictions/latest?symbol=FPT&model=LinearRegression`
- `GET /api/predictions/history?symbol=FPT&limit=20`

**Lưu ý an toàn:** mặc định API Flask không kiểm tra bearer token và bind `127.0.0.1`; không expose port 5001 trực tiếp ra Internet. Zalo Agent khác máy cần reverse proxy HTTPS có xác thực, rate limiting và domain có thể truy cập được. CORS không thay thế xác thực. Không đẩy `.env`, SQL dump, bundle, file model hoặc log lên GitHub.

**Lưu ý mô hình:** đây là E02 dự báo lợi nhuận H5, không phải E10 dự báo biến động. `risk_level` chỉ biểu diễn biến động lịch sử; `target_date` chưa xét lịch nghỉ sàn. Dự báo không phải khuyến nghị đầu tư.

## Đẩy lên GitHub

Tại thư mục repo `LichTrinhTuDong_GitHub_READY`, tạo một repository rỗng tên **LichTrinhTuDong** trên GitHub (chọn Private nếu chỉ chia sẻ nhóm). **Không** tải ZIP bundle model hoặc `.env` vào GitHub.

```powershell
git init -b main
git add .
git status --short
git commit -m "Initial E02 prediction API for Zalo integration"
git remote add origin https://github.com/USERNAME/LichTrinhTuDong.git
git push -u origin main
```

Thay `USERNAME` bằng username GitHub và xác thực khi Git yêu cầu. Nếu không dùng terminal, GitHub → New repository → `LichTrinhTuDong` → Create → Add file → Upload files và tải các file **đã giải nén** (không upload file ZIP thành một file duy nhất).
