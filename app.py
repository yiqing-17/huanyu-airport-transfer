"""黑桃機場接送：網站 + 預約紀錄 + 後台。

- 前台網站是 site/ 裡的靜態網站，由這個程式直接提供。
- /data/prices.json 不讀檔案，而是回傳資料庫裡目前的價格，所以後台改價，前台立刻更新。
- /api/bookings 接收預約並存檔（價格由伺服器重新計算）。
- /admin 後台：訂單管理、價格管理。必須先登入。
"""
import json
import os
import secrets
from datetime import timedelta
from pathlib import Path

from flask import (Flask, Response, abort, flash, jsonify, redirect, render_template,
                   request, send_from_directory, session, url_for)
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

import bookings as bk
import pricing
import security
from models import Booking, PriceVersion, db

BASE_DIR = Path(__file__).resolve().parent
STATUSES = ["待確認", "已確認", "已派車", "已完成", "已取消"]

# 前台網站只開放這些檔案，其他（build.py、src/、README 等）一律 404
SITE_DIRS = {"css", "js", "images", "data"}
SITE_FILES = {"favicon.svg", "robots.txt", "sitemap.xml"}
PUBLIC_DATA = {"routes.json", "fleet.json"}          # prices.json 由資料庫提供，不直接讀檔


def create_app(test_config=None):
    try:
        from dotenv import load_dotenv
        load_dotenv(BASE_DIR / ".env")
    except ImportError:
        pass

    app = Flask(__name__)
    dev = os.environ.get("FLASK_DEBUG") == "1"

    config = dict(
        SECRET_KEY=os.environ.get("SECRET_KEY"),
        SQLALCHEMY_DATABASE_URI=(os.environ.get("DATABASE_URL") or "sqlite:///huanyu.db")
        .replace("postgres://", "postgresql://", 1),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        ADMIN_USER=os.environ.get("ADMIN_USER", "admin"),
        ADMIN_PASSWORD_HASH=os.environ.get("ADMIN_PASSWORD_HASH", ""),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=os.environ.get("SESSION_COOKIE_SECURE", "0" if dev else "1") == "1",
        PERMANENT_SESSION_LIFETIME=timedelta(hours=8),
        BOOKING_LIMIT=8, BOOKING_WINDOW=3600,        # 同一個來源每小時最多送 8 筆預約
        LOGIN_LIMIT=5, LOGIN_WINDOW=900,             # 登入失敗 5 次後鎖 15 分鐘
        SITE_DIR=str(BASE_DIR / "site"),
    )
    config.update(test_config or {})

    if not config["SECRET_KEY"]:
        if dev or config.get("TESTING"):
            config["SECRET_KEY"] = secrets.token_hex(32)
        else:
            raise RuntimeError(
                "請設定環境變數 SECRET_KEY（一長串隨機文字）。"
                "可用這個指令產生：python -c \"import secrets; print(secrets.token_hex(32))\""
            )
    app.config.from_mapping(config)

    if os.environ.get("TRUST_PROXY") == "1":
        # 放在 Render、Railway 這類代理後面時，才能看到訪客真正的 IP
        from werkzeug.middleware.proxy_fix import ProxyFix
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    app.extensions["booking_limiter"] = security.RateLimiter(config["BOOKING_LIMIT"], config["BOOKING_WINDOW"])
    app.extensions["login_limiter"] = security.RateLimiter(config["LOGIN_LIMIT"], config["LOGIN_WINDOW"])

    db.init_app(app)
    with app.app_context():
        db.create_all()
        seed_prices(app)

    register_helpers(app)
    register_public_routes(app)
    register_admin_routes(app)
    return app


# ------------------------------------------------------------------ 價目資料 ----


def seed_prices(app):
    """第一次啟動時，把 site/data/prices.json 匯入資料庫，成為第一個版本。"""
    if PriceVersion.query.first():
        return
    path = Path(app.config["SITE_DIR"]) / "data" / "prices.json"
    sheet = pricing.load_sheet_file(path)
    errors = pricing.validate_sheet(sheet)
    if errors:
        raise RuntimeError("初始價目資料有誤：" + "；".join(errors[:5]))
    db.session.add(PriceVersion(
        data=json.dumps(sheet, ensure_ascii=False), created_by="系統",
        note="初始資料（來自 site/data/prices.json）", changes="[]"))
    db.session.commit()


def current_version():
    return PriceVersion.query.order_by(PriceVersion.id.desc()).first()


def current_sheet():
    version = current_version()
    return version, json.loads(version.data)


def save_version(sheet, note, changes):
    errors = pricing.validate_sheet(sheet)
    if errors:                      # 理論上不會發生；萬一發生，寧可不存也不要讓前台壞掉
        raise pricing.PriceError("價目資料驗證失敗：" + "；".join(errors[:3]))
    version = PriceVersion(
        data=json.dumps(sheet, ensure_ascii=False), created_by=session.get("user", ""),
        note=note[:200], changes=json.dumps(changes, ensure_ascii=False))
    db.session.add(version)
    db.session.commit()
    return version


