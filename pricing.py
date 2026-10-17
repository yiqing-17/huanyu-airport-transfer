"""價目資料：驗證、查價、修改、比對。

價目資料的格式和 site/data/prices.json 完全相同，前台網站直接讀取，所以這裡的驗證
要比一般表單嚴格：價格錯了，客人看到的就是錯的價格。

價格陣列的順序固定是 [送機, 接機]。
"""
import copy
import json
import re

MIN_PRICE = 1
MAX_PRICE = 200_000

DIRS = ("send", "pickup")
DIR_INDEX = {"send": 0, "pickup": 1}
DIR_LABEL = {"send": "送機", "pickup": "接機"}

# 單次修改超過這個比例就提醒（常見的是多打或少打一個 0）
BIG_CHANGE_RATIO = 0.5


class PriceError(ValueError):
    """價目資料或查價參數有問題。訊息可以直接顯示給使用者。"""


def _is_price(value):
    return (
        isinstance(value, int)
        and not isinstance(value, bool)
        and MIN_PRICE <= value <= MAX_PRICE
    )


# ------------------------------------------------------------------ 驗證 ----


def validate_sheet(sheet):
    """檢查整份價目資料，回傳錯誤訊息清單（空清單代表沒問題）。"""
    if not isinstance(sheet, dict):
        return ["價目資料格式錯誤"]

    errors = []
    vehicles = sheet.get("vehicles")
    airports = sheet.get("airports")
    if not isinstance(vehicles, list) or not vehicles:
        errors.append("缺少車型資料")
    if not isinstance(airports, list) or not airports:
        errors.append("缺少機場資料")
    if errors:
        return errors

    vehicle_ids = []
    for v in vehicles:
        if not isinstance(v, dict) or not v.get("id") or not v.get("name"):
            errors.append("有車型缺少 id 或名稱")
            continue
        vehicle_ids.append(v["id"])
    if len(set(vehicle_ids)) != len(vehicle_ids):
        errors.append("車型 id 重複")

    airport_ids = set()
    for ap in airports:
        if not isinstance(ap, dict) or not ap.get("id") or not ap.get("name"):
            errors.append("有機場缺少 id 或名稱")
            continue
        label = ap["name"]
        if ap["id"] in airport_ids:
            errors.append(f"機場 id 重複：{ap['id']}")
        airport_ids.add(ap["id"])

        names = set()
        for group in ap.get("groups") or []:
            for area in group.get("areas") or []:
                name = area.get("name")
                if not name:
                    errors.append(f"{label} 有地區缺少名稱")
                    continue
                if name in names:
                    errors.append(f"{label} 的地區名稱重複：{name}")
                names.add(name)

                prices = area.get("prices")
                if not isinstance(prices, dict) or set(prices) != set(vehicle_ids):
                    errors.append(f"{label}｜{name}：車型價格不完整")
                    continue
                for vid, pair in prices.items():
                    ok = isinstance(pair, list) and len(pair) == 2 and all(_is_price(p) for p in pair)
                    if not ok:
                        errors.append(
                            f"{label}｜{name}｜{vid}：價格必須是 [送機, 接機]，"
                            f"且為 {MIN_PRICE} 到 {MAX_PRICE} 的整數"
                        )
        if not names:
            errors.append(f"{label} 沒有任何地區")

        premium = ap.get("premium")
        if premium is not None:
            rows = premium.get("rows") if isinstance(premium, dict) else None
            if not isinstance(rows, list) or not all(
                isinstance(r, list) and len(r) == 2 and r[0] and _is_price(r[1]) for r in rows
            ):
                errors.append(f"{label} 的尊爵車價格格式錯誤")
    return errors


# ------------------------------------------------------------------ 查找 ----


def areas_of(airport):
    return [a for g in airport["groups"] for a in g["areas"]]


def find_airport(sheet, airport_id):
    for ap in sheet["airports"]:
        if ap["id"] == airport_id:
            return ap
    raise PriceError("找不到這個機場")


def find_vehicle(sheet, vehicle_id):
    for v in sheet["vehicles"]:
        if v["id"] == vehicle_id:
            return v
    raise PriceError("找不到這個車型")


def find_area(sheet, airport_id, area_name):
    for area in areas_of(find_airport(sheet, airport_id)):
        if area["name"] == area_name:
            return area
    raise PriceError("找不到這個地區")


