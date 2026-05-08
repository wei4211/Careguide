# 部署到 Render

CareGuide 已經放好 `render.yaml`、`gunicorn`、Python 版本等部署所需檔案，照著下面三個階段做就能上線。

---

## 階段一：把程式碼放到 GitHub

Render 是從 Git repo 自動部署的，所以一定要先有一個 GitHub repo。

```bash
cd careguide

# 第一次：初始化並送上 GitHub
git init
git add .
git commit -m "init: CareGuide MVP"

# 在 GitHub 建一個 repo（網頁上 New repository → 取名 careguide）
# 之後把它接上來：
git branch -M main
git remote add origin git@github.com:你的帳號/careguide.git
git push -u origin main
```

> 沒裝過 git 或 SSH 金鑰的話，可以改用 GitHub Desktop 圖形介面，把 `careguide/` 整個資料夾拖進去就好。

---

## 階段二：在 Render 建立服務

1. 註冊 / 登入 [Render](https://render.com)，建議用 GitHub 帳號登入（之後授權更省事）
2. Dashboard → **New +** → **Blueprint**
3. 選剛剛建立的 `careguide` repo → **Apply**
   - Render 會自動讀 `render.yaml`，建出名稱為 `careguide` 的 Web Service
   - 自動產生 `FLASK_SECRET_KEY`
4. 進到 service 的 **Environment** 頁，把 `GEMINI_API_KEY` 填上你的金鑰
   - 沒有金鑰也能部署，AI 建議區塊會用本地備援文字（系統不會壞）
5. 第一次部署會跑 `pip install` + `gunicorn` 啟動，約 3–5 分鐘
6. 部署成功後 URL 會像 `https://careguide.onrender.com`

---

## 階段三：自動部署設定

`render.yaml` 已啟用「**Auto-Deploy on Push**」，之後做：

```bash
git add .
git commit -m "add: 新功能"
git push
```

Render 會自動偵測並重新部署。

---

## 常見注意事項

### SQLite 資料會在重新部署時清空

Render Free 方案的檔案系統是 ephemeral（暫存），意思是每次重新部署或休眠重啟，`database/careguide.db` 都會被重置。

對於 demo / 課堂展示這沒問題，但若要長期保存使用者資料，建議三選一：

| 方案 | 成本 | 改動 |
| --- | --- | --- |
| 加裝 Render Disk | 約 $1/月（1 GB） | 在 service 設定 → Disks 加一顆 1GB，掛載點 `/var/data`，把 `database/careguide.db` 路徑改成 `/var/data/careguide.db` |
| 改用 Render Postgres | 前 90 天免費，之後 $7/月 | 把 `modules/database.py` 換成用 `psycopg`，改寫 SQL |
| 接受資料會清空 | 免費 | 不用改 |

### 免費方案會「睡眠」

15 分鐘沒人訪問會休眠，下次第一個請求需等約 30 秒喚醒。期末示範前先打開來預熱即可。

### 瀏覽器 cookie 需 HTTPS

Render 預設提供 HTTPS，所以 Flask session 的 cookie 會正常設定，不用改 `app.py`。

### Python 版本

`render.yaml` 已固定 Python 3.12.4。要換版本就改裡面的 `PYTHON_VERSION`。

---

## 檢查清單

部署前確認：

- [ ] `git status` 沒有未提交的變更
- [ ] `.env` **沒有**被 commit 進去（`.gitignore` 已排除）
- [ ] 在 Render 上把 `GEMINI_API_KEY` 設好（如有需要）
- [ ] 第一次部署後，到 URL 開瀏覽器試一次「註冊 → 評估 → 看結果」流程

部署後檢查：

- [ ] 訪問 `https://你的網址.onrender.com/api/health` 應該回 `{"status":"ok"}`
- [ ] 註冊帳號、登入、做評估能正常運作
- [ ] PDF 下載能拿到中文 PDF（Render 的 Linux 容器需安裝 Noto CJK，下方說明）

---

## PDF 中文字型在 Render 上的處理

Render 的 Linux 環境**沒有預裝中文字型**，所以直接用 PDF 下載功能會失敗。有兩種解法：

### 方法 A：下載 Noto Sans TC 字型放入專案（推薦）

1. 從 [Google Fonts](https://fonts.google.com/noto/specimen/Noto+Sans+TC) 下載 Noto Sans TC（OFL 授權，可自由散布）
2. 解壓縮後把 `NotoSansTC-Regular.otf` 放到 `careguide/static/fonts/`
3. 在 `modules/pdf_generator.py` 的 `_FONT_CANDIDATES` 最前面加一行：
   ```python
   (str(Path(__file__).resolve().parent.parent / "static/fonts/NotoSansTC-Regular.otf"), None, "NotoSansTC"),
   ```
4. `git add static/fonts/NotoSansTC-Regular.otf && git commit && git push`

### 方法 B：在 Render 加 build step 安裝字型

把 `render.yaml` 的 `buildCommand` 改成：

```yaml
buildCommand: apt-get update && apt-get install -y fonts-noto-cjk && pip install -r requirements.txt
```

但 Render 的 native runtime 不一定有 root 權限，這方法**不一定成功**，建議優先用方法 A。

---

## 出狀況時看哪裡

- **Render Dashboard → Logs**：即時看部署與運行記錄，最常用
- **Events**：看每次部署、重啟的時間軸
- **Shell**（付費方案才有）：直接進容器除錯

部署過程中最常見的錯誤：

| 錯誤訊息 | 通常原因 |
| --- | --- |
| `ModuleNotFoundError` | 套件沒寫進 `requirements.txt` |
| `Address already in use` | 沒用 `$PORT`（render.yaml 已處理） |
| `KeyError: 'FLASK_SECRET_KEY'` | env var 沒設（render.yaml 會自動產生） |
| PDF 下載 500 | 容器沒中文字型（見上方說明） |

---

## 進階：用 Docker 部署

如果想練習 Docker 或之後要把專案搬到其他雲端，CareGuide 已附上 `Dockerfile`，會在容器內裝好中文字型（文泉驛微米黑），PDF 下載開箱即用。

### 切換到 Docker 模式

```bash
# 把現有的 native 版備份起來，換上 Docker 版
mv render.yaml render.native.yaml
mv render.docker.yaml render.yaml
git add . && git commit -m "switch to docker deploy" && git push
```

Render 偵測到 `render.yaml` 改成 `runtime: docker` 後，會：
1. 讀取 `Dockerfile`
2. Build image（首次約 5–8 分鐘）
3. 用容器啟動服務

### 本機測試 Docker 版

```bash
# 確認 Docker Desktop 已啟動
docker build -t careguide:local .

docker run --rm -p 8001:8000 \
  -e GEMINI_API_KEY=你的key \
  -e FLASK_SECRET_KEY=任意字串 \
  careguide:local

# 開瀏覽器到 http://localhost:8001
```

### Docker vs Native runtime 取捨

| | Native runtime | Docker |
| --- | --- | --- |
| 設定複雜度 | 低 | 中 |
| Build 時間 | 1–2 分鐘 | 5–8 分鐘 |
| Image 大小 | 不適用 | ~250 MB |
| 中文字型 | 需手動加字型檔 | apt 一行解決 |
| 跨平台移植 | 綁 Render | 可移到任何雲 |

對於 demo / 課堂展示，native 已經夠用。要寫進履歷或之後想轉部署平台時再切 Docker。
