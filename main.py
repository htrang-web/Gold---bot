#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bot theo dõi giá vàng (trong nước + thế giới) và gửi báo cáo qua Telegram.
Chạy định kỳ bằng GitHub Actions (xem .github/workflows/gold-price.yml).

PHIÊN BẢN 2 — LỊCH SỬ THAY ĐỔI:
Bản đầu dùng sjc.com.vn (qua thư viện vnstock), goldprice.org và api.btmc.vn
làm nguồn dữ liệu. Khi chạy thật trên GitHub Actions, cả 3 nguồn này đều lỗi:
- sjc.com.vn & goldprice.org: trả về 403 Forbidden — các trang này chặn theo
  dải IP của các nhà cung cấp cloud (Azure/AWS/GCP), mà GitHub Actions runner
  chạy trên Azure nên bị chặn, KHÔNG liên quan tới code.
- api.btmc.vn: connection timeout — máy chủ không phản hồi được từ ngoài VN.
Bản 2 này chuyển sang các nguồn thân thiện với việc lấy dữ liệu tự động hơn:
- Giá thế giới (XAU/USD): Stooq.com — nguồn dữ liệu tài chính phổ biến, hầu
  như không chặn theo IP.
- Giá trong nước (SJC/DOJI/PNJ): giavang.org — trang tổng hợp có định dạng
  văn bản ổn định, dễ phân tích, gom đủ cả 3 thương hiệu bạn cần so sánh.
- Thêm cơ chế "proxy dự phòng" (allorigins.win): nếu gọi trực tiếp vẫn bị
  chặn/lỗi, script tự động thử lại qua proxy trung gian trước khi bỏ cuộc.

LƯU Ý QUAN TRỌNG:
- Đây đều là nguồn không chính thức (không phải API do SJC/DOJI/PNJ công bố),
  nên CÓ THỂ thay đổi cấu trúc hoặc ngừng hoạt động bất cứ lúc nào. Mọi hàm
  lấy dữ liệu đều được bọc try/except: nếu 1 nguồn lỗi, bot vẫn gửi báo cáo
  với các nguồn còn lại thay vì crash hoàn toàn.
- Đây KHÔNG phải là lời khuyên đầu tư. "Tín hiệu xu hướng" trong báo cáo chỉ
  mang tính tham khảo dựa trên dữ liệu lịch sử đơn giản.
