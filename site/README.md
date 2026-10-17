# 機場接送網站（純 HTML / CSS / JavaScript）

機場接送與包車服務的單頁式網站範本。沒有框架、沒有建置步驟，價格放在 JSON 檔裡，改價格不用動版面。

## 功能

- **首頁**：登機證樣式的價格試算（接機或送機、機場、地區、車型）、三個機場入口、車型一覽、聯絡方式
- **機場頁**（桃園 `tpe.html`、松山 `tsa.html`、清泉崗 `rmq.html`）：
  - **路線圖**：像地鐵路線，從機場出發沿線一站一站標價，可切換送機（Departure）與接機（Arrival）
  - **完整價目表**：航班資訊看板風格，列出所有地區
  - 選了站點或地區後，底部出現預約列，一鍵用 LINE 預約
- **座位與行李圖示**：車型用小圖示標示可乘坐人數與行李數
- **班機誤點不加價看板**（首頁）：用航班看板的樣式呈現深夜、誤點、天候的處理原則
- **夜間天空**：台灣時間晚上 10 點到清晨 6 點，頁首變深並出現星點，提醒「一樣 24 小時接受預約」
- **手機優先**：手機版價格固定在畫面底部，底部另有電話、LINE、WhatsApp 快速聯絡列
- **SEO**：每頁獨立的 title / description / canonical、JSON-LD 結構化資料、自動產生的 `sitemap.xml`
- **無障礙**：鍵盤可操作、有焦點外框、支援「減少動態效果」設定

## 在本機執行

網站會用 `fetch` 讀取 `data/prices.json`，所以不能直接點兩下開啟 `index.html`，請用本機伺服器：

```bash
python3 -m http.server 8000
# 瀏覽器開啟 http://localhost:8000
```

Windows 的 PowerShell 請用 `python -m http.server 8000`。

## 建置（修改頁面或導覽時需要）

頁面是由 `src/` 的範本組裝出來的，共用的頁首、頁尾只寫一份：

```bash
python build.py
```

只用 Python 標準函式庫，不用安裝任何套件。**產生出來的 `.html` 檔要一起 commit**，GitHub Pages 才有東西可以顯示。

- 改價格：只改 `data/prices.json`，不需要重新建置
- 改路線圖的站點：改 `data/routes.json`（每個站點指向價目表裡的一個地區，價格不會重複存放）；建置時會檢查站點對應的地區是否存在，名稱對不上就會停止並指出哪一個
- 改導覽列、新增機場頁：改 `build.py` 最上面的 `AIRPORTS`、`NAV`，再執行 `python build.py`
- 改頁首、頁尾：改 `src/partials/`，再執行 `python build.py`
- 改頁面內容：改 `src/pages/`，再執行 `python build.py`

## 專案結構

```
.
├── build.py              # 建置腳本（頁面設定在檔案最上面）
├── src/
│   ├── partials/         # 共用片段：head、頁首、頁尾、頁面標題、聯絡清單、飛機圖示
│   └── pages/            # 頁面範本：index、airport、fleet、terms、booking、recruit
├── index.html            # 以下 8 個頁面是建置產生的，要一起 commit
├── tpe.html  tsa.html  rmq.html
├── fleet.html  terms.html  booking.html  recruit.html
├── sitemap.xml           # 建置時一併產生
├── css/
│   ├── style.css         # 基本樣式
│   └── airport.css       # 機場風樣式
├── js/
│   ├── config.js         # 店名、電話、LINE、地址
│   ├── site.js           # 所有頁面共用
│   ├── home.js           # 首頁：價格試算
│   ├── airport.js        # 機場頁：路線圖與價目表
│   ├── fleet.js          # 車隊頁
│   └── booking.js        # 預約頁
├── data/prices.json      # 所有價格（機場、車型、地區、備註、Alphard）
├── data/routes.json      # 路線圖：每個機場的路線與站點
├── data/fleet.json       # 車隊照片與規格
├── images/               # 車型照片（webp）與 Logo
├── favicon.svg
└── robots.txt
```