# ------------------------------------------------------------------ 共用小工具 ----


def client_ip():
    return request.remote_addr or "unknown"


def register_helpers(app):
    app.jinja_env.globals["csrf_token"] = security.csrf_token
    app.jinja_env.globals["csrf_input"] = security.csrf_input
    app.jinja_env.globals["STATUSES"] = STATUSES

    @app.template_filter("taipei")
    def taipei(value):
        """資料庫存的是 UTC，顯示成台北時間。"""
        return "" if value is None else (value + timedelta(hours=8)).strftime("%Y-%m-%d %H:%M")

    @app.template_filter("money")
    def money(value):
        return f"NT$ {int(value):,}"

    @app.template_filter("service_label")
    def service_label(value):
        # 舊版 MVP 存的是 pickup（送機）與 dropoff（接機）
        return {"pickup": "送機", "dropoff": "接機"}.get(value, value)

    @app.after_request
    def secure_admin_responses(response):
        if request.path.startswith("/admin"):
            response.headers["Cache-Control"] = "no-store"
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["X-Frame-Options"] = "DENY"
            response.headers["Referrer-Policy"] = "same-origin"
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; style-src 'self'; script-src 'self'; "
                "frame-ancestors 'none'; form-action 'self'; base-uri 'none'")
        return response

    @app.before_request
    def admin_csrf_guard():
        if request.path.startswith("/admin") and request.method == "POST":
            security.verify_csrf()


# ------------------------------------------------------------------ 前台 ----


def register_public_routes(app):
    @app.get("/healthz")
    def healthz():
        return "ok"

    @app.get("/data/prices.json")
    def prices_json():
        response = Response(current_version().data, content_type="application/json; charset=utf-8")
        response.headers["Cache-Control"] = "no-cache"        # 每次都向伺服器確認，改價後立刻生效
        return response

    @app.post("/api/bookings")
    def api_create_booking():
        if not app.extensions["booking_limiter"].allow(client_ip()):
            return jsonify(ok=False, message="送出太頻繁，請稍後再試，或直接用 LINE 聯絡我們。"), 429
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return jsonify(ok=False, message="資料格式不正確"), 400

        _, sheet = current_sheet()
        clean, errors = bk.validate_booking(data, sheet)
        if errors:
            return jsonify(ok=False, errors=errors, message=errors[0]), 400

        for _ in range(3):                                    # 訂單編號極少數情況會重複，換一個再試
            booking = Booking(order_no=bk.new_order_no(), **clean)
            db.session.add(booking)
            try:
                db.session.commit()
                return jsonify(ok=True, order_no=booking.order_no, price=booking.price), 201
            except IntegrityError:
                db.session.rollback()
        return jsonify(ok=False, message="系統忙碌，請稍後再試，或直接用 LINE 聯絡我們。"), 500

    @app.get("/")
    def site_index():
        return send_from_directory(app.config["SITE_DIR"], "index.html")

    @app.get("/<path:filename>")
    def site_file(filename):
        parts = filename.split("/")
        if len(parts) == 1:
            allowed = filename.endswith(".html") or filename in SITE_FILES
        elif parts[0] in SITE_DIRS:
            allowed = parts[0] != "data" or (len(parts) == 2 and parts[1] in PUBLIC_DATA)
        else:
            allowed = False
        if not allowed:
            abort(404)
        return send_from_directory(app.config["SITE_DIR"], filename)


# ------------------------------------------------------------------ 後台 ----


