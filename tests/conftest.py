import re
import sys
from datetime import timedelta
from pathlib import Path

import pytest
from werkzeug.security import generate_password_hash

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import bookings as bk          # noqa: E402
import security                # noqa: E402
from app import create_app     # noqa: E402

PASSWORD = "correct-horse-battery"
FAST_HASH = generate_password_hash(PASSWORD, method="pbkdf2:sha256:1000")   # 測試用：迭代次數少，跑得快
AREA = "台北市（萬華、中正、大安、信義、大同、中山、松山）"   # 桃園機場 台北市：轎車 送機 1000 / 接機 1100


def make_app(**overrides):
    config = dict(
        TESTING=True,
        SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
        ADMIN_USER="admin",
        ADMIN_PASSWORD_HASH=FAST_HASH,
        SESSION_COOKIE_SECURE=False,
        BOOKING_LIMIT=1000,
    )
    config.update(overrides)
    return create_app(config)


@pytest.fixture()
def app():
    return make_app()


@pytest.fixture()
def client(app):
    return app.test_client()


def csrf_from(client, path="/admin/login"):
    client.get(path)
    with client.session_transaction() as s:
        return s["csrf"]


def login(client, password=PASSWORD, next_url=""):
    token = csrf_from(client)
    return client.post("/admin/login", data={
        "username": "admin", "password": password, "csrf_token": token, "next": next_url})


@pytest.fixture()
def admin(app):
    client = app.test_client()
    response = login(client)
    assert response.status_code == 302
    return client


def post(client, url, **data):
    """以目前 session 的 CSRF token 送出表單。"""
    with client.session_transaction() as s:
        has_token = "csrf" in s
    if not has_token:                       # 真實使用時一定先看過某個頁面；測試這裡補上
        client.get("/admin/login")
        client.get("/admin")
    with client.session_transaction() as s:
        data.setdefault("csrf_token", s.get("csrf", ""))
    return client.post(url, data=data)


def booking_payload(**overrides):
    tomorrow = (bk.now_taipei().date() + timedelta(days=1)).isoformat()
    payload = dict(
        dir="send", airport="tpe", vehicle="sedan", area=AREA,
        name="王小明", phone="0912-345-678", date=tomorrow, time="08:30",
        address="台北市信義區市府路1號", flight="BR 123", passengers=2, luggage=2, note="",
    )
    payload.update(overrides)
    return payload
