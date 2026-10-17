"""後台的登入、CSRF 防護與流量限制。"""
import hmac
import secrets
import time
from collections import defaultdict, deque
from functools import wraps

from flask import abort, redirect, request, session, url_for
from markupsafe import Markup
from werkzeug.security import check_password_hash, generate_password_hash


class RateLimiter:
    """簡單的流量限制：同一個來源在一段時間內最多幾次。

    資料存在程式記憶體裡，所以每個 worker 各算各的、重新啟動就歸零。
    這足以擋住隨手的亂送與暴力猜密碼，但不是完整的防護。
    """

    def __init__(self, limit, window_seconds):
        self.limit = limit
        self.window = window_seconds
        self._hits = defaultdict(deque)

    def _prune(self, key, now):
        queue = self._hits[key]
        while queue and now - queue[0] > self.window:
            queue.popleft()
        if not queue:
            self._hits.pop(key, None)
        return self._hits[key] if key in self._hits else deque()

    def allow(self, key):
        """記錄一次，並回傳這次是否還在限制內。"""
        now = time.monotonic()
        queue = self._prune(key, now)
        if len(queue) >= self.limit:
            return False
        self._hits[key].append(now)
        return True

    def blocked(self, key):
        return len(self._prune(key, time.monotonic())) >= self.limit

    def record(self, key):
        self._hits[key].append(time.monotonic())

    def reset(self, key):
        self._hits.pop(key, None)


# ---------------------------------------------------------------- 密碼 ----


def hash_password(password):
    return generate_password_hash(password, method="pbkdf2:sha256", salt_length=16)


def admin_configured(app):
    return bool(app.config.get("ADMIN_PASSWORD_HASH"))


def verify_login(app, username, password):
    """帳號與密碼都要檢查，並且兩項都做完再回答，避免從回應時間猜出帳號。"""
    stored = app.config.get("ADMIN_PASSWORD_HASH")
    if not stored:
        return False
    user_ok = hmac.compare_digest(str(username).encode(), app.config["ADMIN_USER"].encode())
    try:
        password_ok = check_password_hash(stored, str(password))
    except ValueError:
        password_ok = False
    return user_ok and password_ok


# ---------------------------------------------------------------- 登入狀態 ----


def start_session(username):
    session.clear()                      # 登入後換一組新的 session，避免被事先塞入的 session 沿用
    session.permanent = True
    session["admin"] = True
    session["user"] = username


def safe_next(target):
    """登入後只允許跳回後台自己的頁面，避免被導去別的網站。"""
    if target and target.startswith("/admin") and not target.startswith("//") and "\\" not in target:
        return target
    return None


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("admin"):
            target = request.full_path.rstrip("?") if request.method == "GET" else None
            return redirect(url_for("admin_login", next=target))
        return view(*args, **kwargs)
    return wrapped


# ---------------------------------------------------------------- CSRF ----


def csrf_token():
    if "csrf" not in session:
        session["csrf"] = secrets.token_urlsafe(32)
    return session["csrf"]


def csrf_input():
    return Markup('<input type="hidden" name="csrf_token" value="{}">').format(csrf_token())


def verify_csrf():
    sent = request.form.get("csrf_token", "")
    expected = session.get("csrf", "")
    if not expected or not hmac.compare_digest(sent.encode(), expected.encode()):
        abort(400, "表單已失效，請重新整理頁面再試一次。")
