#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Bot theo dõi giá vàng (trong nước + thế giới) và gửi báo cáo qua Telegram.

Các nguyên tắc chính của phiên bản này:
1. History được lưu theo NGÀY, không theo số lần bot chạy.
2. Mỗi ngày chỉ có 1 record. Nếu bot chạy nhiều lần/ngày, record của ngày đó
   sẽ được cập nhật thay vì append thêm.
3. D-1 lấy ngày có dữ liệu gần nhất trước ngày hiện tại.
4. D-7 lấy đúng ngày cách hiện tại 7 ngày; nếu không có dữ liệu thì báo N/A.
5. SMA3/SMA7 được tính theo các ngày có dữ liệu, bao gồm giá hiện tại.
6. History chỉ giữ tối đa 90 ngày theo CALENDAR DATE.
7. Có validation cơ bản để tránh ghi dữ liệu bất thường.
"""

import csv
import html
import io
import json
import os
import re
import sys
from datetime import datetime, timezone, timedelta
from urllib.parse import quote

import requests
from bs4 import BeautifulSoup


# ============================================================
# CẤU HÌNH
# ============================================================

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
HISTORY_FILE = os.path.join(BASE_DIR, "history.json")
MAX_HISTORY_DAYS = 90

VN_TZ = timezone(timedelta(hours=7))

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
}

REQUEST_TIMEOUT = 15

# Nguồn giá vàng trong nước.
DOMESTIC_SOURCES = {
    "SJC": "https://giavang.org/trong-nuoc/sjc/",
    "DOJI": "https://giavang.org/trong-nuoc/doji/",
    "PNJ": "https://giavang.org/trong-nuoc/pnj/",
}

# 1 lượng vàng Việt Nam = 37.5 gram.
# 1 troy ounce = 31.1034768 gram.
GRAM_PER_LUONG = 37.5
GRAM_PER_TROY_OZ = 31.1034768
OZ_PER_LUONG = GRAM_PER_LUONG / GRAM_PER_TROY_OZ


# ============================================================
# HTTP HELPER
# ============================================================

def smart_get(url, timeout=REQUEST_TIMEOUT, use_proxy_fallback=True):
    """
    Gọi GET trực tiếp.
    Nếu lỗi, thử qua allorigins.win như một phương án dự phòng.
    """
    try:
        response = requests.get(
            url,
            headers=HEADERS,
            timeout=timeout
        )

        if response.status_code == 200:
            return response

        raise requests.exceptions.HTTPError(
            "HTTP %s cho %s" % (response.status_code, url)
        )

    except Exception as direct_error:
        if not use_proxy_fallback:
            raise

        try:
            proxy_url = (
                "https://api.allorigins.win/raw?url="
                + quote(url, safe="")
            )

            response = requests.get(
                proxy_url,
                headers=HEADERS,
                timeout=timeout + 10
            )
            response.raise_for_status()
            return response

        except Exception as proxy_error:
            raise RuntimeError(
                "Gọi trực tiếp lỗi (%s); gọi qua proxy cũng lỗi (%s)"
                % (direct_error, proxy_error)
            )


# ============================================================
# UTILITY
# ============================================================

def safe_float(value):
    """Chuyển value sang float; trả None nếu không hợp lệ."""
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def is_valid_positive_number(value):
    """Kiểm tra số dương hợp lệ."""
    return value is not None and value > 0


def parse_date(date_text):
    """Parse YYYY-MM-DD thành date object."""
    try:
        return datetime.strptime(date_text, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


def fmt_vnd(value):
    if value is None:
        return "N/A"

    return "{:,.0f}".format(value).replace(",", ".")


def fmt_usd(value):
    if value is None:
        return "N/A"

    return "{:,.2f}".format(value)


def trend_arrow(change):
    if change is None:
        return "➖"

    if change > 0.05:
        return "📈"

    if change < -0.05:
        return "📉"

    return "➡️"


def pct_change(current, previous):
    if current is None or previous in (None, 0):
        return None

    return (current - previous) / previous * 100


# ============================================================
# LẤY GIÁ VÀNG THẾ GIỚI
# ============================================================

def fetch_world_gold():
    """
    Lấy giá vàng thế giới (USD/oz).

    Nguồn chính:
        goldprice.dev

    Nguồn dự phòng:
        GoldAPI.io nếu có GOLDAPI_KEY
        Stooq
    """

    # --------------------------------------------------------
    # Nguồn chính: goldprice.dev
    # --------------------------------------------------------
    try:
        spot_url = "https://api.goldprice.dev/v1/spot/XAU-USD-SPOT"

        response = smart_get(spot_url)
        data = response.json()

        price = safe_float(data.get("price"))

        if not is_valid_positive_number(price):
            raise ValueError("Giá XAU/USD không hợp lệ")

        today = datetime.now(VN_TZ).date()
        yesterday = today - timedelta(days=1)

        hist_url = (
            "https://api.goldprice.dev/v1/bars"
            "?symbol=XAU-USD-SPOT"
            "&interval=1d"
            "&from=%s"
            "&to=%s"
            % (
                yesterday.strftime("%Y-%m-%d"),
                today.strftime("%Y-%m-%d")
            )
        )

        hist_response = smart_get(hist_url)
        hist = hist_response.json()
        bars = hist.get("bars", [])

        change_pct = None

        # API hiện được kỳ vọng trả bars theo thứ tự mới -> cũ.
        # Tuy nhiên vẫn kiểm tra dữ liệu trước khi tính.
        if len(bars) >= 2:
            first_close = safe_float(bars[0].get("close"))
            second_close = safe_float(bars[1].get("close"))

            if (
                is_valid_positive_number(first_close)
                and is_valid_positive_number(second_close)
            ):
                change_pct = pct_change(first_close, second_close)

        return {
            "usd_oz": price,
            "change_pct": change_pct,
            "source": "goldprice.dev",
        }

    except Exception as error:
        print(
            "[LỖI] fetch_world_gold (goldprice.dev): %s"
            % error,
            file=sys.stderr
        )

    # --------------------------------------------------------
    # Dự phòng 1: GoldAPI.io
    # --------------------------------------------------------
    goldapi_key = os.environ.get("GOLDAPI_KEY", "")

    if goldapi_key:
        try:
            api_headers = {
                "x-access-token": goldapi_key,
                "User-Agent": HEADERS["User-Agent"],
            }

            response = requests.get(
                "https://www.goldapi.io/api/XAU/USD",
                headers=api_headers,
                timeout=REQUEST_TIMEOUT
            )

            response.raise_for_status()
            data = response.json()

            price = safe_float(data.get("price"))

            if not is_valid_positive_number(price):
                raise ValueError("Giá XAU/USD từ GoldAPI không hợp lệ")

            change = safe_float(data.get("ch"))

            return {
                "usd_oz": price,
                "change_pct": change,
                "source": "goldapi.io",
            }

        except Exception as error:
            print(
                "[LỖI] fetch_world_gold (goldapi.io): %s"
                % error,
                file=sys.stderr
            )

    # --------------------------------------------------------
    # Dự phòng 2: Stooq
    # --------------------------------------------------------
    try:
        response = smart_get(
            "https://stooq.com/q/d/l/?s=xauusd&i=d"
        )

        rows = list(
            csv.reader(
                io.StringIO(response.text.strip())
            )
        )

        if len(rows) >= 2:
            data_rows = rows[1:]

            for row in reversed(data_rows):
                if len(row) < 5:
                    continue

                close = safe_float(row[4])

                if is_valid_positive_number(close):
                    return {
                        "usd_oz": close,
                        "change_pct": None,
                        "source": "stooq",
                    }

    except Exception as error:
        print(
            "[LỖI] fetch_world_gold (Stooq): %s"
            % error,
            file=sys.stderr
        )

    return None


# ============================================================
# TỶ GIÁ USD/VND
# ============================================================

def fetch_usd_vnd_rate():
    """Lấy tỷ giá USD/VND từ open.er-api.com."""
    try:
        response = smart_get(
            "https://open.er-api.com/v6/latest/USD"
        )

        data = response.json()
        rate = safe_float(
            data.get("rates", {}).get("VND")
        )

        if not is_valid_positive_number(rate):
            raise ValueError("Tỷ giá USD/VND không hợp lệ")

        return rate

    except Exception as error:
        print(
            "[LỖI] fetch_usd_vnd_rate: %s"
            % error,
            file=sys.stderr
        )

        return None


# ============================================================
# GIÁ VÀNG TRONG NƯỚC
# ============================================================

_PRICE_PATTERN = re.compile(
    r"Mua\s*vào\s*([\d.,]+)\s*x1000đ/lượng"
    r".*?"
    r"Bán\s*ra\s*([\d.,]+)\s*x1000đ/lượng",
    re.IGNORECASE | re.DOTALL,
)


def parse_domestic_price(text):
    """
    Parse giá từ text của trang giavang.org.

    Dạng kỳ vọng:
        Mua vào 137.400 x1000đ/lượng
        ...
        Bán ra 141.400 x1000đ/lượng
    """

    match = _PRICE_PATTERN.search(text)

    if not match:
        return None

    buy_raw = match.group(1)
    sell_raw = match.group(2)

    try:
        buy = float(
            buy_raw.replace(".", "").replace(",", "")
        ) * 1000

        sell = float(
            sell_raw.replace(".", "").replace(",", "")
        ) * 1000

    except ValueError:
        return None

    if not is_valid_positive_number(buy):
        return None

    if not is_valid_positive_number(sell):
        return None

    # Giá bán không hợp lý nếu thấp hơn giá mua.
    if sell < buy:
        return None

    return {
        "buy": buy,
        "sell": sell,
    }


def fetch_domestic_brand(brand_name, url):
    """Lấy giá mua/bán của SJC, DOJI hoặc PNJ."""
    try:
        response = smart_get(url)

        soup = BeautifulSoup(
            response.text,
            "lxml"
        )

        text = soup.get_text(
            " ",
            strip=True
        )

        price = parse_domestic_price(text)

        if price is None:
            print(
                "[LỖI] fetch_domestic_brand(%s): "
                "không tìm thấy mẫu giá hợp lệ"
                % brand_name,
                file=sys.stderr
            )

            return None

        return {
            "name": brand_name,
            "buy": price["buy"],
            "sell": price["sell"],
        }

    except Exception as error:
        print(
            "[LỖI] fetch_domestic_brand(%s): %s"
            % (brand_name, error),
            file=sys.stderr
        )

        return None


# ============================================================
# HISTORY
# ============================================================

def validate_history_record(record):
    """
    Kiểm tra record history có cấu trúc hợp lệ không.
    Không yêu cầu tất cả trường giá phải có dữ liệu.
    """

    if not isinstance(record, dict):
        return False

    date_text = record.get("date")

    if parse_date(date_text) is None:
        return False

    numeric_fields = (
        "sjc_buy",
        "sjc_sell",
        "world_usd_oz",
        "usd_vnd",
    )

    for field in numeric_fields:
        value = record.get(field)

        if value is not None:
            value = safe_float(value)

            if value is None or value <= 0:
                return False

    return True


def normalize_history(history):
    """
    Chuẩn hóa history cũ:
    - bỏ record lỗi
    - ép số về float
    - nếu có nhiều record cùng ngày thì giữ record cuối cùng
    - sắp xếp theo ngày tăng dần
    """

    if not isinstance(history, list):
        return []

    by_date = {}

    for record in history:
        if not validate_history_record(record):
            continue

        date_text = record["date"]

        normalized = {
            "date": date_text,
            "sjc_buy": safe_float(record.get("sjc_buy")),
            "sjc_sell": safe_float(record.get("sjc_sell")),
            "world_usd_oz": safe_float(
                record.get("world_usd_oz")
            ),
            "usd_vnd": safe_float(
                record.get("usd_vnd")
            ),
        }

        # Nếu history cũ có nhiều lần chạy cùng ngày,
        # record cuối cùng sẽ được giữ lại.
        by_date[date_text] = normalized

    result = list(by_date.values())

    result.sort(
        key=lambda item: item["date"]
    )

    return result


def load_history():
    if not os.path.exists(HISTORY_FILE):
        return []

    try:
        with open(
            HISTORY_FILE,
            "r",
            encoding="utf-8"
        ) as file:
            history = json.load(file)

        return normalize_history(history)

    except Exception as error:
        print(
            "[CẢNH BÁO] Không đọc được history.json: %s"
            % error,
            file=sys.stderr
        )

        return []


def save_history(history, today_date):
    """
    Lưu history theo ngày.
    Chỉ giữ MAX_HISTORY_DAYS ngày gần nhất.
    Ghi file theo kiểu atomic để giảm nguy cơ file JSON bị hỏng.
    """

    history = normalize_history(history)

    today = parse_date(today_date)

    if today is None:
        raise ValueError(
            "today_date không hợp lệ: %s"
            % today_date
        )

    oldest_allowed_date = (
        today - timedelta(days=MAX_HISTORY_DAYS - 1)
    )

    filtered = []

    for record in history:
        record_date = parse_date(record["date"])

        if record_date is None:
            continue

        if (
            oldest_allowed_date
            <= record_date
            <= today
        ):
            filtered.append(record)

    filtered.sort(
        key=lambda item: item["date"]
    )

    temp_file = HISTORY_FILE + ".tmp"

    with open(
        temp_file,
        "w",
        encoding="utf-8"
    ) as file:
        json.dump(
            filtered,
            file,
            ensure_ascii=False,
            indent=2
        )

    os.replace(
        temp_file,
        HISTORY_FILE
    )


def upsert_today_record(history, today_record):
    """
    Thêm hoặc cập nhật record của ngày hiện tại.

    Đây là phần quan trọng để bot có thể chạy nhiều lần/ngày
    mà không biến 7 lần chạy thành 7 ngày.
    """

    today_date = today_record["date"]

    updated = False
    new_history = []

    for record in history:
        if record.get("date") == today_date:
            new_history.append(today_record)
            updated = True
        else:
            new_history.append(record)

    if not updated:
        new_history.append(today_record)

    return normalize_history(new_history)


# ============================================================
# PHÂN TÍCH XU HƯỚNG
# ============================================================

def get_previous_available_record(history, current_date):
    """
    Tìm record gần nhất trước current_date.

    Dùng cho D-1 theo nghĩa:
    "ngày trước đó gần nhất có dữ liệu".
    """

    current = parse_date(current_date)

    if current is None:
        return None

    candidates = []

    for record in history:
        record_date = parse_date(record.get("date"))
        price = safe_float(record.get("sjc_sell"))

        if record_date is None:
            continue

        if record_date < current and price is not None and price > 0:
            candidates.append(record)

    if not candidates:
        return None

    candidates.sort(
        key=lambda item: item["date"],
        reverse=True
    )

    return candidates[0]


def get_exact_date_record(history, target_date):
    """Tìm đúng record của target_date."""
    target = parse_date(target_date)

    if target is None:
        return None

    for record in history:
        if record.get("date") == target.strftime("%Y-%m-%d"):
            return record

    return None


def get_sjc_values(history):
    """
    Lấy danh sách record có SJC sell hợp lệ,
    sắp xếp theo ngày tăng dần.
    """

    records = []

    for record in history:
        value = safe_float(
            record.get("sjc_sell")
        )

        if value is None or value <= 0:
            continue

        if parse_date(record.get("date")) is None:
            continue

        records.append({
            "date": record["date"],
            "sjc_sell": value,
        })

    records.sort(
        key=lambda item: item["date"]
    )

    return records


def compute_sma_from_records(records, window):
    """
    SMA theo số NGÀY có dữ liệu, không theo số lần chạy.
    """

    if len(records) < window:
        return None

    values = [
        item["sjc_sell"]
        for item in records[-window:]
        if item["sjc_sell"] is not None
    ]

    if len(values) < window:
        return None

    return sum(values) / float(len(values))


def analyze_trend(history, sjc_sell_today, today_date):
    """
    Phân tích xu hướng dựa trên giá bán SJC.

    D-1:
        so với ngày có dữ liệu gần nhất trước hôm nay.

    D-7:
        so với đúng ngày cách hôm nay 7 ngày.

    SMA3/SMA7:
        tính trên dữ liệu theo ngày, bao gồm giá hôm nay.
    """

    if sjc_sell_today is None:
        return None

    today = parse_date(today_date)

    if today is None:
        return None

    # --------------------------------------------------------
    # Tạo dữ liệu phân tích = history + giá hôm nay.
    # Nếu hôm nay đã có record thì thay thế bằng giá mới nhất.
    # --------------------------------------------------------
    analysis_history = []

    for record in history:
        if record.get("date") == today_date:
            continue

        analysis_history.append(record)

    analysis_history.append({
        "date": today_date,
        "sjc_sell": sjc_sell_today,
    })

    analysis_history.sort(
        key=lambda item: item["date"]
    )

    # --------------------------------------------------------
    # D-1
    # --------------------------------------------------------
    previous_record = get_previous_available_record(
        analysis_history,
        today_date
    )

    previous_price = None
    previous_date = None

    if previous_record:
        previous_price = safe_float(
            previous_record.get("sjc_sell")
        )
        previous_date = previous_record.get("date")

    d1 = pct_change(
        sjc_sell_today,
        previous_price
    )

    # --------------------------------------------------------
    # D-7: đúng ngày cách 7 ngày
    # --------------------------------------------------------
    target_d7 = today - timedelta(days=7)

    d7_record = get_exact_date_record(
        analysis_history,
        target_d7.strftime("%Y-%m-%d")
    )

    d7_price = None
    d7_date = None

    if d7_record:
        d7_price = safe_float(
            d7_record.get("sjc_sell")
        )
        d7_date = d7_record.get("date")

    d7 = pct_change(
        sjc_sell_today,
        d7_price
    )

    # --------------------------------------------------------
    # SMA3 / SMA7
    # --------------------------------------------------------
    sjc_records = get_sjc_values(
        analysis_history
    )

    sma3 = compute_sma_from_records(
        sjc_records,
        3
    )

    sma7 = compute_sma_from_records(
        sjc_records,
        7
    )

    # --------------------------------------------------------
    # Tín hiệu
    # --------------------------------------------------------
    signal = "Chưa đủ dữ liệu lịch sử để đánh giá xu hướng"

    if sma3 is not None and sma7 is not None:
        upper_threshold = sma7 * 1.001
        lower_threshold = sma7 * 0.999

        if sma3 > upper_threshold:
            signal = (
                "Xu hướng ngắn hạn nghiêng về TĂNG "
                "(SMA3 > SMA7)"
            )

        elif sma3 < lower_threshold:
            signal = (
                "Xu hướng ngắn hạn nghiêng về GIẢM "
                "(SMA3 < SMA7)"
            )

        else:
            signal = (
                "Giá đang đi ngang, chưa rõ xu hướng "
                "(SMA3 gần SMA7)"
            )

    return {
        "d1_pct": d1,
        "d1_date": previous_date,
        "d7_pct": d7,
        "d7_date": d7_date,
        "sma3": sma3,
        "sma7": sma7,
        "signal": signal,
    }


# ============================================================
# QUY ĐỔI GIÁ THẾ GIỚI
# ============================================================

def convert_world_gold_to_vnd_per_luong(
    usd_per_oz,
    usd_vnd
):
    """
    Quy đổi XAU/USD sang VND/lượng.

    Công thức:
        USD/oz
        × troy oz/lượng
        × VND/USD
    """

    if not is_valid_positive_number(usd_per_oz):
        return None

    if not is_valid_positive_number(usd_vnd):
        return None

    return (
        usd_per_oz
        * OZ_PER_LUONG
        * usd_vnd
    )


# ============================================================
# ĐỊNH DẠNG TIN NHẮN TELEGRAM
# ============================================================

def build_message(
    now_str,
    world,
    usd_vnd,
    domestic,
    trend
):
    lines = []

    lines.append(
        "🥇 <b>BÁO CÁO GIÁ VÀNG</b> — %s"
        % html.escape(now_str)
    )

    lines.append("")

    # --------------------------------------------------------
    # Giá trong nước
    # --------------------------------------------------------
    lines.append(
        "💰 <b>Giá vàng trong nước</b>"
    )

    for brand in ("SJC", "DOJI", "PNJ"):
        data = domestic.get(brand)

        if data:
            lines.append(
                "• %s: mua %s — bán %s đ/lượng"
                % (
                    brand,
                    fmt_vnd(data["buy"]),
                    fmt_vnd(data["sell"])
                )
            )
        else:
            lines.append(
                "• %s: ⚠️ không lấy được dữ liệu lúc này"
                % brand
            )

    lines.append("")

    # --------------------------------------------------------
    # Giá thế giới
    # --------------------------------------------------------
    lines.append(
        "🌍 <b>Giá vàng thế giới</b>"
    )

    if world:
        world_price = world.get("usd_oz")
        world_change = world.get("change_pct")

        if world_change is not None:
            lines.append(
                "• XAU/USD: %s USD/oz (%s %.2f%% so với hôm qua)"
                % (
                    fmt_usd(world_price),
                    trend_arrow(world_change),
                    world_change
                )
            )
        else:
            lines.append(
                "• XAU/USD: %s USD/oz"
                % fmt_usd(world_price)
            )

        world_vnd_luong = convert_world_gold_to_vnd_per_luong(
            world_price,
            usd_vnd
        )

        if world_vnd_luong is not None:
            lines.append(
                "• Quy đổi ≈ %s đ/lượng (chưa thuế/phí)"
                % fmt_vnd(world_vnd_luong)
            )

            lines.append(
                "• Tỷ giá USD/VND: %s"
                % fmt_vnd(usd_vnd)
            )

            sjc = domestic.get("SJC")

            if sjc and sjc.get("sell") is not None:
                difference = (
                    sjc["sell"]
                    - world_vnd_luong
                )

                lines.append(
                    "📊 Chênh lệch SJC bán ra "
                    "so với giá thế giới quy đổi: %s đ/lượng"
                    % fmt_vnd(difference)
                )

        else:
            lines.append(
                "• ⚠️ Không thể quy đổi sang VND/lượng "
                "do thiếu tỷ giá hoặc giá thế giới."
            )

    else:
        lines.append(
            "• ⚠️ Không lấy được dữ liệu lúc này"
        )

    lines.append("")

    # --------------------------------------------------------
    # Xu hướng
    # --------------------------------------------------------
    lines.append(
        "📊 <b>Phân tích xu hướng "
        "(tham khảo, dựa trên giá SJC)</b>"
    )

    if trend:
        if trend.get("d1_pct") is not None:
            d1_label = "ngày trước đó"

            if trend.get("d1_date"):
                d1_label = trend["d1_date"]

            lines.append(
                "• So với %s: %s %.2f%%"
                % (
                    d1_label,
                    trend_arrow(trend["d1_pct"]),
                    trend["d1_pct"]
                )
            )
        else:
            lines.append(
                "• So với ngày trước đó: ➖ N/A"
            )

        if trend.get("d7_pct") is not None:
            lines.append(
                "• So với 7 ngày trước (%s): %s %.2f%%"
                % (
                    trend["d7_date"],
                    trend_arrow(trend["d7_pct"]),
                    trend["d7_pct"]
                )
            )
        else:
            lines.append(
                "• So với 7 ngày trước: ➖ Chưa đủ dữ liệu"
            )

        if trend.get("sma3") is not None:
            lines.append(
                "• SMA3: %s đ/lượng"
                % fmt_vnd(trend["sma3"])
            )

        if trend.get("sma7") is not None:
            lines.append(
                "• SMA7: %s đ/lượng"
                % fmt_vnd(trend["sma7"])
            )

        lines.append(
            "• Tín hiệu: %s"
            % trend["signal"]
        )

    else:
        lines.append(
            "• Chưa đủ dữ liệu để phân tích"
        )

    lines.append("")

    lines.append(
        "⚠️ <i>Đây chỉ là thông tin tham khảo dựa "
        "trên dữ liệu lịch sử đơn giản, không phải "
        "lời khuyên đầu tư. Vui lòng tự cân nhắc "
        "trước khi quyết định.</i>"
    )

    return "\n".join(lines)


# ============================================================
# TELEGRAM
# ============================================================

def send_telegram(message):
    if not TELEGRAM_BOT_TOKEN:
        raise RuntimeError(
            "Thiếu TELEGRAM_BOT_TOKEN."
        )

    if not TELEGRAM_CHAT_ID:
        raise RuntimeError(
            "Thiếu TELEGRAM_CHAT_ID."
        )

    url = (
        "https://api.telegram.org/bot%s/sendMessage"
        % TELEGRAM_BOT_TOKEN
    )

    response = requests.post(
        url,
        json={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        },
        timeout=REQUEST_TIMEOUT
    )

    if not response.ok:
        raise RuntimeError(
            "Gửi Telegram thất bại: %s %s"
            % (
                response.status_code,
                response.text
            )
        )

    print(
        "Đã gửi báo cáo Telegram thành công."
    )


# ============================================================
# MAIN
# ============================================================

def main():
    # --------------------------------------------------------
    # Thời gian hiện tại theo Việt Nam
    # --------------------------------------------------------
    now_vn = datetime.now(VN_TZ)

    today_date = now_vn.strftime(
        "%Y-%m-%d"
    )

    now_str = now_vn.strftime(
        "%H:%M %d/%m/%Y"
    )

    print(
        "Bắt đầu chạy bot: %s"
        % now_str
    )

    # --------------------------------------------------------
    # 1. Lấy dữ liệu
    # --------------------------------------------------------
    world = fetch_world_gold()
    usd_vnd = fetch_usd_vnd_rate()

    domestic = {}

    for brand, url in DOMESTIC_SOURCES.items():
        domestic[brand] = fetch_domestic_brand(
            brand,
            url
        )

    # --------------------------------------------------------
    # 2. Đọc history
    # --------------------------------------------------------
    history = load_history()

    # --------------------------------------------------------
    # 3. Giá SJC hiện tại
    # --------------------------------------------------------
    sjc = domestic.get("SJC")

    sjc_sell_today = None

    if sjc:
        sjc_sell_today = safe_float(
            sjc.get("sell")
        )

    # --------------------------------------------------------
    # 4. Phân tích trước khi lưu record hôm nay
    # --------------------------------------------------------
    trend = analyze_trend(
        history,
        sjc_sell_today,
        today_date
    )

    # --------------------------------------------------------
    # 5. Tạo/cập nhật record hôm nay
    # --------------------------------------------------------
    today_record = {
        "date": today_date,
        "sjc_buy": (
            safe_float(sjc.get("buy"))
            if sjc else None
        ),
        "sjc_sell": sjc_sell_today,
        "world_usd_oz": (
            safe_float(world.get("usd_oz"))
            if world else None
        ),
        "usd_vnd": safe_float(usd_vnd),
    }

    history = upsert_today_record(
        history,
        today_record
    )

    # --------------------------------------------------------
    # 6. Lưu history TRƯỚC khi gửi Telegram
    # --------------------------------------------------------
    try:
        save_history(
            history,
            today_date
        )

        print(
            "Đã lưu history: %s"
            % HISTORY_FILE
        )

    except Exception as error:
        print(
            "[LỖI] Không thể lưu history: %s"
            % error,
            file=sys.stderr
        )

    # --------------------------------------------------------
    # 7. Tạo message
    # --------------------------------------------------------
    message = build_message(
        now_str,
        world,
        usd_vnd,
        domestic,
        trend
    )

    # --------------------------------------------------------
    # 8. Gửi Telegram
    # --------------------------------------------------------
    send_telegram(message)


if __name__ == "__main__":
    try:
        main()

    except KeyboardInterrupt:
        print(
            "Bot bị dừng bởi người dùng."
        )
        sys.exit(130)

    except Exception as error:
        print(
            "[LỖI NGHIÊM TRỌNG] %s"
            % error,
            file=sys.stderr
        )
        sys.exit(1)
