#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bot theo dõi giá vàng (trong nước + thế giới) và gửi báo cáo qua Telegram.
Được thiết kế để chạy định kỳ bằng GitHub Actions (xem .github/workflows/gold-price.yml).

Nguồn dữ liệu:
- Vàng SJC & các thương hiệu khác (BTMC tổng hợp nhiều loại): thư viện vnstock
  (https://github.com/thinh-vu/vnstock) - đây là thư viện mã nguồn mở được bảo trì
  tích cực, lấy dữ liệu chính thức từ SJC.
- Vàng DOJI: API công khai (không chính thức) của giavang.doji.vn
- Vàng PNJ: cào dữ liệu (scrape) từ trang giavang.pnj.com.vn (best-effort)
- Giá vàng thế giới (XAU/USD): API công khai miễn phí của goldprice.org
- Tỷ giá USD/VND: API công khai miễn phí open.er-api.com

LƯU Ý QUAN TRỌNG:
- DOJI và PNJ không có API chính thức công khai, script phải "cào" dữ liệu (scrape)
  từ các endpoint không chính thức. Các endpoint này CÓ THỂ thay đổi hoặc ngừng hoạt
  động bất cứ lúc nào mà không báo trước, khiến nguồn đó tạm thời không lấy được dữ
  liệu. Vì vậy mọi hàm lấy dữ liệu đều được bọc trong try/except: nếu 1 nguồn lỗi,
  bot vẫn gửi báo cáo với các nguồn còn lại thay vì bị crash hoàn toàn.
- Đây KHÔNG phải là lời khuyên đầu tư. Các "tín hiệu xu hướng" trong báo cáo chỉ mang
  tính tham khảo dựa trên dữ liệu lịch sử đơn giản, không phải khuyến nghị tài chính.
"""

import json
import os
import sys
from datetime import datetime, timezone, timedelta

import requests

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
    )
}

REQUEST_TIMEOUT = 10  # giây


# ============================================================
# CÁC HÀM LẤY DỮ LIỆU
# ============================================================

def fetch_world_gold():
    """Lấy giá vàng thế giới (USD/oz) từ goldprice.org (API công khai, không cần key)."""
    try:
        r = requests.get(
            "https://data-asg.goldprice.org/dbXRates/USD",
            headers=HEADERS, timeout=REQUEST_TIMEOUT,
        )
        r.raise_for_status()
        data = r.json()
        item = data["items"][0]
        return {
            "usd_oz": float(item["xauPrice"]),
            "change_pct": float(item.get("pcXau", 0)),
        }
    except Exception as e:
        print(f"[LỖI] fetch_world_gold: {e}", file=sys.stderr)
        return None


def fetch_usd_vnd_rate():
    """Lấy tỷ giá USD/VND từ open.er-api.com (API công khai, không cần key)."""
    try:
        r = requests.get(
            "https://open.er-api.com/v6/latest/USD",
            headers=HEADERS, timeout=REQUEST_TIMEOUT,
        )
        r.raise_for_status()
        data = r.json()
        return float(data["rates"]["VND"])
    except Exception as e:
        print(f"[LỖI] fetch_usd_vnd_rate: {e}", file=sys.stderr)
        return None


def fetch_sjc():
    """Lấy giá vàng SJC qua thư viện vnstock."""
    try:
        from vnstock.explorer.misc.gold_price import sjc_gold_price
        df = sjc_gold_price()
        if df is None or len(df) == 0:
            return None
        row = df.iloc[0]
        return {
            "buy": float(row.get("buy_price", 0)),
            "sell": float(row.get("sell_price", 0)),
            "name": str(row.get("name", "Vàng SJC")),
        }
    except Exception as e:
        print(f"[LỖI] fetch_sjc: {e}", file=sys.stderr)
        return None


def fetch_btmc():
    """Lấy bảng giá vàng Bảo Tín Minh Châu (nhiều loại vàng) qua vnstock."""
    try:
        from vnstock.explorer.misc.gold_price import btmc_goldprice
        df = btmc_goldprice()
        if df is None or len(df) == 0:
            return None
        results = []
        for _, row in df.iterrows():
            results.append({
                "name": str(row.get("name", "")),
                "buy": float(row.get("buy_price", 0)),
                "sell": float(row.get("sell_price", 0)),
            })
        return results
    except Exception as e:
        print(f"[LỖI] fetch_btmc: {e}", file=sys.stderr)
        return None


def fetch_doji():
    """Lấy giá vàng DOJI qua API công khai (không chính thức) của giavang.doji.vn.
    Best-effort: nguồn này có thể đổi cấu trúc hoặc chặn request bất kỳ lúc nào."""
    try:
        r = requests.get(
            "http://giavang.doji.vn/api/giavang/?api_key=258fbd2a72ce8481089d88c678e9fe4f",
            headers=HEADERS, timeout=REQUEST_TIMEOUT,
        )
        r.raise_for_status()
        data = r.json()
        rows = data.get("Data", {}).get("Group", [])
        # Tìm dòng vàng SJC/nhẫn tại khu vực Hà Nội hoặc HCM trong bảng DOJI
        for group in rows:
            items = group.get("Item", [])
            for item in items:
                name = item.get("Name", "")
                if "SJC" in name.upper() or "NHẪN" in name.upper() or "9999" in name:
                    buy = item.get("Buy") or item.get("BuyValue")
                    sell = item.get("Sell") or item.get("SellValue")
                    if buy and sell:
                        return {
                            "name": name,
                            "buy": float(str(buy).replace(",", "")) * 1000,
                            "sell": float(str(sell).replace(",", "")) * 1000,
                        }
        return None
    except Exception as e:
        print(f"[LỖI] fetch_doji (nguồn có thể đang thay đổi cấu trúc): {e}", file=sys.stderr)
        return None


def fetch_pnj():
    """Lấy giá vàng PNJ bằng cách cào (scrape) trang giavang.pnj.com.vn.
    Best-effort: PNJ không có API JSON công khai ổn định, nên hàm này dễ lỗi nhất
    trong số các nguồn. Nếu lỗi, bot sẽ bỏ qua nguồn này trong báo cáo."""
    try:
        from bs4 import BeautifulSoup
        r = requests.get(
            "https://giavang.pnj.com.vn/",
            headers=HEADERS, timeout=REQUEST_TIMEOUT,
        )
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "lxml")
        text = soup.get_text(" ", strip=True)
        # Việc cào HTML thô rất dễ vỡ khi PNJ đổi giao diện, nên ở đây ta không
        # cố gắng phân tích chi tiết mà để ngỏ - khuyến khích thay bằng API ổn định
        # hơn nếu tìm được trong tương lai.
        return None  # Hiện tại chưa có cách bóc tách tin cậy, xem ghi chú trong README
    except Exception as e:
        print(f"[LỖI] fetch_pnj: {e}", file=sys.stderr)
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
    """Trả về icon xu hướng dựa trên % thay đổi."""
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


def build_message(now_str, world, usd_vnd, sjc, btmc, doji, trend):
    lines = []
    lines.append(f"🥇 <b>BÁO CÁO GIÁ VÀNG</b> — {now_str}")
    lines.append("")

    # --- Giá trong nước ---
    lines.append("💰 <b>Giá vàng trong nước</b>")
    if sjc:
        lines.append(
            f"• SJC: mua {fmt_vnd(sjc['buy'])} — bán {fmt_vnd(sjc['sell'])} đ/lượng"
        )
    else:
        lines.append("• SJC: ⚠️ không lấy được dữ liệu lúc này")

    if doji:
        lines.append(
            f"• DOJI: mua {fmt_vnd(doji['buy'])} — bán {fmt_vnd(doji['sell'])} đ/lượng"
        )
    else:
        lines.append("• DOJI: ⚠️ không lấy được dữ liệu lúc này")

    if btmc:
        # chỉ hiện 1-2 dòng tiêu biểu (vàng miếng SJC & nhẫn tròn) để tin nhắn gọn
        shown = 0
        for item in btmc:
            if shown >= 2:
                break
            if item["buy"] and item["sell"]:
                lines.append(
                    f"• {item['name']}: mua {fmt_vnd(item['buy'])} — "
                    f"bán {fmt_vnd(item['sell'])} đ/lượng"
                )
                shown += 1

    lines.append("")

    # --- Giá thế giới ---
    lines.append("🌍 <b>Giá vàng thế giới</b>")
    if world:
        arrow = trend_arrow(world["change_pct"])
        lines.append(
            f"• XAU/USD: {world['usd_oz']:,.2f} USD/oz "
            f"({arrow} {world['change_pct']:+.2f}% so với hôm qua)"
        )
        if usd_vnd:
            # quy đổi tương đối: 1 lượng = 1.20556 oz troy
            oz_per_luong = 1.20556
            world_vnd_luong = world["usd_oz"] * oz_per_luong * usd_vnd
            lines.append(f"• Quy đổi ≈ {fmt_vnd(world_vnd_luong)} đ/lượng (chưa thuế/phí)")
            lines.append(f"• Tỷ giá USD/VND: {usd_vnd:,.0f}")

            if sjc:
                premium = sjc["sell"] - world_vnd_luong
                lines.append(
                    f"📊 Chênh lệch SJC vs thế giới: {fmt_vnd(premium)} đ/lượng"
                )
    else:
        lines.append("• ⚠️ không lấy được dữ liệu lúc này")

    lines.append("")

    # --- Xu hướng ---
    lines.append("📊 <b>Phân tích xu hướng (tham khảo)</b>")
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
    sjc = fetch_sjc()
    btmc = fetch_btmc()
    doji = fetch_doji()
    # pnj = fetch_pnj()  # tạm thời chưa ổn định, xem README

    history = load_history()
    trend = analyze_trend(history, sjc["sell"] if sjc else None)

    message = build_message(now_str, world, usd_vnd, sjc, btmc, doji, trend)
    send_telegram(message)

    # Lưu lại dữ liệu hôm nay vào lịch sử để tính xu hướng cho các lần sau
    today_record = {
        "date": now_vn.strftime("%Y-%m-%d"),
        "sjc_buy": sjc["buy"] if sjc else None,
        "sjc_sell": sjc["sell"] if sjc else None,
        "world_usd_oz": world["usd_oz"] if world else None,
        "usd_vnd": usd_vnd,
    }
    history.append(today_record)
    save_history(history)


if __name__ == "__main__":
    main()
