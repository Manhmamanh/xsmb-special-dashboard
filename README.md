# XSMB Special Tail Dashboard

Web app thống kê 2 số cuối giải đặc biệt XSMB trong 100 ngày gần nhất.

## Nguồn dữ liệu

Dashboard tự lấy dữ liệu từ:

<https://raw.githubusercontent.com/khiemdoan/vietnam-lottery-xsmb-analysis/refs/heads/main/data/xsmb.csv>

## Cập nhật tự động

GitHub Actions chạy hằng ngày lúc 20:00 giờ Việt Nam (`0 13 * * *` UTC), sinh lại `index.html` và deploy lên GitHub Pages.

Khi người dùng mở trang, app cũng tự thử tải dữ liệu mới nhất từ GitHub raw CSV. Nếu mạng lỗi, app dùng dữ liệu đã nhúng trong `index.html` làm dự phòng.

## Chạy local

```sh
python3 build_dashboard.py
```

Sau đó mở `index.html` trong trình duyệt.

## Lưu ý

Mô hình xác suất trong dashboard là thống kê tham khảo. Nếu xổ số độc lập và công bằng, mỗi số từ `00` đến `99` có xác suất lý thuyết gần `1%`.