"""

import csv
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

HISTORY_FILE = os.path.join(os.path.dirname(__file__), "history.json")
MAX_HISTORY_DAYS = 90  # chỉ giữ lại 90 ngày gần nhất để file không phình to

VN_TZ = timezone(timedelta(hours=7))

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
}

REQUEST_TIMEOUT = 15  # giây

# Trang giá vàng tổng hợp — có sẵn cả SJC, DOJI, PNJ với định dạng ổn định
DOMESTIC_SOURCES = {
    "SJC": "https://giavang.org/trong-nuoc/sjc/",
    "DOJI": "https://giavang.org/trong-nuoc/doji/",
    "PNJ": "https://giavang.org/trong-nuoc/pnj/",
}


# ============================================================
# HTTP HELPER — có cơ chế proxy dự phòng khi bị chặn/lỗi
# ============================================================

def smart_get(url, timeout=REQUEST_TIMEOUT, use_proxy_fallback=True):
    """Gọi GET tới url. Nếu lỗi (bị chặn 403, timeout...) và use_proxy_fallback=True,
    thử lại 1 lần qua proxy trung gian (allorigins.win) trước khi báo lỗi."""
    try:
        r = requests.get(url, headers=HEADERS, timeout=timeout)
        if r.status_code == 200:
            return r
        raise requests.exceptions.HTTPError(f"HTTP {r.status_code} cho {url}")
    except Exception as direct_err:
        if not use_proxy_fallback:
            raise
        try:
            proxy_url = "https://api.allorigins.win/raw?url=" + quote(url, safe="")
            r2 = requests.get(proxy_url, headers=HEADERS, timeout=timeout + 10)
            r2.raise_for_status()
            return r2
        except Exception as proxy_err:
            raise RuntimeError(
                f"gọi trực tiếp lỗi ({direct_err}); gọi qua proxy cũng lỗi ({proxy_err})"
            )


# ============================================================
# CÁC HÀM LẤY DỮ LIỆU
# ============================================================

def fetch_world_gold():
    """Lấy giá vàng thế giới (USD/oz). Ưu tiên Stooq (ít bị chặn IP cloud),
    dự phòng bằng goldprice.org nếu Stooq lỗi."""
    # --- Nguồn chính: Stooq (dùng endpoint tải dữ liệu lịch sử, ổn định hơn
    # endpoint "quote" q/l/ vốn hay đổi/trả 404) ---
    try:
        r = smart_get("https://stooq.com/q/d/l/?s=xauusd&i=d")
        rows = list(csv.DictReader(io.StringIO(r.text.strip())))
        if rows:
            last = rows[-1]  # dòng cuối = phiên gần nhất
            close = float(last["Close"])
            if close > 0:
                return {"usd_oz": close, "change_pct": None}
    except Exception as e:
        print(f"[LỖI] fetch_world_gold (Stooq): {e}", file=sys.stderr)

    # --- Dự phòng: goldprice.org ---
    try:
        r = smart_get("https://data-asg.goldprice.org/dbXRates/USD")
        data = r.json()
        item = data["items"][0]
        return {
            "usd_oz": float(item["xauPrice"]),
            "change_pct": float(item.get("pcXau", 0)),
        }
    except Exception as e:
        print(f"[LỖI] fetch_world_gold (goldprice.org): {e}", file=sys.stderr)
        return None


def fetch_usd_vnd_rate():
    """Lấy tỷ giá USD/VND từ open.er-api.com (API công khai, không cần key)."""
    try:
        r = smart_get("https://open.er-api.com/v6/latest/USD")
        data = r.json()
        return float(data["rates"]["VND"])
    except Exception as e:
        print(f"[LỖI] fetch_usd_vnd_rate: {e}", file=sys.stderr)
        return None


_PRICE_PATTERN = re.compile(
    r"Mua\s*vào\s*([\d.,]+)\s*x1000đ/lượng.*?Bán\s*ra\s*([\d.,]+)\s*x1000đ/lượng",
    re.IGNORECASE | re.DOTALL,
)


def fetch_domestic_brand(brand_name, url):
    """Lấy giá mua/bán của 1 thương hiệu vàng (SJC/DOJI/PNJ) từ trang tổng hợp
    giavang.org. Trang này hiển thị giá theo dạng: 'Mua vào 137.400 x1000đ/lượng
    ... Bán ra 141.400 x1000đ/lượng' ngay đầu trang — ta dùng regex để lấy ra."""
    try:
        r = smart_get(url)
        soup = BeautifulSoup(r.text, "lxml")
        text = soup.get_text(" ", strip=True)
        match = _PRICE_PATTERN.search(text)
        if not match:
            print(f"[LỖI] fetch_domestic_brand({brand_name}): không tìm thấy mẫu giá trong trang",
                  file=sys.stderr)
            return None
        buy_raw, sell_raw = match.group(1), match.group(2)
        buy = float(buy_raw.replace(".", "").replace(",", "")) * 1000
        sell = float(sell_raw.replace(".", "").replace(",", "")) * 1000
        if buy <= 0 or sell <= 0:
            return None
        return {"name": brand_name, "buy": buy, "sell": sell}
    except Exception as e:
        print(f"[LỖI] fetch_domestic_brand({brand_name}): {e}", file=sys.stderr)
        return None


# ============================================================
# LỊCH SỬ & PHÂN TÍCH XU HƯỚNG
# ============================================================

def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []


def save_history(history):
    history = history[-MAX_HISTORY_DAYS:]
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)


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


def compute_sma(values, window):
    vals = [v for v in values[-window:] if v is not None]
    if not vals:
        return None
    return sum(vals) / len(vals)


def analyze_trend(history, sjc_sell_today):
    """So sánh giá SJC hôm nay với hôm qua, 7 ngày trước, và tính SMA7/SMA3
    để đưa ra một 'tín hiệu' xu hướng đơn giản, mang tính tham khảo."""
    if sjc_sell_today is None:
        return None

    closes = [h.get("sjc_sell") for h in history if h.get("sjc_sell") is not None]

    yesterday = closes[-1] if len(closes) >= 1 else None
    week_ago = closes[-7] if len(closes) >= 7 else None

    d1 = pct_change(sjc_sell_today, yesterday)
    d7 = pct_change(sjc_sell_today, week_ago)

    sma3 = compute_sma(closes, 3)
    sma7 = compute_sma(closes, 7)

    signal = "Chưa đủ dữ liệu lịch sử để đánh giá xu hướng"
    if sma3 is not None and sma7 is not None:
        if sma3 > sma7 * 1.001:
            signal = "Xu hướng ngắn hạn nghiêng về TĂNG (SMA3 > SMA7)"
        elif sma3 < sma7 * 0.999:
            signal = "Xu hướng ngắn hạn nghiêng về GIẢM (SMA3 < SMA7)"
        else:
            signal = "Giá đang đi ngang, chưa rõ xu hướng"

    return {
        "d1_pct": d1,
        "d7_pct": d7,
        "sma3": sma3,
        "sma7": sma7,
        "signal": signal,
    }


# ============================================================
# ĐỊNH DẠNG TIN NHẮN
# ============================================================

def fmt_vnd(x):
    if x is None:
        return "N/A"
    return f"{x:,.0f}".replace(",", ".")


