# 🥇 Gold Price Bot — Bot theo dõi giá vàng qua Telegram

Bot tự động lấy giá vàng trong nước (SJC, DOJI, BTMC...) và giá vàng thế giới
(XAU/USD), phân tích xu hướng ngắn hạn, rồi gửi báo cáo vào Telegram của bạn
mỗi sáng. Chạy hoàn toàn miễn phí trên GitHub Actions — không cần thuê server.

## 1. Chuẩn bị

Bạn cần có sẵn:
- `TELEGRAM_BOT_TOKEN` — token của bot Telegram (lấy từ @BotFather)
- `TELEGRAM_CHAT_ID` — chat ID của bạn

## 2. Đưa code lên GitHub

1. Tạo một repo mới trên GitHub (có thể để **private**).
2. Upload toàn bộ các file trong thư mục này lên repo đó (giữ nguyên cấu trúc,
   đặc biệt là thư mục `.github/workflows/`).

## 3. Khai báo Secrets

Vào repo trên GitHub → **Settings** → **Secrets and variables** → **Actions**
→ **New repository secret**, thêm 2 secret:

| Name | Value |
|---|---|
| `TELEGRAM_BOT_TOKEN` | token bot của bạn |
| `TELEGRAM_CHAT_ID` | chat ID của bạn |

## 4. Bật GitHub Actions & test thử

1. Vào tab **Actions** của repo, bấm **"I understand my workflows, go ahead
   and enable them"** nếu được hỏi.
2. Chọn workflow **"Gold Price Bot"** → **Run workflow** để chạy thử ngay
   (không cần đợi tới 8h sáng).
3. Nếu chạy thành công, bạn sẽ nhận được tin nhắn báo giá vàng trong Telegram.

Sau đó bot sẽ tự động chạy mỗi ngày lúc **8:00 sáng giờ Việt Nam** theo lịch
cron trong `.github/workflows/gold-price.yml`. Muốn đổi giờ, sửa dòng
`cron: "0 1 * * *"` (giờ UTC = giờ VN − 7).

## 5. Cấu trúc project

```
.
├── main.py                          # logic chính: lấy giá, phân tích, gửi Telegram
├── requirements.txt                 # thư viện Python cần cài
├── history.json                     # lịch sử giá theo ngày (bot tự cập nhật & commit lại)
├── .github/workflows/gold-price.yml # lịch chạy tự động trên GitHub Actions
└── README.md
```

## 6. Nguồn dữ liệu & giới hạn cần biết

| Nguồn | Cách lấy | Độ ổn định |
|---|---|---|
| Vàng SJC | thư viện [`vnstock`](https://github.com/thinh-vu/vnstock) | Khá ổn định, được cộng đồng bảo trì |
| Vàng BTMC (nhiều loại) | thư viện `vnstock` | Khá ổn định |
| Vàng DOJI | API không chính thức của giavang.doji.vn | Có thể đổi/ngừng bất kỳ lúc nào |
| Vàng thế giới (XAU/USD) | API công khai goldprice.org | Ổn định, được nhiều app dùng |
| Tỷ giá USD/VND | API công khai open.er-api.com | Ổn định |
| Vàng PNJ | *(chưa bật)* — PNJ không có API JSON công khai ổn định | — |

Vì DOJI/PNJ không có API chính thức, mọi lỗi lấy dữ liệu đều được xử lý an
toàn (try/except): nếu một nguồn bị lỗi, bot vẫn gửi báo cáo với các nguồn
còn lại thay vì crash. Nếu bạn thấy một nguồn liên tục báo lỗi, có thể trang
web nguồn đã đổi cấu trúc — lúc đó cần cập nhật lại hàm `fetch_...` tương ứng
trong `main.py`.

Phần PNJ hiện đang tắt (`fetch_pnj` trả về `None`) vì mình chưa tìm được cách
bóc tách dữ liệu đáng tin cậy từ trang PNJ. Nếu bạn tìm được API/endpoint ổn
định của PNJ, có thể bổ sung vào hàm `fetch_pnj()` trong `main.py`.

## 7. Phần phân tích xu hướng

Bot tính:
- % thay đổi so với hôm qua và 7 ngày trước (dựa trên giá SJC)
- Đường trung bình động 3 ngày (SMA3) và 7 ngày (SMA7) để đưa ra tín hiệu xu
  hướng ngắn hạn (Tăng / Giảm / Đi ngang)
- Chênh lệch giữa giá vàng trong nước và giá vàng thế giới quy đổi

**Đây là công cụ tham khảo, không phải lời khuyên đầu tư.** Xu hướng dựa trên
dữ liệu lịch sử ngắn hạn có thể sai lệch nhiều so với biến động thực tế của
thị trường vàng — bạn nên tự cân nhắc, kết hợp thêm các nguồn thông tin khác
trước khi ra quyết định.

## 8. Tùy chỉnh thêm (gợi ý)

- Thêm cảnh báo khi giá biến động vượt ngưỡng bạn đặt (ví dụ ±1%/ngày)
- Thêm lệnh Telegram tương tác (`/gia`) bằng cách host thêm 1 webhook nhỏ
  (Render, Railway...) bên cạnh phần cron trên GitHub Actions
- Vẽ biểu đồ giá theo thời gian từ `history.json` và gửi kèm ảnh vào Telegram
