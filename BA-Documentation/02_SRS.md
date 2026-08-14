# Software Requirements Specification (SRS)

## 1. Purpose

Tài liệu này mô tả các yêu cầu chức năng và yêu cầu phi chức năng của hệ thống Gold Price Monitoring Bot.

Tài liệu SRS là cơ sở cho quá trình phát triển, kiểm thử và quản lý truy vết yêu cầu, theo chuỗi:

Yêu cầu nghiệp vụ → Yêu cầu người dùng → Yêu cầu chức năng → Use Case → Test Case

---

## 2. User Requirements

| ID | User Requirement | Related BR |
|---|---|---|
| UR-01 | Người dùng muốn nhận báo cáo giá vàng tự động qua Telegram. | BR-01 |
| UR-02 | Người dùng muốn biết mức thay đổi giá so với ngày trước và 7 ngày trước. | BR-04 |
| UR-03 | Người dùng muốn xem tín hiệu xu hướng TĂNG/GIẢM/ĐI NGANG được hệ thống tổng hợp. | BR-04 |
| UR-04 | Người dùng muốn xem giá vàng thế giới quy đổi sang VND/lượng và chênh lệch với SJC. | BR-05 |
| UR-05 | Người dùng muốn báo cáo vẫn được tạo khi một nguồn dữ liệu không khả dụng, kèm cảnh báo tương ứng. | BR-03 |

---

## 3. Functional Requirements

### 3.1 Data Collection

| ID | Requirement | Related BR |
|---|---|---|
| FR-01 | Hệ thống phải thu thập giá vàng thế giới XAU/USD từ nguồn dữ liệu được cấu hình và sử dụng nguồn dự phòng khi nguồn chính không khả dụng. | BR-01 |
| FR-02 | Hệ thống phải thu thập giá mua/bán của SJC, DOJI và PNJ. | BR-01 |
| FR-03 | Hệ thống phải thu thập tỷ giá USD/VND và kiểm tra giá trị hợp lệ. | BR-05 |
| FR-04 | Hệ thống phải có cơ chế retry/fallback khi request trực tiếp thất bại. | BR-03 |

### 3.2 Data Management

| ID | Requirement | Related BR |
|---|---|---|
| FR-05 | Hệ thống phải đọc và chuẩn hóa dữ liệu từ `history.json`. | BR-04 |
| FR-06 | Hệ thống phải cập nhật record của ngày hiện tại nếu đã tồn tại hoặc tạo record mới nếu chưa tồn tại. | BR-04 |
| FR-07 | Hệ thống phải lưu trữ tối đa 90 ngày dữ liệu lịch sử gần nhất. | BR-06 |
| FR-08 | Hệ thống không được tạo nhiều record cho cùng một ngày. | BR-04 |

### 3.3 Trend Analysis

| ID | Requirement | Related BR |
|---|---|---|
| FR-09 | Hệ thống phải tính % thay đổi giá SJC so với ngày gần nhất trước đó có dữ liệu. | BR-04 |
| FR-10 | Hệ thống phải tính % thay đổi giá SJC so với đúng 7 ngày trước. | BR-04 |
| FR-11 | Hệ thống phải tính SMA3 dựa trên dữ liệu giá bán SJC. | BR-04 |
| FR-12 | Hệ thống phải tính SMA7 dựa trên dữ liệu giá bán SJC. | BR-04 |
| FR-13 | Hệ thống phải xác định tín hiệu TĂNG, GIẢM hoặc ĐI NGANG dựa trên SMA3 và SMA7. | BR-04 |

### 3.4 Reporting

| ID | Requirement | Related BR |
|---|---|---|
| FR-14 | Hệ thống phải quy đổi giá vàng thế giới sang VND/lượng dựa trên tỷ giá USD/VND. | BR-05 |
| FR-15 | Hệ thống phải tính chênh lệch giữa giá bán SJC và giá vàng thế giới quy đổi. | BR-05 |
| FR-16 | Hệ thống phải tạo báo cáo tổng hợp giá vàng và thông tin phân tích. | BR-02 |
| FR-17 | Hệ thống phải hiển thị cảnh báo đối với dữ liệu không khả dụng. | BR-03 |
| FR-18 | Hệ thống phải gửi báo cáo qua Telegram Bot API. | BR-02 |

---

## 4. Business Rules

