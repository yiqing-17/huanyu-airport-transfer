"""資料表。

Booking 的欄位和原本的 MVP 完全相同，所以舊的資料庫可以直接沿用。
PriceVersion 是新增的資料表，db.create_all() 會自動建立，不需要手動搬資料。
時間一律存 UTC（沒有時區資訊），顯示時再轉成台北時間。
"""
from datetime import datetime, timezone

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Booking(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_no = db.Column(db.String(32), unique=True, nullable=False)
    service_type = db.Column(db.String(20), nullable=False)   # 新資料存「送機」或「接機」
    airport = db.Column(db.String(50), nullable=False)
    area = db.Column(db.String(150), nullable=False)
    vehicle = db.Column(db.String(50), nullable=False)
    date = db.Column(db.String(20), nullable=False)
    time = db.Column(db.String(20), nullable=False)
    passengers = db.Column(db.Integer, nullable=False)
    luggage = db.Column(db.Integer, default=0)
    address = db.Column(db.Text, nullable=False)
    name = db.Column(db.String(80), nullable=False)
    phone = db.Column(db.String(30), nullable=False)
    flight = db.Column(db.String(30), default="")
    note = db.Column(db.Text, default="")
    price = db.Column(db.Integer, nullable=False)              # 下單當下的報價，之後改價不影響
    status = db.Column(db.String(20), default="待確認")
    created_at = db.Column(db.DateTime, default=utcnow)


class PriceVersion(db.Model):
    """價目資料的每一個版本。最新的一筆就是目前網站使用的價格。"""
    id = db.Column(db.Integer, primary_key=True)
    data = db.Column(db.Text, nullable=False)                  # 整份價目 JSON（格式同 site/data/prices.json）
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)
    created_by = db.Column(db.String(80), default="")
    note = db.Column(db.String(200), default="")
    changes = db.Column(db.Text, default="[]")                 # 和上一版相比，改了哪些價格（JSON）