def register_admin_routes(app):
    @app.route("/admin/login", methods=["GET", "POST"])
    def admin_login():
        configured = security.admin_configured(app)
        if session.get("admin"):
            return redirect(url_for("admin_bookings"))
        if request.method == "POST":
            ip = client_ip()
            limiter = app.extensions["login_limiter"]
            username = request.form.get("username", "")
            if limiter.blocked(ip):
                flash("嘗試次數太多，請 15 分鐘後再試。", "error")
            elif security.verify_login(app, username, request.form.get("password", "")):
                limiter.reset(ip)
                security.start_session(username)
                return redirect(security.safe_next(request.form.get("next")) or url_for("admin_bookings"))
            else:
                limiter.record(ip)
                flash("帳號或密碼錯誤。", "error")
        return render_template("admin/login.html", configured=configured,
                               next=request.values.get("next", ""))

    @app.post("/admin/logout")
    def admin_logout():
        session.clear()
        flash("已登出。", "ok")
        return redirect(url_for("admin_login"))

    # ---- 訂單 ----

    @app.get("/admin")
    @security.login_required
    def admin_bookings():
        status = request.args.get("status", "")
        query = Booking.query.order_by(Booking.created_at.desc(), Booking.id.desc())
        if status in STATUSES:
            query = query.filter_by(status=status)
        counts = dict(db.session.query(Booking.status, func.count(Booking.id)).group_by(Booking.status).all())
        return render_template("admin/bookings.html", bookings=query.limit(300).all(),
                               status=status, counts=counts, total=sum(counts.values()), active="bookings")

    @app.post("/admin/bookings/<int:booking_id>/status")
    @security.login_required
    def admin_booking_status(booking_id):
        booking = db.get_or_404(Booking, booking_id)
        status = request.form.get("status", "")
        if status not in STATUSES:
            abort(400)
        booking.status = status
        db.session.commit()
        flash(f"訂單 {booking.order_no} 已改為「{status}」。", "ok")
        back = request.form.get("back", "")
        return redirect(back if back.startswith("/admin") and not back.startswith("//") else url_for("admin_bookings"))

    # ---- 價格 ----

    @app.route("/admin/prices", methods=["GET", "POST"])
    @security.login_required
    def admin_prices():
        version, sheet = current_sheet()
        airports, vehicles = sheet["airports"], sheet["vehicles"]
        airport_id = request.values.get("airport") or airports[0]["id"]
        vehicle_id = request.values.get("vehicle") or vehicles[0]["id"]
        try:
            airport = pricing.find_airport(sheet, airport_id)
            vehicle = pricing.find_vehicle(sheet, vehicle_id)
        except pricing.PriceError:
            abort(404)
        rows = pricing.price_rows(sheet, airport_id, vehicle_id)
        context = dict(active="prices", sheet=sheet, version=version, airport=airport, vehicle=vehicle,
                       rows=rows, row_errors={}, warnings=[], confirm=False)

        if request.method == "POST":
            if request.form.get("base_version") != str(version.id):
                flash("價格在你編輯的期間已經被更新，請重新整理後再修改，避免蓋掉別人的修改。", "error")
                return redirect(url_for("admin_prices", airport=airport_id, vehicle=vehicle_id))

            updates, row_errors, shown = {}, {}, []
            for row in rows:
                i = row["index"]
                raw_send = request.form.get(f"send_{i}", "")
                raw_pickup = request.form.get(f"pickup_{i}", "")
                shown.append({**row, "send": raw_send, "pickup": raw_pickup})
                try:
                    updates[i] = (pricing.parse_price(raw_send), pricing.parse_price(raw_pickup))
                except pricing.PriceError as exc:
                    row_errors[i] = str(exc)
            context.update(rows=shown, row_errors=row_errors)

            if row_errors:
                flash(f"有 {len(row_errors)} 列的價格不正確，請修正後再儲存（沒有任何資料被儲存）。", "error")
                return render_template("admin/prices.html", **context)

            new_sheet = pricing.apply_prices(sheet, airport_id, vehicle_id, updates)
            changes = pricing.diff_changes(sheet, new_sheet)
            if not changes:
                flash("沒有任何價格變動。", "ok")
                return redirect(url_for("admin_prices", airport=airport_id, vehicle=vehicle_id))

            warnings = pricing.soft_warnings(sheet, new_sheet)
            if warnings and request.form.get("confirm") != "1":
                context.update(warnings=warnings, confirm=True)
                return render_template("admin/prices.html", **context)

            note = f"{airport['name']}｜{vehicle['name']}：更新 {len(changes)} 筆價格"
            saved = save_version(new_sheet, note, changes)
            flash(f"已儲存（版本 #{saved.id}）：{note}。前台網站已經套用新價格。", "ok")
            return redirect(url_for("admin_prices", airport=airport_id, vehicle=vehicle_id))

        return render_template("admin/prices.html", **context)

    @app.get("/admin/prices/history")
    @security.login_required
    def admin_prices_history():
        versions = PriceVersion.query.order_by(PriceVersion.id.desc()).limit(100).all()
        history = []
        for v in versions:
            history.append({"v": v, "changes": json.loads(v.changes or "[]")})
        return render_template("admin/history.html", history=history, current_id=versions[0].id,
                               active="history")

    @app.post("/admin/prices/restore/<int:version_id>")
    @security.login_required
    def admin_prices_restore(version_id):
        old = db.get_or_404(PriceVersion, version_id)
        current = current_version()
        if old.id == current.id:
            flash("這已經是目前使用的版本。", "ok")
            return redirect(url_for("admin_prices_history"))
        old_sheet, current_sheet_ = json.loads(old.data), json.loads(current.data)
        changes = pricing.diff_changes(current_sheet_, old_sheet)
        try:
            saved = save_version(old_sheet, f"還原到版本 #{old.id}", changes)
        except pricing.PriceError as exc:
            flash(str(exc), "error")
            return redirect(url_for("admin_prices_history"))
        flash(f"已還原到版本 #{old.id} 的價格（新版本 #{saved.id}）。", "ok")
        return redirect(url_for("admin_prices_history"))


if __name__ == "__main__":
    os.environ.setdefault("FLASK_DEBUG", "1")      # 本機開發用；正式環境請用 gunicorn wsgi:app
    create_app().run(debug=True, host="127.0.0.1", port=5000)
