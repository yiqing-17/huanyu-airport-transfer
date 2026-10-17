# 黑桃機場接送：網站 + 後台

機場接送與包車服務的網站，加上店家自己登入使用的後台。

- **前台**：`site/` 裡的靜態網站（原本獨立的版本，原樣複製進來），由這個程式直接提供。
- **後台**：登入後可以**管理價格**、**查看與追蹤預約訂單**。
- 客人在預約頁送出時，預約會先存進後台，再帶著訂單編號開 LINE 傳給客服。**後端失敗也不影響預約**，會照常開 LINE。

> 這個專案的前身是一個只有 82 行的 MVP，舊檔案原封不動放在 `legacy/`，可以隨時參考或刪除。

## 專案結構

```
.
├── app.py              # 應用程式：網站、預約 API、後台
├── pricing.py          # 價目資料的驗證、查價、修改、比對
├── bookings.py         # 預約資料的驗證（價格由伺服器重新計算）
├── security.py         # 登入、CSRF 防護、流量限制
├── models.py           # 資料表
├── manage.py           # 產生後台密碼
├── wsgi.py             # 正式環境進入點（gunicorn wsgi:app）
├── templates/admin/    # 後台頁面
├── static/css/admin.css
├── site/               # 前台網站（含它自己的 build.py 與說明）
├── tests/              # 自動化測試（139 項）
├── legacy/             # 舊版 MVP 的原始檔案
└── .env.example        # 設定範本
```

## 第一次在本機執行（Windows PowerShell）

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt

copy .env.example .env
python -c "import secrets; print(secrets.token_hex(32))"    # 複製輸出，貼到 .env 的 SECRET_KEY=
python manage.py hash-password                              # 輸入密碼，把輸出那一行貼進 .env

python app.py
```

打開 <http://127.0.0.1:5000> 看網站，<http://127.0.0.1:5000/admin> 進後台。

- `.env` 不會被 git 追蹤，請**不要**把它上傳到 GitHub。
- 還沒設定密碼時，後台會顯示提示而且無法登入（預設是關閉的，不是開放的）。
- `ADMIN_PASSWORD_HASH` 的值要保留前後的單引號，因為雜湊值裡有 `$` 符號。

## 後台功能

| 頁面 | 功能 |
|---|---|
| 訂單 | 看客人送出的預約，依狀態篩選（待確認、已確認、已派車、已完成、已取消），修改狀態 |
| 價格 | 選機場與車型，直接修改每個地區的送機價、接機價 |
| 價格紀錄 | 每次修改都留下版本，可以看改了哪些價格，也可以還原到舊版本 |

價格修改的保護：

- 價格必須是 1 到 200,000 的整數，**任何一列有問題，整張都不會儲存**。
- 變動超過 50%（常見的多打一個 0），或接機價比送機價低，會先警告，確認後才儲存。
- 兩個人同時編輯時，後存的人會被擋下並要求重新整理，避免蓋掉對方的修改。
- 儲存後前台立刻套用；已經成立的訂單金額不受影響。

## 價格怎麼運作（重要）

價格的「正本」在**資料庫**，不是檔案：

1. 第一次啟動時，`site/data/prices.json` 會匯入資料庫，成為版本 #1。
2. 之後前台讀取的 `/data/prices.json` 是由資料庫即時產生的。
3. **所以之後再修改 `site/data/prices.json` 檔案，不會影響上線的價格。** 要改價格請用後台。

資料庫目前只能修改**既有地區的價格**。新增或刪除地區、修改備註與 Alphard 價格，還沒有做（見最後的「還沒做的」）。

## 前台與原版本的差異

`site/` 是原本靜態網站的完整複本，只有預約這一塊不同：

| 檔案 | 差異 |
|---|---|
| `site/js/booking.js` | 送出時先呼叫 `/api/bookings` 存檔，再開 LINE，訊息帶訂單編號 |
| `site/src/pages/booking.html` | 「人數」改成必填（後台需要這個資料） |
| `site/booking.html` | 上一個檔案重新建置的結果 |

修改 `site/src/` 之後要重新建置：`python site/build.py`。

**部署時要改的地方：** `site/build.py` 最上面的 `SITE_URL` 目前是 `https://yiqing-17.github.io/`，要改成實際的網址，並重新建置，搜尋引擎看到的正式網址才會正確。

## API

| 路徑 | 說明 |
|---|---|
| `GET /data/prices.json` | 目前的價目資料（前台使用） |
| `POST /api/bookings` | 建立預約。傳入 JSON：`dir`（send 或 pickup）、`airport`、`vehicle`、`area`、`name`、`phone`、`date`、`time`、`address`、`passengers`，選填 `luggage`、`flight`、`note`。價格由伺服器依目前價目表計算，傳來的金額會被忽略。同一個來源每小時最多 8 筆 |
| `GET /healthz` | 回傳 ok，給主機檢查用 |

## 測試

```powershell
python -m pytest
```

139 項測試涵蓋：價目資料驗證、預約驗證、登入與鎖定、CSRF、權限、價格修改與還原、檔案存取範圍。改動程式後請先跑測試。

## 部署

任何支援 Python 的主機（Render、Railway、Fly.io 等）都可以，Procfile 已設定好 `gunicorn wsgi:app`。

1. 設定環境變數：`SECRET_KEY`、`ADMIN_USER`、`ADMIN_PASSWORD_HASH`、`DATABASE_URL`；放在代理後面時加上 `TRUST_PROXY=1`。
2. 安裝時使用 `requirements-prod.txt`（多了 PostgreSQL 驅動）。
3. **資料庫請用 PostgreSQL。** 預設的 SQLite 檔案在多數雲端主機重新部署時會被清掉，訂單與價格紀錄會消失。
4. 一定要用 **HTTPS**。登入用的 cookie 預設只在 HTTPS 下傳送。
5. 沒有設定 `SECRET_KEY` 時，正式環境會直接拒絕啟動（避免登入狀態不穩定）。

## 安全與隱私

預約資料包含客人的姓名、電話、地址與航班，屬於個人資料。

- 後台一定要設定強密碼；登入失敗 5 次會鎖 15 分鐘（來源 IP）。
- 流量限制存在程式記憶體裡，重新啟動就歸零，也不會在多個 worker 之間共用。它能擋住隨手的亂送與暴力猜密碼，但不是完整的防護。
- 目前只有一組後台帳號，沒有忘記密碼功能；忘記時要重新產生雜湊值並更新環境變數。
- 請定期備份資料庫。
- 依個資法，蒐集個人資料前應告知客人用途。我不是律師，細節請向專業人士確認。

## 還沒做的

- 新增與刪除地區、修改備註與 Alphard 價格的介面
- 多個後台帳號與權限
- 新預約的自動通知
- 訂單匯出（CSV）與報表
- 資料庫結構升級工具（目前新增資料表會自動建立，但修改既有欄位需要手動處理）
