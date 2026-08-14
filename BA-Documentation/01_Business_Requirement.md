# Business Requirement – Gold Price Bot

## 1. Business Problem

Người dùng muốn theo dõi giá vàng tự động, cập nhật cụ thể mỗi ngày.

## 2. Business Objective

Tự động hóa việc thu thập, tổng hợp, lưu trữ và phân tích
dữ liệu giá vàng, sau đó cung cấp báo cáo định kỳ cho người dùng
thông qua Telegram.

## 3. Stakeholders

| Stakeholder | Role |
|---|---|
| User | Nhận và theo dõi báo cáo |
| Gold Bot | Thu thập và xử lý dữ liệu |
| Data Sources | Cung cấp dữ liệu giá |
| Telegram | Phân phối báo cáo |

## 4. Business Requirements

| ID | Requirement |
|---|---|
| BR-01 | Hệ thống tự động thu thập dữ liệu giá vàng. |
| BR-02 | Hệ thống tổng hợp giá vàng từ các nguồn được hỗ trợ. |
| BR-03 | Hệ thống lưu trữ dữ liệu lịch sử giá vàng. |
| BR-04 | Hệ thống phân tích biến động giá dựa trên dữ liệu lịch sử. |
| BR-05 | Hệ thống tạo báo cáo tổng hợp giá vàng. |
| BR-06 | Hệ thống gửi báo cáo định kỳ qua Telegram. |

## 5. Scope

### In Scope
- Thu thập dữ liệu giá vàng trong nước và thế giới.  
- Lưu trữ lịch sử giá theo ngày (tối đa 90 ngày gần nhất), không tạo bản ghi trùng ngày dù bot chạy nhiều lần/ngày.
- Phân tích biến động.
- Tạo báo cáo.
- Gửi Telegram.

### Out of Scope
- Giao dịch mua/bán vàng.
- Tư vấn đầu tư.
- Dự đoán giá vàng bằng Machine Learning.
- Dashboard Web.
