# Use Case – Gold Price Monitoring Bot

## UC-01 – Thu thập dữ liệu giá vàng

**Actor:** Gold Bot  
**Trigger:** Bot được chạy.

**Precondition:**
- Các nguồn dữ liệu được cấu hình.
- `history.json` có thể truy cập.

**Main Flow:**
1. Bot lấy giá vàng thế giới.
2. Bot lấy giá vàng trong nước.
3. Bot lấy tỷ giá USD/VND.
4. Bot kiểm tra và chuẩn hóa dữ liệu.
5. Bot cập nhật dữ liệu ngày hiện tại.
6. Bot lưu vào `history.json`.

**Alternate Flow:**
- Nguồn chính lỗi → sử dụng nguồn dự phòng.
- Một nguồn lỗi → tiếp tục xử lý các nguồn còn lại.

**Postcondition:** Dữ liệu hợp lệ được lưu, không trùng ngày.

---

## UC-02 – Phân tích biến động giá

**Actor:** Gold Bot  
**Trigger:** Dữ liệu đã được cập nhật.

**Precondition:** Có dữ liệu lịch sử hợp lệ.

**Main Flow:**
1. Tính % thay đổi D-1.
2. Tính % thay đổi D-7.
3. Tính SMA3 và SMA7.
4. Xác định xu hướng TĂNG/GIẢM/ĐI NGANG.

**Alternate Flow:**
- Không đủ dữ liệu → không tính chỉ số tương ứng.
- Không đủ dữ liệu SMA → thông báo chưa đủ dữ liệu.

**Postcondition:** Kết quả phân tích sẵn sàng cho báo cáo.

---

## UC-03 – Tạo và gửi báo cáo

**Actor:** Gold Bot / User  
**Trigger:** Thu thập và phân tích dữ liệu hoàn tất.

**Precondition:** Có dữ liệu khả dụng và Telegram được cấu hình.

**Main Flow:**
1. Tổng hợp dữ liệu giá vàng.
2. Quy đổi giá thế giới sang VND/lượng.
3. Tính chênh lệch giá.
4. Thêm kết quả phân tích.
5. Tạo báo cáo.
6. Gửi báo cáo qua Telegram.

**Alternate Flow:**
- Dữ liệu thiếu → hiển thị cảnh báo tương ứng.
- Gửi Telegram lỗi → ghi nhận lỗi.

**Postcondition:** User nhận được báo cáo nếu Telegram khả dụng.