| ID | Rule |
|---|---|
| BRULE-01 | D-1 được tính với ngày gần nhất trước ngày hiện tại có dữ liệu hợp lệ. |
| BRULE-02 | D-7 được tính với đúng ngày cách ngày hiện tại 7 ngày. |
| BRULE-03 | SMA3 sử dụng 3 ngày có dữ liệu gần nhất. |
| BRULE-04 | SMA7 sử dụng 7 ngày có dữ liệu gần nhất. |
| BRULE-05 | Nếu SMA3 > SMA7 × 1.001 → TĂNG. |
| BRULE-06 | Nếu SMA3 < SMA7 × 0.999 → GIẢM. |
| BRULE-07 | Các trường hợp còn lại → ĐI NGANG. |
| BRULE-08 | Nếu chưa đủ dữ liệu, hệ thống không đưa ra tín hiệu xu hướng. |
| BRULE-09 | Giá mua/bán phải là số dương và giá bán không thấp hơn giá mua. |
| BRULE-10 | Mỗi ngày chỉ duy trì một record trong `history.json`. |

---

## 5. Non-Functional Requirements

| ID | Category | Requirement |
|---|---|---|
| NFR-01 | Performance | HTTP request có timeout tối đa 15 giây; proxy fallback có timeout tối đa 25 giây. |
| NFR-02 | Reliability | Hệ thống có cơ chế fallback cho nguồn dữ liệu và kết nối mạng. |
| NFR-03 | Fault Tolerance | Lỗi tại một nguồn dữ liệu không được làm dừng toàn bộ quá trình xử lý. |
| NFR-04 | Security | `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` và `GOLDAPI_KEY` phải được quản lý bằng environment variables. |
| NFR-05 | Data Integrity | `history.json` được ghi thông qua temporary file và `os.replace()`. |
| NFR-06 | Maintainability | Hệ thống phải ghi log lỗi có thông tin ngữ cảnh để hỗ trợ monitoring và troubleshooting. |
| NFR-07 | Timezone | Logic thời gian sử dụng múi giờ Việt Nam UTC+7. |
| NFR-08 | Scalability | Cấu trúc nguồn dữ liệu cho phép bổ sung thương hiệu mới mà không thay đổi logic xử lý chính. |

---

## 6. Data Requirements

### Data Source

`history.json`

### Data Dictionary

| Field | Type | Description | Constraint |
|---|---|---|---|
| `date` | String | Ngày ghi nhận | `YYYY-MM-DD`, unique |
| `sjc_buy` | Float / Null | Giá mua SJC | > 0 nếu có giá trị |
| `sjc_sell` | Float / Null | Giá bán SJC | > 0 nếu có giá trị |
| `world_usd_oz` | Float / Null | Giá vàng thế giới | > 0 nếu có giá trị |
| `usd_vnd` | Float / Null | Tỷ giá USD/VND | > 0 nếu có giá trị |

**Retention:** Tối đa 90 ngày gần nhất.

---

## 7. Assumptions & Constraints

### Assumptions

- Người dùng có Telegram Chat ID hợp lệ.
- Các nguồn dữ liệu bên thứ ba khả dụng tại thời điểm hệ thống chạy.
- Dữ liệu đầu vào tuân theo cấu trúc mà hệ thống hiện hỗ trợ.

### Constraints

- Hệ thống phụ thuộc vào API/website của bên thứ ba.
- Dữ liệu giá vàng trong nước phụ thuộc vào cấu trúc HTML của nguồn dữ liệu.
- GoldAPI chỉ được sử dụng khi `GOLDAPI_KEY` được cấu hình.
- Hệ thống hiện sử dụng `history.json` thay vì database.
- Hệ thống hiện hỗ trợ một Telegram Chat ID cho mỗi cấu hình chạy.
- Hệ thống không thực hiện giao dịch mua/bán vàng.
- Hệ thống không cung cấp tư vấn đầu tư.

---

## 8. Traceability

| Business Requirement | User Requirement | Functional Requirement |
|---|---|---|
| BR-01 | UR-01 | FR-01, FR-02 |
| BR-02 | UR-01 | FR-16, FR-18 |
| BR-03 | UR-05 | FR-04, FR-17 |
| BR-04 | UR-02, UR-03 | FR-05, FR-06, FR-08, FR-09–FR-13 |
| BR-05 | UR-04 | FR-03, FR-14, FR-15 |
| BR-06 | — | FR-07 |
| BR-07 | — | Các FR liên quan |

---

## 9. Out of Scope

- Giao dịch mua/bán vàng.
- Tư vấn đầu tư.
- Dự đoán giá bằng Machine Learning.
- Dashboard Web.
- Quản lý tài khoản người dùng.
- Multi-tenant.
- Cảnh báo theo mức giá do người dùng tự cấu hình.