## 頁面

| 頁面 | 檔案 | 內容 |
|---|---|---|
| 首頁 | `index.html` | 價格試算、三個機場入口、服務項目、車型、班機誤點看板、聯絡方式 |
| 桃園、松山、清泉崗機場 | `tpe.html` `tsa.html` `rmq.html` | 路線圖與完整價目表 |
| 車隊 | `fleet.html` | 11 款車型與實車照片 |
| 服務須知 | `terms.html` | 服務特色、收費與搭乘規定 |
| 預約 | `booking.html` | 選行程、填乘客資料、用 LINE 傳出；可從機場頁帶參數進來 |
| 司機招募 | `recruit.html` | 招募內容 |

預約頁可以接受網址參數預填行程，例如 `booking.html?airport=tsa&dir=pickup&vehicle=van&area=台中`，不合法的值會自動忽略。

## 備註

`css/style.css` 裡還留有一些舊版單頁使用、目前沒有頁面用到的樣式（例如舊的價目表、舊的預約區塊），不影響運作，之後可以清理。

## 目前的資料狀態

資料來自寰宇機場接送原站（桃園機場以網頁文字表為準，松山、清泉崗、Alphard 為價目圖轉錄）：

- 桃園機場：4 種車型 × 29 個地區，已與原站文字表逐筆核對
- 松山機場：4 種車型 × 30 個地區（接機價為送機價加 100 元）
- 台中清泉崗機場：4 種車型 × 20 個地區（接機價為送機價加 100 元）
- Alphard 尊爵：桃園與松山各 8 個地區（送機、接機統一價）
- 車隊：11 款車型照片與規格，在 `data/fleet.json`
- 服務特色、費用與搭乘須知、店家聯絡資料

## 上線前請店家確認

- [ ] **桃園機場有兩套價格**：網頁文字表（接機加 100 元）與價目圖（接機加 200 元，地區分得比較粗，例如桃園市區以內 800 元）不一致，目前採用網頁文字表
- [ ] **基隆市**：網頁文字表的北部與東部各列一次，休旅車、九人座、賓士兩處價格不同，目前採用北部價格
- [ ] **車型載客與行李數**不一致：官網車型說明為轎車 4 人 2 件、休旅 4 人 4 件、九人座 8 人 8 件；價目圖為 3 人 2 件、4 人 3 件、7 人 7 件。目前採用官網車型說明
- [ ] 預約專線（0900-043-688）與老闆電話（0956-602-888）哪一支為主要號碼
- [ ] 價格選項上的車型照片對應：轎車 Camry、休旅 bZ4X、九人座商務車 Staria、賓士 V-Class，可在 `data/prices.json` 的 `image` 修改
- [ ] 網址目前設為 `https://yiqing-17.github.io/`，若更換網址，修改 `build.py` 的 `SITE_URL` 和 `robots.txt` 的 Sitemap 網址，再執行 `python build.py`

### 修改價格

`data/prices.json` 的結構：

```json
{
  "vehicles": [{ "id": "sedan", "name": "國產五人座轎車", "seats": "5 人" }],
  "airports": [{
    "id": "tpe",
    "name": "桃園機場",
    "groups": [{
      "name": "北部",
      "areas": [{
        "name": "桃園市（桃園、中壢）",
        "prices": { "sedan": [900, 1000] }
      }]
    }]
  }]
}
```

`prices` 裡每個陣列是 `[送機價, 接機價]`，每個地區都要填滿所有 `vehicles` 的 `id`。要新增機場，就在 `airports` 加一筆。

## 部署

### GitHub Pages（免費）

1. 把專案推到 GitHub
2. Repo 的 Settings → Pages → Source 選 `main` 分支、根目錄
3. 幾分鐘後會得到 `https://<帳號>.github.io/<repo>/`
4. 要綁自己的網域，在同頁填入 Custom domain，並到網域商設定 DNS

### Cloudflare Pages / Netlify

連結 GitHub repo，建置指令留空，輸出目錄填 `/`。

## 授權

MIT，見 `LICENSE`。
