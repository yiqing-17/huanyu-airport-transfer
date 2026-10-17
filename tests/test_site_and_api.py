import json

import pytest

from conftest import AREA, booking_payload, make_app
from models import Booking, PriceVersion, db


# ------------------------------------------------------------- 前台網站 ----

@pytest.mark.parametrize("path", [
    "/", "/index.html", "/tpe.html", "/tsa.html", "/rmq.html", "/fleet.html", "/terms.html",
    "/booking.html", "/recruit.html", "/css/airport.css", "/js/site.js", "/js/booking.js",
    "/images/camry.webp", "/data/routes.json", "/data/fleet.json", "/favicon.svg", "/robots.txt",
    "/sitemap.xml", "/healthz",
])
def test_public_files_are_served(client, path):
    assert client.get(path).status_code == 200


@pytest.mark.parametrize("path", [
    "/build.py", "/src/pages/index.html", "/README.md", "/LICENSE", "/js/../../app.py",
    "/css/../app.py", "/app.py", "/models.py", "/.env", "/legacy/app.py", "/instance/huanyu.db",
    "/data/prices.json.bak", "/nope.html", "/admin/unknown",
])
def test_private_files_are_not_served(client, path):
    assert client.get(path).status_code in (404, 302)
    body = client.get(path).get_data(as_text=True)
    assert "SECRET_KEY" not in body and "create_app" not in body


def test_prices_json_comes_from_database(client, app):
    response = client.get("/data/prices.json")
    assert response.status_code == 200
    assert "no-cache" in response.headers["Cache-Control"]
    sheet = response.get_json()
    assert sheet["airports"][0]["id"] == "tpe"
    with app.app_context():
        assert PriceVersion.query.count() == 1


# ------------------------------------------------------------- 預約 API ----

def book(client, **overrides):
    return client.post("/api/bookings", json=booking_payload(**overrides))


def test_booking_is_saved_with_server_side_price(client, app):
    response = book(client)
    assert response.status_code == 201
    data = response.get_json()
    assert data["ok"] and data["order_no"].startswith("HY") and data["price"] == 1000
    with app.app_context():
        saved = Booking.query.one()
        assert (saved.order_no, saved.service_type, saved.price, saved.status) == (data["order_no"], "送機", 1000, "待確認")
        assert (saved.airport, saved.vehicle, saved.area) == ("桃園機場", "國產五人座轎車", AREA)


def test_pickup_price_and_other_vehicle(client):
    assert book(client, dir="pickup").get_json()["price"] == 1100
    assert book(client, vehicle="benz").get_json()["price"] == 1800


def test_client_supplied_price_is_ignored(client):
    assert book(client, price=1, total=1).get_json()["price"] == 1000


@pytest.mark.parametrize("overrides", [
    dict(area="不存在的地區"), dict(airport="zzz"), dict(vehicle="zzz"), dict(dir="bad"),
    dict(name=""), dict(name="   "), dict(phone=""), dict(phone="abc"), dict(phone="123"),
    dict(address=""), dict(date=""), dict(date="2020-01-01"), dict(date="not-a-date"),
    dict(date="2999-01-01"), dict(time=""), dict(time="25:00"),
    dict(passengers=0), dict(passengers=10), dict(passengers="abc"), dict(passengers=None),
    dict(luggage=-1), dict(luggage=99), dict(note="x" * 501), dict(name="x" * 81),
    dict(name={"a": 1}), dict(passengers=True),
])
def test_invalid_bookings_are_rejected(client, app, overrides):
    response = book(client, **overrides)
    assert response.status_code == 400
    assert response.get_json()["ok"] is False and response.get_json()["errors"]
    with app.app_context():
        assert Booking.query.count() == 0


@pytest.mark.parametrize("body", ["not json", "[1,2,3]", "null", '"text"'])
def test_non_object_json_is_rejected(client, body):
    response = client.post("/api/bookings", data=body, content_type="application/json")
    assert response.status_code == 400


def test_luggage_is_optional(client):
    payload = booking_payload()
    payload.pop("luggage")
    assert client.post("/api/bookings", json=payload).status_code == 201


def test_booking_rate_limit():
    limited = make_app(BOOKING_LIMIT=2).test_client()
    assert [book(limited).status_code for _ in range(4)] == [201, 201, 429, 429]


def test_booking_keeps_price_after_price_change(admin):
    first = book(admin).get_json()
    from conftest import post
    version = admin.get("/data/prices.json")
    # 改價之後，新預約用新價格；舊預約的價格不變
    page = admin.get("/admin/prices?airport=tpe&vehicle=sedan").get_data(as_text=True)
    base = page.split('name="base_version" value="')[1].split('"')[0]
    form = {"airport": "tpe", "vehicle": "sedan", "base_version": base}
    for line in page.split("<input")[1:]:
        if 'name="send_' in line or 'name="pickup_' in line:
            name = line.split('name="')[1].split('"')[0]
            value = line.split('value="')[1].split('"')[0]
            form[name] = value
    form["send_0"], form["pickup_0"] = "1150", "1250"
    assert post(admin, "/admin/prices", **form).status_code == 302
    second = book(admin).get_json()
    assert (first["price"], second["price"]) == (1000, 1150)