def build_message(now_str, world, usd_vnd, domestic, trend):
    lines = []
    lines.append(f"🥇 <b>BÁO CÁO GIÁ VÀNG</b> — {now_str}")
    lines.append("")

    # --- Giá trong nước ---
    lines.append("💰 <b>Giá vàng trong nước</b>")
    for brand in ("SJC", "DOJI", "PNJ"):
        d = domestic.get(brand)
        if d:
            lines.append(f"• {brand}: mua {fmt_vnd(d['buy'])} — bán {fmt_vnd(d['sell'])} đ/lượng")
        else:
            lines.append(f"• {brand}: ⚠️ không lấy được dữ liệu lúc này")

    lines.append("")

    # --- Giá thế giới ---
    lines.append("🌍 <b>Giá vàng thế giới</b>")
    if world:
        if world["change_pct"] is not None:
            arrow = trend_arrow(world["change_pct"])
            lines.append(
                f"• XAU/USD: {world['usd_oz']:,.2f} USD/oz "
                f"({arrow} {world['change_pct']:+.2f}% so với hôm qua)"
            )
        else:
            lines.append(f"• XAU/USD: {world['usd_oz']:,.2f} USD/oz")

        if usd_vnd:
            oz_per_luong = 1.20556  # 1 lượng = 1.20556 troy oz
            world_vnd_luong = world["usd_oz"] * oz_per_luong * usd_vnd
            lines.append(f"• Quy đổi ≈ {fmt_vnd(world_vnd_luong)} đ/lượng (chưa thuế/phí)")
            lines.append(f"• Tỷ giá USD/VND: {usd_vnd:,.0f}")

            sjc = domestic.get("SJC")
            if sjc:
                premium = sjc["sell"] - world_vnd_luong
                lines.append(f"📊 Chênh lệch SJC vs thế giới: {fmt_vnd(premium)} đ/lượng")
    else:
        lines.append("• ⚠️ không lấy được dữ liệu lúc này")

    lines.append("")

    # --- Xu hướng ---
    lines.append("📊 <b>Phân tích xu hướng (tham khảo, dựa trên giá SJC)</b>")
    if trend:
        if trend["d1_pct"] is not None:
            lines.append(f"• So với hôm qua: {trend_arrow(trend['d1_pct'])} {trend['d1_pct']:+.2f}%")
        if trend["d7_pct"] is not None:
            lines.append(f"• So với 7 ngày trước: {trend_arrow(trend['d7_pct'])} {trend['d7_pct']:+.2f}%")
        lines.append(f"• Tín hiệu: {trend['signal']}")
    else:
        lines.append("• Chưa đủ dữ liệu để phân tích")

    lines.append("")
    lines.append(
        "⚠️ <i>Đây chỉ là thông tin tham khảo dựa trên dữ liệu lịch sử đơn giản, "
        "không phải lời khuyên đầu tư. Vui lòng tự cân nhắc trước khi quyết định.</i>"
    )

    return "\n".join(lines)


# ============================================================
# GỬI TELEGRAM
# ============================================================

def send_telegram(message):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("[LỖI] Thiếu TELEGRAM_BOT_TOKEN hoặc TELEGRAM_CHAT_ID trong biến môi trường/secrets.",
              file=sys.stderr)
        sys.exit(1)

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    resp = requests.post(url, json={
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }, timeout=REQUEST_TIMEOUT)

    if not resp.ok:
        print(f"[LỖI] Gửi Telegram thất bại: {resp.status_code} {resp.text}", file=sys.stderr)
        sys.exit(1)
    print("Đã gửi báo cáo Telegram thành công.")


# ============================================================
# MAIN
# ============================================================

def main():
    now_vn = datetime.now(VN_TZ)
    now_str = now_vn.strftime("%H:%M %d/%m/%Y")

    world = fetch_world_gold()
    usd_vnd = fetch_usd_vnd_rate()

    domestic = {}
    for brand, url in DOMESTIC_SOURCES.items():
        domestic[brand] = fetch_domestic_brand(brand, url)

    history = load_history()
    sjc_sell_today = domestic["SJC"]["sell"] if domestic.get("SJC") else None
    trend = analyze_trend(history, sjc_sell_today)

    message = build_message(now_str, world, usd_vnd, domestic, trend)
    send_telegram(message)

    # Lưu lại dữ liệu hôm nay vào lịch sử để tính xu hướng cho các lần sau
    today_record = {
        "date": now_vn.strftime("%Y-%m-%d"),
        "sjc_buy": domestic["SJC"]["buy"] if domestic.get("SJC") else None,
        "sjc_sell": sjc_sell_today,
        "world_usd_oz": world["usd_oz"] if world else None,
        "usd_vnd": usd_vnd,
    }
    history.append(today_record)
    save_history(history)


if __name__ == "__main__":
    main()
