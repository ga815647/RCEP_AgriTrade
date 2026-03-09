# RCEP 農產品貿易分析系統 v4.0 — 使用說明

## 系統需求

- Python 3.10+（[下載](https://www.python.org/downloads/)）
- 目前本地磁碟至少需 8GB 可用空間
- **不需要任何付費帳號或 API Key**

## 安裝

```bash
git clone [repo_url]
cd rcep_agri_trade
pip install -r requirements.txt
```

## 首次使用：手動準備步驟（只需做一次）

### 步驟 P1（30–60 分鐘）：下載 BACI 最新版本

前往 `https://www.cepii.fr/CEPII/en/bdd_modele/bdd_modele_item.asp?id=37`
**不需要註冊帳號**，直接下載最新版本的三個 zip 壓縮檔。

| BACI 版本 | 下載檔案範例 | 解壓縮路徑 |
|---------|---------|-----------|
| **BACI HS07** | `BACI_HS07_V202XXXX.zip` | `data/raw/baci/hs07/` |
| **BACI HS12** | `BACI_HS12_V202XXXX.zip` | `data/raw/baci/hs12/` |
| **BACI HS17** | `BACI_HS17_V202XXXX.zip` | `data/raw/baci/hs17/` |

> ⚠️ 注意：各版本的資料夾中應包含其附帶的 `product_codes_HS*_V*.csv`，系統會自動根據資料年份補入正確的英文商品說明。國家代碼則統一由 `hs17` 目錄讀取。

### 步驟 P2（5 分鐘）：下載 HS 版本對照表

請直接點擊以下連結下載 UN Stats 提供的對照表，並放入 `data/reference/`：

1. [HS2017 to HS2007 Conversion](https://unstats.un.org/unsd/classifications/Econ/tables/HS2017toHS2007ConversionAndCorrelationTables.xlsx)
2. [HS2017 to HS2012 Conversion](https://unstats.un.org/unsd/classifications/Econ/tables/HS2017toHS2012ConversionAndCorrelationTables.xlsx)

> **檔名說明**：請保持原始長檔名（如 `HS2017toHS2007...xlsx`），系統已設定為自動反轉映射方向且支援 6 碼補零與金額等比分配。

## 啟動系統

```bash
streamlit run app.py
```

瀏覽器會自動開啟，系統啟動後會先執行「環境檢查」：
- ✅ 代表檔案已就緒。
- ❌ 代表檔案缺失，請檢查資料夾路徑與檔名是否與上述步驟一致。

## 操作說明

1. **設定年份**：拖拉側邊欄的年份滑桿選擇分析範圍（預設 2007–2024）。
2. **設定 Top N**：預設取前 10 大品項。
3. **執行分析**：點選「▶ 開始執行」。系統會自動從 BACI 取用台灣資料（M49=490），無須連網。
4. **下載結果**：執行完成後，點選下方出現的「📥 下載 Excel 報表」。

## 常見問題 (FAQ)

**Q：台灣數據來自哪裡？**
A：本系統為貫徹單一來源，台灣數據（M49=490）直接由 BACI 本地 CSV 過濾取得。這避開了財政部關務署 URL 經常失效的問題。

**Q：2023–2024 年的資料為什麼有 provisional 標記？**
A：BACI 的最新兩年通常為初步估計值，未來發布新版本時可能會有些微修正。

**Q：為什麼不需要 HS22 對照表？**
A：BACI HS17 版本已經包含了 2022-2024 年的數據，且代碼已經統一轉換為 HS2017。因此使用 HS17 版本即可涵蓋至 2024 年。
