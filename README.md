# 寰宇機場接送正式網站 MVP

## 啟動
python -m venv .venv
.venv\\Scripts\\activate
pip install -r requirements.txt
python app.py

開啟 http://127.0.0.1:5000
管理後台：http://127.0.0.1:5000/admin

## 已完成
- 以目前公開網站內容為基準的首頁
- 四種車型與桃園機場公開價目表
- 送機 / 接機報價
- 線上預約
- SQLite / PostgreSQL 相容資料庫
- 訂單編號
- 管理後台與訂單狀態
- 手機版

## 正式上線前還要做
- 管理員登入與權限
- LINE 官方帳號正式通知
- Email / SMS
- 金流
- 司機與車輛管理
- 航班追蹤
- Google Maps / 地址驗證
- 隱私權、服務條款、取消退款規則
- HTTPS、備份、監控
