import json
import re
from pathlib import Path

import pytest

from conftest import AREA, PASSWORD, booking_payload, csrf_from, login, make_app, post
from models import Booking, PriceVersion, db


def version_count(app):
    with app.app_context():
        return PriceVersion.query.count()


def form_from(page, airport="tpe", vehicle="sedan"):
    """把後台價格頁目前的欄位原樣組成表單，方便只改其中幾格。"""
    form = {"airport": airport, "vehicle": vehicle,
            "base_version": re.search(r'name="base_version" value="(\d+)"', page).group(1)}
    for match in re.finditer(r'<input type="number"[^>]*name="((?:send|pickup)_\d+)"[^>]*value="([^"]*)"', page):
        form[match.group(1)] = match.group(2)
    return form


def price_page(admin):
    return admin.get("/admin/prices?airport=tpe&vehicle=sedan").get_data(as_text=True)


# ------------------------------------------------------------ 登入與權限 ----

@pytest.mark.parametrize("path", ["/admin", "/admin/prices", "/admin/prices/history"])
def test_admin_pages_require_login(client, path):
    response = client.get(path)
    assert response.status_code == 302 and "/admin/login" in response.headers["Location"]
    assert "預約訂單" not in response.get_data(as_text=True)


def test_admin_posts_require_login_and_csrf(client, app):
    client.post("/api/bookings", json=booking_payload())
    # 沒登入、沒 token
    assert client.post("/admin/bookings/1/status", data={"status": "已完成"}).status_code == 400
    # 有 token 但沒登入
    token = csrf_from(client)
    response = client.post("/admin/bookings/1/status", data={"status": "已完成", "csrf_token": token})
    assert response.status_code == 302 and "/admin/login" in response.headers["Location"]
    with app.app_context():
        assert Booking.query.one().status == "待確認"


def test_login_page_without_configured_password():
    client = make_app(ADMIN_PASSWORD_HASH="").test_client()
    page = client.get("/admin/login").get_data(as_text=True)
    assert "還沒有設定密碼" in page and "<form" not in page.split("<main")[1].split("</main>")[0]
    response = client.post("/admin/login", data={"username": "admin", "password": "anything"})
    assert response.status_code != 302                       # 不會登入成功
    assert client.get("/admin").status_code == 302


def test_wrong_password_does_not_login(client):
    response = login(client, "wrong-password")
    assert response.status_code == 200 and "帳號或密碼錯誤" in response.get_data(as_text=True)
    assert client.get("/admin").status_code == 302


def test_correct_login_and_logout(client):
    assert login(client).status_code == 302
    assert client.get("/admin").status_code == 200
    assert post(client, "/admin/logout").status_code == 302
    assert client.get("/admin").status_code == 302


def test_wrong_username_does_not_login(client):
    token = csrf_from(client)
    response = client.post("/admin/login", data={"username": "root", "password": PASSWORD, "csrf_token": token})
    assert response.status_code == 200 and client.get("/admin").status_code == 302


def test_login_without_csrf_token_is_rejected(client):
    client.get("/admin/login")
    response = client.post("/admin/login", data={"username": "admin", "password": PASSWORD})
    assert response.status_code == 400


def test_login_lockout_after_repeated_failures(client):
    for _ in range(5):
        login(client, "wrong-password")
    response = login(client)                                   # 這次密碼是對的，但已被鎖住
    assert response.status_code == 200 and "嘗試次數太多" in response.get_data(as_text=True)
    assert client.get("/admin").status_code == 302


@pytest.mark.parametrize("target,expected", [
    ("/admin/prices", "/admin/prices"),
    ("//evil.example.com", "/admin"),
    ("https://evil.example.com", "/admin"),
    ("/admin\\..\\evil", "/admin"),
    ("", "/admin"),
])
def test_login_redirect_target_is_safe(client, target, expected):
    response = login(client, next_url=target)
    assert response.status_code == 302 and response.headers["Location"].endswith(expected)
    assert "evil" not in response.headers["Location"].replace("/admin\\..\\evil", "")


def test_admin_responses_have_security_headers(admin):
    headers = admin.get("/admin").headers
    assert headers["Cache-Control"] == "no-store"
    assert headers["X-Frame-Options"] == "DENY"
    assert "default-src 'self'" in headers["Content-Security-Policy"]


# ------------------------------------------------------------ 訂單管理 ----

def test_bookings_list_and_status_update(admin, app):
    admin.post("/api/bookings", json=booking_payload())
    page = admin.get("/admin").get_data(as_text=True)
    assert "王小明" in page and "NT$ 1,000" in page and "待確認（1）" in page

    assert post(admin, "/admin/bookings/1/status", status="已確認").status_code == 302
    with app.app_context():
        assert Booking.query.one().status == "已確認"
    assert "已確認（1）" in admin.get("/admin").get_data(as_text=True)
    assert "王小明" in admin.get("/admin?status=已確認").get_data(as_text=True)
    assert "王小明" not in admin.get("/admin?status=已取消").get_data(as_text=True)


def test_status_update_rejects_unknown_status_and_missing_booking(admin):
    admin.post("/api/bookings", json=booking_payload())
    assert post(admin, "/admin/bookings/1/status", status="亂寫的狀態").status_code == 400
    assert post(admin, "/admin/bookings/999/status", status="已確認").status_code == 404


def test_status_update_without_csrf_is_rejected(admin, app):
    admin.post("/api/bookings", json=booking_payload())
    assert admin.post("/admin/bookings/1/status", data={"status": "已完成"}).status_code == 400
    with app.app_context():
        assert Booking.query.one().status == "待確認"