def quote(sheet, airport_id, vehicle_id, area_name, direction):
    """查單趟價格。direction 是 'send'（送機）或 'pickup'（接機）。"""
    if direction not in DIR_INDEX:
        raise PriceError("服務類型不正確")
    find_vehicle(sheet, vehicle_id)
    area = find_area(sheet, airport_id, area_name)
    return area["prices"][vehicle_id][DIR_INDEX[direction]]


def price_rows(sheet, airport_id, vehicle_id):
    """後台價格表要顯示的列：依機場內的順序，附上分組名稱。"""
    find_vehicle(sheet, vehicle_id)
    rows = []
    index = 0
    for group in find_airport(sheet, airport_id)["groups"]:
        for area in group["areas"]:
            send, pickup = area["prices"][vehicle_id]
            rows.append({"index": index, "group": group["name"], "name": area["name"],
                         "send": send, "pickup": pickup})
            index += 1
    return rows


# ------------------------------------------------------------------ 修改 ----


def parse_price(text):
    """把表單輸入轉成價格；不合法就丟出 PriceError。"""
    cleaned = re.sub(r"[,\s]", "", str(text or ""))
    if not re.fullmatch(r"\d{1,7}", cleaned):
        raise PriceError("請輸入整數")
    value = int(cleaned)
    if not _is_price(value):
        raise PriceError(f"價格必須在 {MIN_PRICE} 到 {MAX_PRICE} 之間")
    return value


def apply_prices(sheet, airport_id, vehicle_id, updates):
    """依 updates 修改某機場、某車型的價格，回傳新的價目資料（不改動原本的）。

    updates 的格式是 {列的順序: (送機, 接機)}，順序和 price_rows() 一致。
    """
    new_sheet = copy.deepcopy(sheet)
    find_vehicle(new_sheet, vehicle_id)
    areas = areas_of(find_airport(new_sheet, airport_id))
    for index, (send, pickup) in updates.items():
        if not 0 <= index < len(areas):
            raise PriceError("價格表的列數不符，請重新整理頁面")
        if not (_is_price(send) and _is_price(pickup)):
            raise PriceError("價格不合法")
        areas[index]["prices"][vehicle_id] = [send, pickup]
    return new_sheet


# ------------------------------------------------------------------ 比對 ----


def _flatten(sheet):
    flat = {}
    for ap in sheet.get("airports", []):
        for area in areas_of(ap):
            for vid, pair in area["prices"].items():
                for i, field in enumerate(("send", "pickup")):
                    flat[(ap["id"], vid, area["name"], field)] = pair[i]
    return flat


def diff_changes(old_sheet, new_sheet):
    """列出兩份價目資料之間每一個不同的價格。"""
    old_flat, new_flat = _flatten(old_sheet), _flatten(new_sheet)
    airports = {a["id"]: a["name"] for a in new_sheet.get("airports", [])}
    vehicles = {v["id"]: v["name"] for v in new_sheet.get("vehicles", [])}
    changes = []
    for key, new_value in new_flat.items():
        old_value = old_flat.get(key)
        if old_value != new_value:
            airport_id, vehicle_id, area, field = key
            changes.append({
                "airport": airports.get(airport_id, airport_id),
                "vehicle": vehicles.get(vehicle_id, vehicle_id),
                "area": area,
                "field": DIR_LABEL[field],
                "old": old_value,
                "new": new_value,
            })
    return changes


def soft_warnings(old_sheet, new_sheet):
    """不擋住儲存、但值得再確認的情況，回傳提醒訊息清單。"""
    warnings = []
    for c in diff_changes(old_sheet, new_sheet):
        if c["old"] and abs(c["new"] - c["old"]) / c["old"] > BIG_CHANGE_RATIO:
            warnings.append(
                f"{c['area']} 的{c['field']}價從 {c['old']:,} 改成 {c['new']:,}，變動超過 "
                f"{int(BIG_CHANGE_RATIO * 100)}%，請確認沒有多打或少打數字。"
            )

    old_flat, new_flat = _flatten(old_sheet), _flatten(new_sheet)
    for (airport_id, vehicle_id, area, field), send in new_flat.items():
        if field != "send":
            continue
        pickup = new_flat[(airport_id, vehicle_id, area, "pickup")]
        before = (old_flat.get((airport_id, vehicle_id, area, "send")),
                  old_flat.get((airport_id, vehicle_id, area, "pickup")))
        if before != (send, pickup) and pickup < send:
            warnings.append(f"{area}：接機價（{pickup:,}）比送機價（{send:,}）低，請確認。")
    return warnings


def load_sheet_file(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)
