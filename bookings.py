"""預約資料的驗證。價格一律由伺服器依目前的價目表重新計算，不信任前端傳來的金額。"""
import re
import secrets
from datetime import datetime, timedelta, timezone

import pricing

TAIPEI = timezone(timedelta(hours=8))          # 台灣沒有日光節約時間，固定 +8 即可
_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def now_taipei():
    return datetime.now(TAIPEI)


def new_order_no():
    return "HY" + now_taipei().strftime("%Y%m%d%H%M%S") + secrets.token_hex(2).upper()


def _text(value):
    if value is None:
        return ""
    if isinstance(value, (dict, list, bool)):
        return None
    return _CONTROL_CHARS.sub("", str(value)).strip()


def _int(value):
    if isinstance(value, bool):
        return None
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def validate_booking(data, sheet, today=None):
    """回傳 (整理好的資料, 錯誤訊息清單)。有錯誤時整理好的資料不可使用。"""
    errors = []
    clean = {}
    today = today or now_taipei().date()

    def field(key, label, maxlen, required=True):
        raw = _text(data.get(key))
        if raw is None:
            errors.append(f"{label}格式不正確")
            return ""
        if required and not raw:
            errors.append(f"請填寫{label}")
        if len(raw) > maxlen:
            errors.append(f"{label}太長（最多 {maxlen} 字）")
        return raw

    # 行程：這四項決定價格，必須和目前的價目表對得上
    direction = _text(data.get("dir"))
    airport_id = _text(data.get("airport"))
    vehicle_id = _text(data.get("vehicle"))
    area_name = _text(data.get("area"))
    price = None
    try:
        price = pricing.quote(sheet, airport_id, vehicle_id, area_name, direction)
        clean["service_type"] = pricing.DIR_LABEL[direction]
        clean["airport"] = pricing.find_airport(sheet, airport_id)["name"]
        clean["vehicle"] = pricing.find_vehicle(sheet, vehicle_id)["name"]
        clean["area"] = area_name
        clean["price"] = price
    except pricing.PriceError as exc:
        errors.append(f"行程資料有誤：{exc}")

    # 乘客資料
    clean["name"] = field("name", "姓名", 80)
    phone = field("phone", "聯絡電話", 30)
    digits = re.sub(r"\D", "", phone)
    if phone and (not re.fullmatch(r"[0-9+\-()\s]+", phone) or not 7 <= len(digits) <= 15):
        errors.append("聯絡電話格式不正確")
    clean["phone"] = phone
    clean["address"] = field("address", "地址", 300)
    clean["flight"] = field("flight", "航班", 30, required=False)
    clean["note"] = field("note", "備註", 500, required=False)

    # 日期與時間
    date_text = _text(data.get("date")) or ""
    try:
        day = datetime.strptime(date_text, "%Y-%m-%d").date()
        if day < today:
            errors.append("日期不能早於今天")
        elif day > today + timedelta(days=730):
            errors.append("日期太遠，請確認是否正確")
    except ValueError:
        errors.append("請填寫正確的日期")
    clean["date"] = date_text
    time_text = _text(data.get("time")) or ""
    try:
        datetime.strptime(time_text, "%H:%M")
    except ValueError:
        errors.append("請填寫正確的時間")
    clean["time"] = time_text

    # 人數與行李
    passengers = _int(data.get("passengers"))
    if passengers is None or not 1 <= passengers <= 9:
        errors.append("人數必須是 1 到 9")
    clean["passengers"] = passengers
    luggage = _int(data.get("luggage")) if str(data.get("luggage", "")).strip() else 0
    if luggage is None or not 0 <= luggage <= 20:
        errors.append("行李數必須是 0 到 20")
    clean["luggage"] = luggage
    return clean, errors