def test_customer_input_is_escaped_in_admin(admin):
    admin.post("/api/bookings", json=booking_payload(name="<script>alert(1)</script>", note="<img src=x onerror=alert(1)>"))
    page = admin.get("/admin").get_data(as_text=True)
    assert "<script>alert(1)</script>" not in page and "<img src=x" not in page
    assert "&lt;script&gt;" in page


def test_legacy_service_types_are_displayed(admin, app):
    with app.app_context():
        db.session.add(Booking(order_no="OLD1", service_type="pickup", airport="桃園機場", area="x", vehicle="y",
                               date="2026-01-01", time="08:00", passengers=1, address="a", name="舊資料",
                               phone="0900000000", price=1000))
        db.session.commit()
    assert "送機｜桃園機場" in admin.get("/admin").get_data(as_text=True)


# ------------------------------------------------------------ 價格管理 ----

def test_price_page_lists_all_rows(admin):
    page = price_page(admin)
    assert page.count('name="send_') == 29 and page.count('name="pickup_') == 29
    assert "桃園機場" in page and "國產五人座轎車" in page


def test_price_update_creates_version_and_updates_public_data(admin, app):
    form = form_from(price_page(admin))
    form["send_0"], form["pickup_0"] = "1150", "1250"
    response = post(admin, "/admin/prices", **form)
    assert response.status_code == 302 and version_count(app) == 2

    sheet = admin.get("/data/prices.json").get_json()
    area = sheet["airports"][0]["groups"][0]["areas"][0]
    assert area["name"] == AREA and area["prices"]["sedan"] == [1150, 1250]
    assert area["prices"]["suv"] == [1200, 1300]                 # 其他車型不受影響
    with app.app_context():
        latest = PriceVersion.query.order_by(PriceVersion.id.desc()).first()
        changes = json.loads(latest.changes)
        assert len(changes) == 2 and latest.created_by == "admin"


def test_no_change_does_not_create_version(admin, app):
    assert post(admin, "/admin/prices", **form_from(price_page(admin))).status_code == 302
    assert version_count(app) == 1


@pytest.mark.parametrize("bad", ["", "abc", "-100", "0", "12.5", "999999999"])
def test_invalid_price_is_not_saved(admin, app, bad):
    form = form_from(price_page(admin))
    form["send_3"] = bad
    response = post(admin, "/admin/prices", **form)
    assert response.status_code == 200 and "價格不正確" in response.get_data(as_text=True)
    assert version_count(app) == 1
    seed = Path(__file__).resolve().parent.parent / "site" / "data" / "prices.json"
    assert admin.get("/data/prices.json").get_json() == json.loads(seed.read_text(encoding="utf-8"))


def test_one_bad_row_blocks_the_whole_save(admin, app):
    form = form_from(price_page(admin))
    form["send_0"], form["pickup_0"] = "1150", "1250"      # 這列是對的
    form["send_5"] = "oops"                                 # 這列是錯的
    assert post(admin, "/admin/prices", **form).status_code == 200
    assert version_count(app) == 1                          # 第一列也不會被存


def test_big_change_needs_confirmation(admin, app):
    form = form_from(price_page(admin))
    form["send_0"], form["pickup_0"] = "10000", "10100"      # 多打了一個 0
    page = post(admin, "/admin/prices", **form)
    assert page.status_code == 200 and version_count(app) == 1
    text = page.get_data(as_text=True)
    assert "變動超過" in text and "確認並儲存" in text
    form["confirm"] = "1"
    assert post(admin, "/admin/prices", **form).status_code == 302
    assert version_count(app) == 2


def test_pickup_cheaper_than_send_needs_confirmation(admin, app):
    form = form_from(price_page(admin))
    form["send_0"], form["pickup_0"] = "1100", "1000"
    assert "比送機價" in post(admin, "/admin/prices", **form).get_data(as_text=True)
    assert version_count(app) == 1


def test_stale_form_is_rejected(admin, app):
    old_form = form_from(price_page(admin))
    new_form = dict(old_form, send_0="1111", pickup_0="1211")
    post(admin, "/admin/prices", **new_form)                  # 別人先存了一版
    stale = dict(old_form, send_1="1234", pickup_1="1334")    # 我用舊畫面送出
    response = post(admin, "/admin/prices", **stale)
    assert response.status_code == 302 and version_count(app) == 2
    sheet = admin.get("/data/prices.json").get_json()
    assert sheet["airports"][0]["groups"][0]["areas"][1]["prices"]["sedan"][0] == 1100   # 沒被蓋掉


def test_unknown_airport_or_vehicle_is_404(admin):
    assert admin.get("/admin/prices?airport=zzz").status_code == 404
    assert admin.get("/admin/prices?vehicle=zzz").status_code == 404


def test_price_post_without_csrf_is_rejected(admin, app):
    form = form_from(price_page(admin))
    form["send_0"] = "1500"
    assert admin.post("/admin/prices", data=form).status_code == 400
    assert version_count(app) == 1


def test_history_and_restore(admin, app):
    form = form_from(price_page(admin))
    post(admin, "/admin/prices", **dict(form, send_0="1150", pickup_0="1250"))
    history = admin.get("/admin/prices/history").get_data(as_text=True)
    assert "#2" in history and "目前使用" in history and "查看 2 筆變動" in history

    assert post(admin, "/admin/prices/restore/1").status_code == 302
    assert version_count(app) == 3
    area = admin.get("/data/prices.json").get_json()["airports"][0]["groups"][0]["areas"][0]
    assert area["prices"]["sedan"] == [1000, 1100]
    # 還原是新增一個版本，舊紀錄都還在
    assert "還原到版本 #1" in admin.get("/admin/prices/history").get_data(as_text=True)
    assert post(admin, "/admin/prices/restore/3").status_code == 302      # 還原到「目前版本」不會新增
    assert version_count(app) == 3
    assert post(admin, "/admin/prices/restore/99").status_code == 404
