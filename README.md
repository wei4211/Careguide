# CareGuide：高齡照護需求評估與建議系統

[![Python](https://img.shields.io/badge/Python-3.12-blue?logo=python&logoColor=white)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-3.x-000000?logo=flask&logoColor=white)](https://flask.palletsprojects.com/)
[![Gemini](https://img.shields.io/badge/AI-Gemini-4285F4?logo=google&logoColor=white)](https://ai.google.dev/)
[![Render](https://img.shields.io/badge/Deploy-Render-46E3B7?logo=render&logoColor=white)](https://render.com/)
[![License](https://img.shields.io/badge/License-Academic-lightgrey)](#license)

CareGuide 是一套面向家屬與照顧者的 **高齡照護需求評估網站**。透過分頁式問卷收集長者的生活、健康、家庭照顧資訊，以 100 分制 **規則式評分模型** 計算照護需求等級，並串接 Google Gemini 產生 **白話化、個人化的照護建議與個案摘要報告**。

> ⚠️ 本系統僅提供初步照護需求評估，不取代正式長照評估或醫療診斷。

🔗 **線上展示**：[careguide-3ktf.onrender.com](https://careguide-3ktf.onrender.com)

> 免費方案閒置 15 分鐘會睡眠，首次訪問請等約 30 秒喚醒；
> 評估資料可能因服務重啟被清空，僅供示範體驗。
> 若 AI 建議區塊出現「系統提示」開頭文字，代表 Gemini 配額暫時用罄，會自動退到本地建議文字。

---

## 為什麼做這個系統

照護需求評估涉及 ADL、IADL、健康、家庭支持、照顧者壓力等多個面向，家屬常常不知道從哪裡看起、要問誰、如何描述長者的狀況。CareGuide 把這些面向結構化成問卷，讓使用者能快速取得：

1. 一份 **照護需求等級** 的初步判斷（低度 / 中度 / 高度 / 極高度）
2. 一份 **AI 撰寫的、針對該長者狀況的個人化建議**
3. 一份可下載的 **個案摘要 PDF**，能拿去長照中心或醫療院所跟專業人員討論

不取代正式評估，但能讓家屬在尋求專業幫助前，先有一份有條理的記錄。

---

## 主要功能

### 評估流程
- 七步驟分頁式問卷，含基本資料、ADL、IADL、健康安全、家庭支持、照顧者壓力、自由描述
- **localStorage 草稿自動儲存**，意外關掉分頁不會全沒（7 天過期）
- 送出時全屏 loading 提示

### 評分與建議
- **100 分制規則式評分**：可解釋的五大面向加總，邏輯透明
- **生成式 AI 建議**：串接 Gemini API 產生五段式建議，回應內容會引用使用者填的具體細節
- **多模型 fallback**：自動嘗試 `gemini-2.5-flash` → `gemini-2.5-flash-lite` → `gemini-2.0-flash` → `gemini-2.0-flash-lite`，遇 quota / 區域問題會自動換下一個
- **重新產生** 按鈕：對 AI 建議不滿意可一鍵重打
- 沒設 API Key 時自動使用本地備援文字，網站照樣能跑

### 帳號與資料
- 使用者註冊 / 登入（密碼以 `werkzeug` 雜湊儲存）
- 評估、結果、報告、紀錄都依 `user_id` 過濾，使用者間嚴格隔離
- 歷史紀錄列表，可查看 / 刪除（含確認 modal）

### 報告輸出
- 結果頁渲染 Markdown（標題、粗體、條列）
- 個案摘要報告頁可一鍵 **複製文字** / **列印** / **下載 PDF**
- PDF 自動偵測作業系統內的中文字型（macOS / Windows / Linux 都通），需要時也支援 `CAREGUIDE_PDF_FONT` 自訂

### 部署
- 提供 **Native runtime** 與 **Docker** 兩種 Render 部署設定
- Docker 版內建 `fonts-wqy-microhei`，PDF 中文開箱即用
- `render.yaml` Blueprint 自動產生 `FLASK_SECRET_KEY`

---

## 系統架構

```
┌────────────────────┐   問卷       ┌────────────────────┐
│   使用者瀏覽器     │ ───────────> │  Flask Routes      │
│   (Bootstrap UI)   │              │  app.py            │
└────────────────────┘              └─────────┬──────────┘
       ▲                                       │
       │ HTML / PDF / JSON                     ▼
       │                          ┌────────────────────────┐
       │                          │  modules/              │
       │                          │  ├ auth.py             │
       │                          │  ├ risk_score.py       │
       │                          │  ├ database.py         │
       │                          │  ├ gemini_service.py   │
       │                          │  └ pdf_generator.py    │
       │                          └─────────┬──────────────┘
       │                                    │
       │                          ┌─────────▼──────────┐
       │                          │  SQLite DB         │
       │                          │  users /           │
       │                          │  assessments /     │
       │                          │  reports           │
       │                          └────────────────────┘
       │
       │                          ┌────────────────────┐
       └─────────────────────────│  Gemini API        │
                                  │  (五段式建議文字)  │
                                  └────────────────────┘
```

### 資料流

1. 使用者填問卷 → POST `/evaluate`
2. `risk_score.py` 計算 ADL / IADL / 健康 / 家庭 / 照顧者壓力五大面向分數
3. `gemini_service.py` 把問卷 + 分數整理成 prompt → 呼叫 Gemini → 取得照護建議
4. `database.py` 寫入 `assessments` 資料表
5. 跳轉到 `/result/<id>`，渲染分數、風險因素、AI 建議
6. 使用者可下載 PDF（`pdf_generator.py` 用 ReportLab + 系統中文字型）

---

## 技術架構

| 層級 | 技術 |
| --- | --- |
| **前端** | HTML、Bootstrap 5、原生 JavaScript |
| **後端** | Python 3.12、Flask 3、Werkzeug Security |
| **資料庫** | SQLite（首次啟動自動建立） |
| **AI** | Google Gemini API（`google-genai` SDK） |
| **PDF** | ReportLab 4 + 系統中文字型（macOS PingFang/STHeiti、Linux WQY、Windows JhengHei） |
| **Markdown** | `markdown` 套件渲染 AI 建議 |
| **部署** | Render + Docker（容器內以 Gunicorn 啟動；repo 另附 `render.native.yaml` 可切換為 Native runtime） |

---

## 評分模型

100 分制，分為五個面向：

| 面向 | 滿分 | 重點題項 |
| --- | --- | --- |
| 日常生活能力 ADL | 30 | 洗澡、穿衣、吃飯、如廁、移位、行走 |
| 工具性日常生活能力 IADL | 20 | 備餐、購物、外出交通、服藥、家務 |
| 健康與安全風險 | 20 | 跌倒史、慢性病、認知退化、住院 |
| 家庭照顧支持 | 20 | 居住、照顧者穩定度、家人支援、緊急協助 |
| 照顧者壓力 | 10 | 照顧者壓力、健康、喘息需求 |

照護需求等級對照：

| 總分 | 等級 | UI 標示色 |
| --- | --- | --- |
| 0–24 | 低度照護需求 | 綠 |
| 25–49 | 中度照護需求 | 黃 |
| 50–74 | 高度照護需求 | 橘 |
| 75–100 | 極高度照護需求 | 紅 |

評分邏輯定義在 [`modules/risk_score.py`](modules/risk_score.py)，可單獨匯入測試：

```python
from modules.risk_score import evaluate

result = evaluate({
    "mobility": "aid",
    "fall_history": "once",
    "bathing": "often",
    # ...
})
print(result["total_score"], result["risk_level"])
# → 58 高度照護需求
```

---

## AI 建議的設計理念

CareGuide 採用「**規則式評分 + 生成式 AI 建議**」分工：

- **規則式評分** 負責計算分數與等級 → 結果可解釋、穩定可重現
- **生成式 AI** 負責把分數轉換為白話建議 → 互動性、個人化

```
規則式評分（穩定）  →  AI 建議（個人化）
(分數 / 等級 / 風險因素)    (白話五段式說明)
```

這樣可以兼顧 **可解釋性**（為什麼是高度需求？看分數）與 **可讀性**（這個情況該怎麼辦？看 AI 建議）。

### Prompt 工程

- 系統 prompt 限制 AI 不可進行醫療診斷、不可判定長照資格
- 強制要求五段式輸出（個案摘要 / 風險說明 / 建議服務 / 行動 / 注意事項）
- 把使用者的自由描述放進 prompt，讓 AI 能引用具體細節
- 多模型 fallback，遇 quota / 503 / 區域限制自動換下一個

詳見 [`modules/gemini_service.py`](modules/gemini_service.py)。

---

## 快速開始

### 1. 取得程式碼並安裝相依套件

```bash
git clone https://github.com/wei4211/Careguide.git
cd Careguide
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. 設定環境變數

```bash
cp .env.example .env
```

編輯 `.env`：

```
GEMINI_API_KEY=從 https://aistudio.google.com/apikey 取得
FLASK_SECRET_KEY=任意隨機字串（python3 -c "import secrets; print(secrets.token_hex(32))" 可產生）
FLASK_ENV=development
```

> 沒有 Gemini Key 也能跑，AI 建議區塊會以本地備援文字呈現。

### 3. 啟動

```bash
python app.py
```

開瀏覽器到 `http://localhost:8000`，註冊帳號就能開始評估。

> **macOS 注意**：原本預設的 port 5000 會被 AirPlay Receiver 占用，所以改成 8000。

### 4. （選用）用 Docker 跑

```bash
docker build -t careguide .
docker run --rm -p 8000:8000 \
  -e GEMINI_API_KEY=你的key \
  -e FLASK_SECRET_KEY=任意字串 \
  careguide
```

Docker 版內建 `fonts-wqy-microhei`，PDF 中文渲染保證可用。

---

## 專案結構

```
careguide/
├── app.py                  # Flask 主應用程式與所有路由
├── requirements.txt
├── Dockerfile              # Docker 部署用
├── .dockerignore
├── render.yaml             # Render Blueprint（Docker 模式）
├── render.native.yaml      # Render Blueprint（Native runtime 模式）
├── .env.example            # 環境變數範本
├── DEPLOY_RENDER.md        # Render 部署完整指南
│
├── modules/
│   ├── auth.py             # 註冊、登入驗證、login_required 裝飾器
│   ├── database.py         # SQLite 連線、users / assessments / reports
│   ├── risk_score.py       # 五大面向規則式評分模型
│   ├── gemini_service.py   # Gemini API 串接 + 多模型 fallback + 本地備援
│   └── pdf_generator.py    # ReportLab PDF 產生器
│
├── templates/
│   ├── base.html           # 共用版面（含 navbar、flash、loading overlay）
│   ├── index.html          # 首頁
│   ├── login.html          # 登入
│   ├── register.html       # 註冊
│   ├── assessment.html     # 評估問卷（7 步驟分頁）
│   ├── result.html         # 評估結果頁（含重新產生 AI）
│   ├── report.html         # 個案摘要報告
│   ├── records.html        # 歷史紀錄列表（含刪除）
│   └── about.html          # 系統說明
│
├── static/
│   ├── css/style.css
│   └── js/assessment.js    # 問卷分頁切換、草稿自動儲存
│
└── database/
    └── careguide.db        # 啟動時自動建立
```

---

## 部署

完整 Render 部署步驟見 [DEPLOY_RENDER.md](DEPLOY_RENDER.md)，內含：

- Native runtime 與 Docker 兩種模式
- GitHub 連動自動部署
- 環境變數設定
- SQLite 資料持久化的三種選擇
- 中文字型處理
- 常見錯誤排解

---

## 安全性

- 密碼以 `werkzeug.security.generate_password_hash` 雜湊後存入資料庫，原始密碼不會被儲存
- 評估、結果、報告、紀錄、刪除等所有路由都套用 `@login_required`，並依 `user_id` 過濾
- 登出採用 `POST` 表單，避免被 CSRF 觸發
- 登入後的 `?next=` 參數會驗證為站內相對路徑，防止 open redirect
- AI 回應的 Markdown 透過 `markupsafe.Markup` 統一處理，避免 XSS

---

## 系統限制與免責聲明

1. CareGuide 僅提供初步照護需求評估，不代表正式長照資格判定
2. 本系統不能取代醫師診斷、社工評估或長照管理中心的正式評估
3. 規則式評分以初步篩檢與系統展示為主，尚未以大規模真實資料驗證
4. 生成式 AI 建議會受到使用者輸入內容影響，可能存在不完整或不精確之情形
5. 若長者已有急性醫療問題、嚴重跌倒、意識混亂或安全疑慮，應優先尋求醫療或專業協助

需要正式評估時，請撥打 **1966 長照服務專線** 或聯繫所在地長期照顧管理中心。

---

## 開發歷程與致謝

本專案延伸自 **「高齡族群長照使用之時間變化與影響因素分析」** 研究主題，原研究以 108–112 年銀髮安居模擬資料為基礎，分析年齡、身心障礙程度、家庭型態、低收入身分、住宅條件等因素對長照使用機率的影響。CareGuide 把這些研究發現轉化為可實際操作的網站，讓家屬也能受惠於資料分析的洞見。

---

## License

本專案採用 **MIT License**，詳見 [LICENSE](LICENSE) 檔。
你可以自由使用、修改、散布本程式碼（含商業用途），唯需保留原始版權聲明。

Copyright (c) 2026 wei4211
