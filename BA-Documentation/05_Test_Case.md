| TC ID | Requirement | Test Scenario | Test Steps | Expected Result |
|---|---|---|---|---|
| TC-01 | FR-01 | Lấy giá vàng thế giới thành công | Chạy Bot khi nguồn chính khả dụng | Giá XAU/USD được lấy thành công |
| TC-02 | FR-01 | Nguồn giá vàng chính lỗi | Làm nguồn chính không khả dụng → chạy Bot | Bot sử dụng nguồn dự phòng |
| TC-03 | FR-02 | Lấy giá vàng trong nước | Chạy Bot khi nguồn dữ liệu khả dụng | Giá SJC, DOJI, PNJ được lấy thành công |
| TC-04 | FR-03 | Lấy tỷ giá USD/VND | Chạy Bot khi API khả dụng | Tỷ giá hợp lệ được lấy |
| TC-05 | FR-05 | Đọc và chuẩn hóa history | Chạy Bot với history hợp lệ | Dữ liệu được đọc và chuẩn hóa |
| TC-06 | FR-06 | Cập nhật record hiện tại | Chạy Bot khi ngày hiện tại đã tồn tại | Record được cập nhật, không tạo record mới |
| TC-07 | FR-06, FR-08 | Tạo record mới | Chạy Bot khi ngày hiện tại chưa tồn tại | Record mới được tạo và không bị trùng |
| TC-08 | FR-07 | Giới hạn lịch sử 90 ngày | Chạy Bot với dữ liệu vượt quá 90 ngày | Chỉ giữ 90 ngày gần nhất |
| TC-09 | FR-09, FR-10 | Tính D-1 và D-7 | Chạy Bot với đủ dữ liệu | D-1 và D-7 được tính chính xác |
| TC-10 | FR-11, FR-12, FR-13 | Phân tích xu hướng | Chạy Bot với đủ dữ liệu | SMA3, SMA7 và tín hiệu được xác định |
| TC-11 | FR-14, FR-15 | Quy đổi và tính chênh lệch | Chạy Bot với dữ liệu hợp lệ | Giá quy đổi và chênh lệch được tính |
| TC-12 | FR-18 | Gửi báo cáo Telegram | Chạy Bot với Telegram hợp lệ | Báo cáo được gửi thành công |
| TC-13 | FR-02 | Dữ liệu giá không hợp lệ | Cung cấp giá âm hoặc giá bán < giá mua | Dữ liệu bị từ chối |
| TC-14 | FR-04 | Request bị timeout | Giả lập request timeout | Bot thực hiện fallback/retry và không crash |
| TC-15 | FR-13, BRULE-08 | Không đủ dữ liệu phân tích | Thiếu dữ liệu để tính SMA | Bot không đưa ra tín hiệu sai |
| TC-16 | FR-17 | Một nguồn dữ liệu bị thiếu | Làm một nguồn không khả dụng | Báo cáo vẫn được tạo và hiển thị cảnh báo |
