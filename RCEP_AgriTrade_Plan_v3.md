# RCEP 農產品貿易動態數據分析計畫 v3.0
## 商業分析版 · 純 BACI 本地方案 · 零 API 請求 · Streamlit GUI

> **v3 變更摘要**：
> - v1 → v2：修正台灣數據來源、WITS 請求量爆炸、HS 版本等 4 個致命錯誤
> - v2 → v3：驗證 BACI 版本後，發現 HS17 只從 2017 開始（非 2010），改為三版本路由；
>   同時確認 BACI 202601 已涵蓋 2024 年，完全移除 WITS 必要邏輯，API 請求次數降為 **0**。

---

## 目錄

1. [可行性審查報告（所有已知問題）](#1-可行性審查報告)
2. [核心架構](#2-核心架構)
3. [數據來源策略](#3-數據來源策略)
4. [執行階段詳細說明](#4-執行階段詳細說明)
5. [請求量與時間估計](#5-請求量與時間估計)
6. [HS Code 版本處理邏輯](#6-hs-code-版本處理邏輯)
7. [專案目錄結構](#7-專案目錄結構)
8. [Streamlit GUI 設計規格](#8-streamlit-gui-設計規格)
9. [給 AI Agent 的最終指令（可直接複製）](#9-給-ai-agent-的最終指令)
10. [README 使用教學](#10-readme-使用教學)
11. [已知風險與備用方案矩陣](#11-已知風險與備用方案矩陣)

---

## 1. 可行性審查報告

本節記錄從原始計畫到 v3 所有已發現並修正的問題，作為決策紀錄。

### 🔴 原計畫致命錯誤（v2 已修正）

| 錯誤 | 原始問題 | 修正方案 |
|------|---------|---------|
| A | portal.sw.nat.gov.tw 無 API，直接請求只得到 HTML | 改用財政部關務署 data.gov.tw 開放 CSV |
| B | WITS 請求量：15×15×10×15 = 33,750 次，需 67 天 | 改用 BACI 本地檔案，API 請求 = 0 |
| C | 台灣在 Comtrade/WITS 數據缺口（2020+ 不穩定）| 台灣數據強制改用本地關務署，不依賴任何 API |
| D | HS Code 跨 2007/2012/2017/2022 四版本，未處理 | 三版本 BACI 路由 + HS2017 統一轉換 |

### 🔴 v2 計畫新發現問題（v3 修正）

| 問題 | v2 的錯誤假設 | 實際情況 | v3 修正 |
|------|------------|---------|--------|
| **E（致命）** | BACI HS17 可涵蓋 2010–2024 | HS17 只從 **2017** 開始，2010–2016 需 HS07/HS12 | 三版本路由：HS07 + HS12 + HS17 |
| **F（大幅改善）** | BACI 最新到 2021，需 WITS 補 2022–2024 | BACI **202601** 版已有 **2024** 年數據 | 完全移除 WITS 必要邏輯；WITS 降為可選的交叉驗證 |
| **G（需手動確認）** | 2010–2012 台灣關務署欄位名稱已知 | 欄位名稱為推估，未對照實際檔案驗證 | README 加入「啟動前必做」手動確認步驟 |

### 🟡 設計缺陷（v2 已修正，v3 保留）

- **E**：數據品質標記（BACI 版本、2023–2024 初步值旗標、HS 轉換旗標）
- **F**：斷點續傳（SQLite 快取，重啟後繼續）
- **G**：輸出多工作表（長表 + 樞紐表 + 品質報告）

---

## 2. 核心架構

```
┌─────────────────────────────────────────────────────────────────┐
│                      Streamlit GUI 前端                           │
│  [年份滑桿] [Top N] [RCEP 國家選擇] [▶執行] [⏸暫停] [🔄繼續]    │
└───────────────────────────┬─────────────────────────────────────┘
                            │  start_year, end_year, top_n
┌───────────────────────────▼─────────────────────────────────────┐
│                      主控 Pipeline                                │
│                                                                   │
│  Stage 1              Stage 2              Stage 3   Stage 4     │
│  台灣數據     →      RCEP 數據    →      整合清理 → 輸出報表    │
│  data.gov.tw          BACI 本地              HS 統一    Excel    │
│  (自動下載)           (三版本路由)           轉換      多工作表  │
└──────────┬────────────────┬────────────────────────────────────┘
           │                │
  ┌────────▼──────┐  ┌──────▼──────────────────────────────┐
  │  台灣關務署   │  │  BACI 本地 CSV（手動下載，三版本）   │
  │  data.gov.tw  │  │  HS07: 2010–2011                     │
  │  年度 zip     │  │  HS12: 2012–2016                     │
  │  (程式下載)   │  │  HS17: 2017–2024（含 2024 初步值）   │
  └───────────────┘  └──────────────────────────────────────┘
           │                │
  ┌────────▼────────────────▼────────┐
  │        本地快取層 (SQLite)        │
  │   進度記錄、斷點續傳、溯源日誌    │
  └───────────────────────────────────┘
```

**關鍵設計原則**：
- 台灣數據（目標 A）和 RCEP 內部數據（目標 B）來自不同來源，在 Stage 3 整合
- BACI 涵蓋 RCEP 15 國之間的所有貿易方向（Reporter × Partner 全矩陣）
- 台灣不在 BACI 中取用（因為 BACI 的台灣數據不完整），台灣 → RCEP 的流向只從關務署取
- API 請求次數 = **0**（純本地解析）

---

## 3. 數據來源策略

### 策略總覽

| 數據需求 | 來源 | 取得方式 | API 請求 |
|---------|------|---------|---------|
| 台灣 → RCEP 出口（目標 A） | 財政部關務署 data.gov.tw | 程式自動下載 | 0（HTTP 下載，非 API） |
| RCEP 內部貿易 2010–2011（目標 B）| BACI HS07（CEPII） | 手動下載 2 個 CSV | 0 |
| RCEP 內部貿易 2012–2016（目標 B）| BACI HS12（CEPII） | 手動下載 5 個 CSV | 0 |
| RCEP 內部貿易 2017–2024（目標 B）| BACI HS17（CEPII） | 手動下載 8 個 CSV | 0 |
| HS Code 說明與版本對照 | BACI 附帶 nomenclature CSV | 程式自動讀取 | 0 |

**總 API 請求次數：0** ← 完全本地

---

### 來源 A：台灣出口數據（程式自動下載）

**資料集**：財政部關務署「進出口貿易統計」open data
```
URL 格式：https://portal.sw.nat.gov.tw/PPL/OpenData/{year}Y_ExportDetail.zip
範例：https://portal.sw.nat.gov.tw/PPL/OpenData/2015Y_ExportDetail.zip
```

**欄位結構與年份映射**（⚠️ 注意：2010–2012 欄位名稱不同，使用前須手動確認一次，見 README 步驟 P1）

| 年份區間 | 年份欄 | HS碼欄（取前6碼）| 國家欄 | 金額欄（USD）| 流向欄 |
|----------|--------|---------|--------|--------|--------|
| 2010–2012 | `YM`（取前4字元）| `CCC_CODE` | `CTY_CODE` | `USD_VALUE` | `EXP_IMP` |
| 2013–2017 | `YEAR` | `HS_CODE` | `COUNTRY_CODE` | `VALUE_USD` | `TYPE` |
| 2018–今 | `YEAR` | `HS_CODE` | `COUNTRY` | `VALUE_USD` | `EXP_IMP` |

> ⚠️ 上表欄位名稱為**推估值**，正式開發前須執行 README 步驟 P1 手動確認。

**過濾條件**：
- 流向 = 出口（`EXP_IMP == 'E'` 或 `TYPE == 'E'`）
- 國家代碼 ∈ RCEP 15 國清單
- HS 前兩碼 ∈ `['01','02',...,'24']`

---

### 來源 B：BACI 三版本（手動下載，RCEP 內部貿易）

**BACI 是什麼**：法國 CEPII 出版的全球貿易數據庫，對 Reporter 出口與 Partner 進口做跨國調和，品質高於 Comtrade 原始數據，是學術與商業報告最常引用的免費貿易數據集。

**最新版本**：202601（2026 年 1 月發布），涵蓋至 **2024 年**

**下載網址**：`http://www.cepii.fr/CEPII/en/bdd_modele/bdd_modele_item.asp?id=37`

**需下載的三個版本及年份**：

| BACI 版本 | 涵蓋年份 | 本計畫需要的年份 | 檔案數量 |
|-----------|---------|--------------|---------|
| **HS07** | 2007–2024 | 2010–2011（取 2 年）| 2 個 CSV |
| **HS12** | 2012–2024 | 2012–2016（取 5 年）| 5 個 CSV |
| **HS17** | 2017–2024 | 2017–2024（取 8 年）| 8 個 CSV |

> **為何選 HS07 而非 HS12 來涵蓋 2010–2011？**
> HS12 從 2012 年才開始，無法提供 2010–2011 的數據，只有 HS07 有。

**BACI CSV 格式**（三個版本格式相同）：
```
t,    i,    j,    k,       v,       q
2015, 156,  764,  030389,  5243.2,  1820
```

| 欄位 | 說明 |
|------|------|
| `t` | 年份 |
| `i` | 出口國 UN M49 代碼 |
| `j` | 進口國 UN M49 代碼 |
| `k` | HS6 商品代碼（字串，注意前導零） |
| `v` | 貿易額（千美元） |
| `q` | 數量（噸） |

**RCEP 國家 M49 對照表**：

| ISO2 | ISO3 | M49 | 中文名 |
|------|------|-----|-------|
| BN | BRN | 96 | 汶萊 |
| KH | KHM | 116 | 柬埔寨 |
| ID | IDN | 360 | 印尼 |
| LA | LAO | 418 | 寮國 |
| MY | MYS | 458 | 馬來西亞 |
| MM | MMR | 104 | 緬甸 |
| PH | PHL | 608 | 菲律賓 |
| SG | SGP | 702 | 新加坡 |
| TH | THA | 764 | 泰國 |
| VN | VNM | 704 | 越南 |
| CN | CHN | 156 | 中國 |
| JP | JPN | 392 | 日本 |
| KR | KOR | 410 | 韓國 |
| AU | AUS | 36 | 澳洲 |
| NZ | NZL | 554 | 紐西蘭 |

> 台灣（TWN, M49=490）**不從 BACI 取用**，台灣 ↔ RCEP 流向全部來自關務署數據。

---

### 來源 C：HS Code 版本對照表（程式自動讀取）

BACI 下載包內附帶：
- `HS07_nomenclature.csv`：HS07 代碼與說明
- `HS12_nomenclature.csv`：HS12 代碼與說明
- `HS17_nomenclature.csv`：HS17 代碼與說明（本計畫基準版本）

版本轉換對照表（跨版本比較用）：
- 下載來源：`https://unstats.un.org/unsd/trade/classifications/correspondence-tables.asp`
- 需下載：HS2007→HS2017、HS2012→HS2017 兩個 Excel（**不需要** HS2022，因為 HS17 版 BACI 已統一）

---

## 4. 執行階段詳細說明

### 階段 0：環境準備（一次性）

#### 套件安裝
```bash
pip install streamlit pandas openpyxl requests tqdm loguru pyyaml
# sqlite3 為 Python 內建，無需安裝
```

#### ✋ 手動操作清單（按順序，執行一次即可）

| 步驟 | 動作 | 時間 | 注意事項 |
|------|------|------|---------|
| **P1（必做）** | 手動下載 2010 年關務署 zip，用 Excel 打開，核對實際欄位名稱是否與表格一致，不符則修改 `config.yaml` 的 `column_mapping` | 5 分鐘 | 欄位錯誤會導致 Stage 1 全失敗 |
| **P2** | 到 CEPII 免費註冊帳號 | 5 分鐘 | 確認 email 才能下載 |
| **P3** | 下載 BACI HS07（2010–2011 年，2 個 zip）| 15 分鐘 | 版本選 202601 |
| **P4** | 下載 BACI HS12（2012–2016 年，5 個 zip）| 30 分鐘 | 版本選 202601 |
| **P5** | 下載 BACI HS17（2017–2024 年，8 個 zip）| 60 分鐘 | 版本選 202601 |
| **P6** | 將所有 zip 解壓縮，CSV 放入對應子資料夾 | 15 分鐘 | 見目錄結構第 7 節 |
| **P7** | 下載 HS2007→HS2017、HS2012→HS2017 對照表，放入 `data/reference/` | 5 分鐘 | UN Stats 免費下載 |

**總手動時間：約 2–2.5 小時（主要是下載等待，可以邊做別的事）**

---

### 階段一：建立台灣 Top10 基準清單

**目的**：達成目標 A，並產出每年的 Top10 HS6 清單，供 Stage 2 過濾 BACI 用

**輸入**：`start_year`、`end_year`（來自 GUI session_state）
**輸出**：`top10_dict` = `{"2010": ["030389", "100190", ...], "2011": [...], ...}`

**執行邏輯**：
```
對每個年份 y in range(start_year, end_year + 1)：

  1. 查 SQLite 快取（taiwan_top10 表），若命中則跳過下載
  2. 若無快取：
     a. 下載 https://portal.sw.nat.gov.tw/PPL/OpenData/{y}Y_ExportDetail.zip
     b. 解壓縮，讀入 CSV
     c. 根據 column_mapping[y] 統一欄位名稱
     d. 過濾：流向 = 出口
     e. 過濾：國家代碼 ∈ RCEP_15_CODES
     f. 過濾：HS6[:2] ∈ {'01','02',...,'24'}
     g. 以 HS6 前 6 碼 groupby 加總 VALUE_USD
     h. 排序，取前 top_n 名（來自 GUI，預設 10）
     i. 寫入 SQLite 快取
  3. 累積至 top10_dict
```

---

### 階段二：抓取 RCEP 內部貿易矩陣（純 BACI 本地解析）

**目的**：達成目標 B，取得 RCEP 15 國之間在 Top10 品項上的全矩陣出口數據

**輸入**：`top10_dict`、`start_year`、`end_year`
**輸出**：`rcep_df`，長表格式

**BACI 版本路由邏輯**（年份邊界是 HS 標準定義，允許出現在程式碼中）：
```python
BACI_VERSION_ROUTER = {
    range(2010, 2012): "HS07",   # 2010–2011
    range(2012, 2017): "HS12",   # 2012–2016
    range(2017, 2025): "HS17",   # 2017–2024
}
```

**執行邏輯**：
```
對每個年份 y in range(start_year, end_year + 1)：

  1. 查 SQLite 快取（baci_trade 表），若命中則跳過
  2. 若無快取：
     a. 查 BACI_VERSION_ROUTER[y] → 得到版本（HS07/HS12/HS17）
     b. 組合路徑：data/raw/baci/{version}/BACI_{version}_Y{y}_V202601.csv
     c. 若檔案不存在 → 拋出明確錯誤，告知使用者下載哪個檔案
     d. 讀入 CSV（dtype={"k": str} 保留前導零）
     e. 過濾：i ∈ RCEP_M49_SET AND j ∈ RCEP_M49_SET
     f. 過濾：k[:2] ∈ {'01','02',...,'24'}
     g. 過濾：k ∈ set(top10_dict[str(y)])（只保留 Top10 品項）
     h. 標記：baci_version = 版本, data_provisional = (y >= 2023)
     i. 轉換欄位名稱至標準格式
     j. 寫入 SQLite 快取
  3. 累積至 rcep_df
```

---

### 階段三：數據清理與整合

#### 3.1 HS Code 版本轉換（轉換至 HS2017 基準）

```python
def get_hs_version_for_baci(baci_version: str) -> str:
    mapping = {"HS07": "HS2007", "HS12": "HS2012", "HS17": "HS2017"}
    return mapping[baci_version]

def harmonize_to_hs2017(hs6: str, source_version: str, concordance: dict) -> list[tuple]:
    """
    回傳 [(hs2017_code, weight), ...]
    一對一：[(new_code, 1.0)]
    一對多（舊代碼拆分）：[(new_code1, 0.5), (new_code2, 0.5)]
    """
    if source_version == "HS2017":
        return [(hs6, 1.0)]
    mapping = concordance.get(source_version, {}).get(hs6)
    if mapping is None:
        return [(hs6, 1.0)]  # 無對照，保留原碼，標記 hs_mapped=False
    return [(code, 1.0 / len(mapping)) for code in mapping]
```

> HS07/HS12 版本的 BACI 數據需要轉換，HS17 版本無需轉換（已是基準版本）。

#### 3.2 台灣數據整合

```python
# 台灣出口數據：Reporter=Taiwan，Partner=各 RCEP 國
taiwan_df["Reporter"]      = "Taiwan"
taiwan_df["Reporter_ISO3"] = "TWN"
taiwan_df["Reporter_M49"]  = 490
taiwan_df["Reporter_Group"]= "Taiwan"
taiwan_df["data_source"]   = "taiwan_customs"

# 合併：台灣出口 + RCEP 內部貿易
final_df = pd.concat([rcep_df, taiwan_df], ignore_index=True)
```

#### 3.3 遺失值處理策略

| 情況 | 處理方式 |
|------|---------|
| BACI 中某筆流向無數據 | 保留為 `NULL`（不填 0，0 和無數據意義不同）|
| 2023–2024 BACI 初步值 | 標記 `data_provisional=True`，不修改數值 |
| HS 代碼無對照表 | 保留原碼，標記 `hs_mapped=False` |
| 小國（BN/LA/MM）數據稀疏 | 標記 `data_quality='sparse'`，不填充 |

---

### 階段四：輸出報表生成

**輸出檔案**：`output/RCEP_AgriTrade_{start_year}_{end_year}_{timestamp}.xlsx`

**工作表清單**：

| 工作表名稱 | 內容 | 主要用途 |
|-----------|------|---------|
| `長表_完整數據` | 所有記錄，長格式，含全部欄位 | 後續 Python/Excel 分析的主表 |
| `Top10_HS6_清單` | 每年台灣 Top10 品項（HS6 代碼+說明+金額）| 快速確認關注品項 |
| `台灣_RCEP出口明細` | 台灣 → 各 RCEP 國，逐年逐品項 | 目標 A 核心報表 |
| `RCEP內部_出口矩陣` | Reporter × Partner × 年份，Top10 品項加總 | 目標 B 核心報表（如日→韓）|
| `年度彙整_出口總額` | 各國各年度農產品出口至 RCEP 合計 | 趨勢分析 |
| `數據品質報告` | 每筆記錄的來源、版本、轉換旗標 | 商業報告可信度聲明 |

**完整欄位定義**：

| 欄位名稱 | 型態 | 說明 |
|---------|------|------|
| `Year` | INT | 年份（來自 GUI 設定） |
| `HS6_Code` | STR(6) | HS6 代碼（統一為 HS2017） |
| `HS6_Code_Original` | STR(6) | 原始年份版本的 HS6 代碼（轉換前）|
| `HS6_Description_EN` | STR | 英文說明（來自 BACI nomenclature）|
| `HS6_Description_ZH` | STR | 中文說明（對照表補入）|
| `HS_Chapter` | STR(2) | HS 前兩碼（01–24）|
| `Reporter` | STR | 出口國名稱 |
| `Reporter_ISO3` | STR(3) | 出口國 ISO3 代碼 |
| `Reporter_Group` | STR | `ASEAN10` / `RCEP5` / `Taiwan` |
| `Partner` | STR | 進口國名稱 |
| `Partner_ISO3` | STR(3) | 進口國 ISO3 代碼 |
| `Value_USD` | FLOAT | 貿易額（美元，BACI 千美元 × 1000）|
| `Value_USD_1000` | FLOAT | 貿易額（千美元，BACI 原始單位）|
| `data_source` | STR | `baci` / `taiwan_customs` |
| `baci_version` | STR | `HS07` / `HS12` / `HS17` / `N/A`（台灣數據）|
| `data_provisional` | BOOL | True = 2023–2024 BACI 初步值，可能被未來版本修正 |
| `hs_converted` | BOOL | True = HS 代碼已做版本轉換 |
| `hs_mapped` | BOOL | False = 找不到對照表，原碼保留 |
| `hs_split` | BOOL | True = 一對多轉換，金額已等比分配 |
| `data_quality` | STR | `verified` / `sparse` / `provisional` |
| `Taiwan_Top10_Flag` | BOOL | True = 此品項為當年台灣 Top10 |

---

## 5. 請求量與時間估計

### 請求量

| 數據段 | 方式 | API 請求次數 |
|--------|------|------------|
| 台灣出口（全年份）| HTTP ZIP 下載 | 0（非 API，直接下載）|
| RCEP 內部 2010–2011 | BACI HS07 本地解析 | **0** |
| RCEP 內部 2012–2016 | BACI HS12 本地解析 | **0** |
| RCEP 內部 2017–2024 | BACI HS17 本地解析 | **0** |
| **合計** | | **0 次 API 請求** |

### 時間估計（預設 2010–2024）

```
T+0:00   ✋ 手動：CEPII 免費註冊（5 分鐘）
T+0:05   ✋ 手動：下載 BACI HS07（2個zip）+ HS12（5個）+ HS17（8個）
          → 共 15 個 zip，視網速約 60–120 分鐘（可背景執行）
T+2:00   ✋ 手動：解壓縮，放入對應資料夾（15 分鐘）
T+2:15   ✋ 手動：P1 步驟：確認 2010 年關務署欄位名稱（5 分鐘）

T+2:20   ▶ 啟動程式（streamlit run app.py）
T+2:50   Stage 1 完成：台灣數據下載與 Top10 計算（30 分鐘，15 年）
T+3:10   Stage 2 完成：BACI 三版本解析（20 分鐘，純本地運算）
T+3:25   Stage 3 完成：整合清理、HS 轉換（15 分鐘）
T+3:30   Stage 4 完成：Excel 報表生成 ✅

總計：約 3.5 小時（含手動下載等待），API 請求 = 0
```

> **若只分析部分年份**（如 2017–2024）：只需下載 BACI HS17（8個zip），手動時間約 30 分鐘，程式約 45 分鐘，合計不到 1.5 小時。

---

## 6. HS Code 版本處理邏輯

### 版本分界（HS 國際標準定義，固定值）

| 年份 | BACI 版本 | HS 分類版本 |
|------|----------|-----------|
| 2010–2011 | HS07 | HS2007 |
| 2012–2016 | HS12 | HS2012 |
| 2017–2024 | HS17 | HS2017（基準版本）|

> HS2022 在本計畫中**不使用**：HS17 版的 BACI 已統一為 HS2017，不會出現 HS2022 代碼。

### 轉換方向

```
BACI HS07 數據（2010–2011）→ HS2007 代碼 → 轉換至 HS2017
BACI HS12 數據（2012–2016）→ HS2012 代碼 → 轉換至 HS2017
BACI HS17 數據（2017–2024）→ HS2017 代碼 → 無需轉換（已是基準）
```

### 農產品（HS01–24）版本變動重要章節

| HS 章 | 主要變動 | 影響 |
|-------|---------|------|
| 03（魚類）| HS2012→HS2017 大幅調整細項 | 轉換必做，影響最多 |
| 02（肉類）| HS2012→HS2017 部分重新分類 | 影響中等 |
| 08（水果）| HS2017 新增數個 6 碼 | 影響小 |
| 21（雜項食品）| HS2017 部分拆分 | 影響小 |

### 一對多轉換的金額分配

若舊代碼 `A` 對應到新代碼 `A1`、`A2` 兩個，則：
- `Value_USD(A1) = Value_USD(A) × 0.5`
- `Value_USD(A2) = Value_USD(A) × 0.5`
- 標記 `hs_split = True`

---

## 7. 專案目錄結構

```
rcep_agri_trade/
│
├── app.py                          # Streamlit GUI 主程式
├── config.yaml                     # 設定檔（見下方）
├── requirements.txt
├── README.md
│
├── pipeline/
│   ├── __init__.py
│   ├── stage1_taiwan.py            # 台灣關務署數據下載與 Top10 計算
│   ├── stage2_baci.py              # BACI 三版本路由與本地解析
│   ├── stage3_clean.py             # 整合、HS 版本轉換、遺失值處理
│   └── stage4_export.py            # Excel 多工作表輸出
│
├── utils/
│   ├── cache.py                    # SQLite 快取（斷點續傳）
│   ├── hs_harmonizer.py            # HS Code 版本轉換邏輯
│   ├── country_codes.py            # M49 ↔ ISO3 ↔ 中文名對照
│   └── validators.py               # 欄位驗證、數據品質檢查
│
├── data/
│   ├── reference/                  # 靜態參考資料（手動放入）
│   │   ├── HS2007_to_HS2017.xlsx   # 從 UN Stats 下載
│   │   ├── HS2012_to_HS2017.xlsx   # 從 UN Stats 下載
│   │   └── hs6_descriptions_zh.csv # HS6 中文說明（可選）
│   ├── raw/
│   │   ├── baci/
│   │   │   ├── hs07/               # 手動放入 BACI HS07 CSV
│   │   │   │   ├── BACI_HS07_Y2010_V202601.csv
│   │   │   │   └── BACI_HS07_Y2011_V202601.csv
│   │   │   ├── hs12/               # 手動放入 BACI HS12 CSV
│   │   │   │   ├── BACI_HS12_Y2012_V202601.csv
│   │   │   │   ├── ...
│   │   │   │   └── BACI_HS12_Y2016_V202601.csv
│   │   │   └── hs17/               # 手動放入 BACI HS17 CSV
│   │   │       ├── BACI_HS17_Y2017_V202601.csv
│   │   │       ├── ...
│   │   │       └── BACI_HS17_Y2024_V202601.csv
│   │   └── taiwan/                 # 程式自動下載（無需手動）
│   └── cache/
│       └── trade_cache.db          # SQLite 快取（自動建立）
│
└── output/
    └── RCEP_AgriTrade_2010_2024_*.xlsx
```

### config.yaml

```yaml
# ===== 預設值設定 =====
# GUI 啟動時載入作為預設；使用者透過 GUI 修改後，以 session_state 為準

time_range:
  start: 2010      # GUI 滑桿預設左端
  end: 2024        # GUI 滑桿預設右端

top_n: 10          # 每年取前幾名 HS6（GUI 可調整 5–20）

rcep_countries:
  asean10: [BN, KH, ID, LA, MY, MM, PH, SG, TH, VN]
  others:  [CN, JP, KR, AU, NZ]

agriculture_hs_chapters: [1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24]

hs_base_version: "HS2017"

# BACI 版本路由（年份邊界固定，通常不需修改）
baci:
  version_router:
    "2010-2011": "HS07"
    "2012-2016": "HS12"
    "2017-2024": "HS17"
  baci_dir: "data/raw/baci"
  filename_pattern: "BACI_{version}_Y{year}_V202601.csv"   # ← CEPII 更新版本號時修改此處

# 台灣數據來源
taiwan_customs:
  base_url: "https://portal.sw.nat.gov.tw/PPL/OpenData/{year}Y_ExportDetail.zip"
  # 欄位映射（P1 步驟驗證後填入正確值）
  column_mapping:
    "2010-2012":
      year_col: "YM"           # 取前 4 字元作為年份
      hs_col: "CCC_CODE"       # ⚠️ 需 P1 步驟確認
      country_col: "CTY_CODE"  # ⚠️ 需 P1 步驟確認
      value_col: "USD_VALUE"   # ⚠️ 需 P1 步驟確認
      flow_col: "EXP_IMP"
      export_flag: "E"
    "2013-2017":
      year_col: "YEAR"
      hs_col: "HS_CODE"
      country_col: "COUNTRY_CODE"
      value_col: "VALUE_USD"
      flow_col: "TYPE"
      export_flag: "E"
    "2018-2025":
      year_col: "YEAR"
      hs_col: "HS_CODE"
      country_col: "COUNTRY"
      value_col: "VALUE_USD"
      flow_col: "EXP_IMP"
      export_flag: "E"

output:
  format: excel
  language: zh
  include_quality_sheet: true
  output_dir: "output"
```

---

## 8. Streamlit GUI 設計規格

### 版面配置

```
┌───────────────────────────────────────────────────────────────┐
│  🌾 RCEP 農產品貿易分析系統  v3.0                              │
├──────────────────┬────────────────────────────────────────────┤
│  ⚙️ 側邊欄        │  主要內容區                                │
│                  │                                            │
│ 📅 時間範圍      │  ① 環境檢查（啟動時自動執行）               │
│ ◀2010━━━━2024▶  │  ✅ BACI HS07：2010, 2011                  │
│ (可自由拖拉)     │  ✅ BACI HS12：2012–2016                   │
│                  │  ✅ BACI HS17：2017–2024                   │
│ 🔢 Top N         │  ✅ HS 對照表                              │
│ [10  ▲▼]        │  ⚠️ 台灣欄位需確認（P1 步驟）              │
│                  │  ─────────────────────────────────         │
│ 🗺️ RCEP 國家     │  ② 執行進度                               │
│ ☑ 全選           │  Stage 1 台灣數據  ████████████ 100% ✅   │
│ ☑ ASEAN10       │  Stage 2 BACI解析  ████████░░░░  67% 🔄   │
│ ☑ CN JP KR AU NZ│  Stage 3 整合清理  ░░░░░░░░░░░░   0% ⏳   │
│                  │  Stage 4 輸出報表  ░░░░░░░░░░░░   0% ⏳   │
│ [▶ 開始執行]     │  ─────────────────────────────────         │
│ [⏸ 暫停]        │  ③ 即時日誌（最新 100 行）                  │
│ [🔄 繼續]       │  10:23:41 [OK]  BACI HS12 2015 讀入完成   │
│                  │  10:23:52 [OK]  Top10 2015 計算完成        │
│ ─────────────── │  10:24:05 [WARN] BN/LA/MM 數據稀疏         │
│ 📊 數據預覽      │  ─────────────────────────────────         │
│ 年份 [2015 ▼]   │  ④ 完成後顯示                              │
│ 國家 [全部 ▼]   │  [互動表格] [趨勢圖] [熱力圖]              │
│ HS章 [全部 ▼]   │  [📥 下載 Excel]  [📥 下載 CSV]           │
└──────────────────┴────────────────────────────────────────────┘
```

### 主要 UI 功能細節

**1. 年份範圍滑桿**
```python
start_year, end_year = st.slider(
    "📅 時間範圍",
    min_value=2010,    # BACI HS07 最早 2007，但本計畫最早到 2010
    max_value=2024,    # BACI 202601 最新到 2024
    value=(2010, 2024),
    step=1
)
st.session_state["start_year"] = start_year
st.session_state["end_year"]   = end_year

# 滑桿下方即時顯示
years_needed = range(start_year, end_year + 1)
versions_needed = set()  # 計算需要哪些 BACI 版本
# ... 顯示：「需要 BACI HS07（2年）+ HS17（8年），預估程式執行時間：約 XX 分鐘」
```

**2. 環境檢查面板**（開啟頁面時自動掃描）

```python
def check_environment(start_year, end_year, cfg) -> dict:
    """掃描所有必要檔案是否存在，回傳狀態字典"""
    status = {}
    for year in range(start_year, end_year + 1):
        version = get_baci_version(year)
        path = build_baci_path(year, version, cfg)
        status[f"baci_{year}"] = "ok" if os.path.exists(path) else "missing"
    # 也檢查 HS 對照表、reference 資料夾等
    return status
```

若有缺失檔案，顯示紅色警告並列出具體要下載哪個版本的哪一年。

**3. 🚫 絕對禁止**：所有年份迴圈只能使用 `session_state["start_year"]`、`session_state["end_year"]`，不得有任何硬編碼年份數字（BACI 版本邊界除外）。

---

## 9. 給 AI Agent 的最終指令（可直接複製）

---

> **請根據以下規格，使用 Python 3.10+ 編寫完整的自動化腳本與 Streamlit GUI。**

### 🚫 絕對禁止事項（最高優先級）

> 在任何業務邏輯的 Python 程式碼中，**嚴禁將分析年份寫死**。
>
> 禁止的寫法範例：`range(2010, 2025)`、`year == 2024`、`if year > 2021`（業務邏輯中）
>
> 所有年份迴圈必須使用 `st.session_state["start_year"]` 和 `st.session_state["end_year"]`。
>
> **允許出現固定年份的唯一情況**：
> - `config.yaml` 中的預設值
> - BACI 版本路由表（`range(2010, 2012): "HS07"` 等，屬於 HS 國際標準邊界，非業務邏輯）

---

### 任務目標

建立可執行的 Python 應用程式，抓取使用者指定年份範圍內：
1. **目標 A**：台灣對 RCEP 15 國出口的農產品（HS01–24）每年前 N 大 HS6 品項
2. **目標 B**：上述品項中，RCEP 15 國之間「任意方向」的出口數據（完整 Reporter × Partner 矩陣）

輸出為標準化 Excel 報表，供商業分析使用。

---

### 技術規格

**1. 套件需求**
```
Python 3.10+
streamlit >= 1.32
pandas >= 2.0
openpyxl >= 3.1
requests >= 2.31
tqdm >= 4.66
loguru >= 0.7
pyyaml >= 6.0
sqlite3（內建）
```

**2. 台灣數據抓取（Stage 1）**

```python
# 台灣關務署開放資料
TAIWAN_URL = cfg["taiwan_customs"]["base_url"]  # 從 config 讀取，非硬編碼

# RCEP 國家代碼（M49 ↔ ISO3 ↔ 關務署代碼）
RCEP_COUNTRY_MAPPING = {
    "BN": {"m49": 96,  "iso3": "BRN", "name_zh": "汶萊"},
    "KH": {"m49": 116, "iso3": "KHM", "name_zh": "柬埔寨"},
    "ID": {"m49": 360, "iso3": "IDN", "name_zh": "印尼"},
    "LA": {"m49": 418, "iso3": "LAO", "name_zh": "寮國"},
    "MY": {"m49": 458, "iso3": "MYS", "name_zh": "馬來西亞"},
    "MM": {"m49": 104, "iso3": "MMR", "name_zh": "緬甸"},
    "PH": {"m49": 608, "iso3": "PHL", "name_zh": "菲律賓"},
    "SG": {"m49": 702, "iso3": "SGP", "name_zh": "新加坡"},
    "TH": {"m49": 764, "iso3": "THA", "name_zh": "泰國"},
    "VN": {"m49": 704, "iso3": "VNM", "name_zh": "越南"},
    "CN": {"m49": 156, "iso3": "CHN", "name_zh": "中國"},
    "JP": {"m49": 392, "iso3": "JPN", "name_zh": "日本"},
    "KR": {"m49": 410, "iso3": "KOR", "name_zh": "韓國"},
    "AU": {"m49": 36,  "iso3": "AUS", "name_zh": "澳洲"},
    "NZ": {"m49": 554, "iso3": "NZL", "name_zh": "紐西蘭"},
}

# 欄位映射（從 config.yaml 讀取，不在程式碼中硬編碼）
def get_column_mapping(year: int, cfg: dict) -> dict:
    for year_range_str, mapping in cfg["taiwan_customs"]["column_mapping"].items():
        start, end = map(int, year_range_str.split("-"))
        if start <= year <= end:
            return mapping
    raise ValueError(f"找不到 {year} 年的欄位映射，請更新 config.yaml")

def run_stage1(start_year: int, end_year: int, top_n: int, cfg: dict) -> dict:
    """回傳 {str(year): [hs6_code, ...]} 的 Top N 清單"""
    top10_dict = {}
    agr_chapters = {f"{i:02d}" for i in cfg["agriculture_hs_chapters"]}
    rcep_sw_codes = {v["iso3"] for v in RCEP_COUNTRY_MAPPING.values()}  # 關務署用的國家代碼

    for year in range(start_year, end_year + 1):
        cached = cache_db.get_taiwan_top10(year)
        if cached:
            top10_dict[str(year)] = cached
            continue

        url = cfg["taiwan_customs"]["base_url"].format(year=year)
        col = get_column_mapping(year, cfg)

        df = download_and_read_zip(url)  # 下載 ZIP，讀入 CSV
        df = normalize_columns(df, col)  # 統一欄位名稱

        df = df[df["flow"] == col["export_flag"]]
        df = df[df["country"].isin(rcep_sw_codes)]
        df["hs6"] = df["hs_code"].str[:6]
        df = df[df["hs6"].str[:2].isin(agr_chapters)]
        top_items = (df.groupby("hs6")["value_usd"].sum()
                       .nlargest(top_n).index.tolist())

        cache_db.set_taiwan_top10(year, top_items)
        top10_dict[str(year)] = top_items

    return top10_dict
```

**3. BACI 數據解析（Stage 2）— 三版本路由**

```python
# BACI 版本路由（HS 國際標準邊界，允許出現固定年份）
BACI_VERSION_ROUTER = {
    range(2010, 2012): "HS07",
    range(2012, 2017): "HS12",
    range(2017, 2025): "HS17",
}

RCEP_M49_SET = {v["m49"] for v in RCEP_COUNTRY_MAPPING.values()}
AGR_CHAPTERS = {f"{i:02d}" for i in range(1, 25)}

def get_baci_version(year: int) -> str:
    for yr_range, version in BACI_VERSION_ROUTER.items():
        if year in yr_range:
            return version
    raise ValueError(f"年份 {year} 超出支援範圍（2010–2024）")

def build_baci_path(year: int, version: str, cfg: dict) -> str:
    baci_dir  = cfg["baci"]["baci_dir"]
    pattern   = cfg["baci"]["filename_pattern"]
    filename  = pattern.format(version=version, year=year)
    return os.path.join(baci_dir, version.lower(), filename)

def load_and_filter_baci(year: int, top10_hs6: set, cfg: dict) -> pd.DataFrame:
    version  = get_baci_version(year)
    path     = build_baci_path(year, version, cfg)

    if not os.path.exists(path):
        raise FileNotFoundError(
            f"[Stage 2] 找不到 BACI {version} {year} 年檔案：\n{path}\n"
            f"請依 README 步驟 P3–P6 下載並解壓縮。"
        )

    df = pd.read_csv(path, dtype={"k": str})
    df = df[df["i"].isin(RCEP_M49_SET) & df["j"].isin(RCEP_M49_SET)]
    df = df[df["k"].str[:2].isin(AGR_CHAPTERS)]
    df = df[df["k"].isin(top10_hs6)]

    # 標準化欄位
    df = df.rename(columns={"t": "Year", "i": "Reporter_M49",
                             "j": "Partner_M49", "k": "HS6_Code_Original",
                             "v": "Value_USD_1000"})
    df["Value_USD"]       = df["Value_USD_1000"] * 1000
    df["baci_version"]    = version
    df["data_source"]     = "baci"
    df["data_provisional"]= (year >= 2023)
    return df

def run_stage2(start_year: int, end_year: int, top10_dict: dict, cfg: dict) -> pd.DataFrame:
    frames = []
    for year in range(start_year, end_year + 1):
        cached = cache_db.get_baci(year)
        if cached is not None:
            frames.append(cached)
            continue
        df = load_and_filter_baci(year, set(top10_dict[str(year)]), cfg)
        cache_db.set_baci(year, df)
        frames.append(df)
        log.info(f"[Stage 2] {year} 完成，{len(df)} 筆")
    return pd.concat(frames, ignore_index=True)
```

**4. HS Code 版本轉換（Stage 3）**

```python
HS_VERSION_MAP = {"HS07": "HS2007", "HS12": "HS2012", "HS17": "HS2017"}

def load_concordance(cfg: dict) -> dict:
    """載入版本對照表，結構：{source_version: {old_hs6: [new_hs6, ...]}}"""
    concordance = {}
    ref_dir = "data/reference"
    for version, source in [("HS2007", "HS2007_to_HS2017.xlsx"),
                             ("HS2012", "HS2012_to_HS2017.xlsx")]:
        path = os.path.join(ref_dir, source)
        if os.path.exists(path):
            df = pd.read_excel(path)
            concordance[version] = df.groupby("old")["new"].apply(list).to_dict()
    return concordance

def harmonize_to_hs2017(row: pd.Series, concordance: dict) -> list[dict]:
    version  = HS_VERSION_MAP.get(row["baci_version"], "HS2017")
    hs6_orig = row["HS6_Code_Original"]

    if version == "HS2017":
        return [{**row.to_dict(), "HS6_Code": hs6_orig,
                 "hs_converted": False, "hs_split": False, "hs_mapped": True,
                 "weight": 1.0}]

    mapping = concordance.get(version, {}).get(hs6_orig)
    if not mapping:
        return [{**row.to_dict(), "HS6_Code": hs6_orig,
                 "hs_converted": True, "hs_split": False, "hs_mapped": False,
                 "weight": 1.0}]

    n = len(mapping)
    result = []
    for new_code in mapping:
        r = row.to_dict()
        r.update({"HS6_Code": new_code, "hs_converted": True,
                  "hs_split": (n > 1), "hs_mapped": True,
                  "Value_USD": row["Value_USD"] / n,
                  "Value_USD_1000": row["Value_USD_1000"] / n,
                  "weight": 1.0 / n})
        result.append(r)
    return result
```

**5. 輸出規格**

```python
# 必須包含的欄位
REQUIRED_COLUMNS = [
    "Year", "HS6_Code", "HS6_Code_Original", "HS6_Description_EN", "HS6_Description_ZH",
    "HS_Chapter", "Reporter", "Reporter_ISO3", "Reporter_Group",
    "Partner", "Partner_ISO3",
    "Value_USD", "Value_USD_1000",
    "data_source", "baci_version", "data_provisional",
    "hs_converted", "hs_split", "hs_mapped",
    "data_quality", "Taiwan_Top10_Flag"
]

# 必須包含的工作表
REQUIRED_SHEETS = [
    "長表_完整數據",
    "Top10_HS6_清單",
    "台灣_RCEP出口明細",
    "RCEP內部_出口矩陣",
    "年度彙整_出口總額",
    "數據品質報告"
]
```

**6. Streamlit GUI 要求**

- 開啟時自動執行環境檢查，列出哪些 BACI 年份已就緒、哪些缺失
- 年份滑桿動態計算並顯示：需要哪些 BACI 版本、預估執行時間
- 斷點續傳：Stage 1 和 Stage 2 各自快取，中途關閉重啟後自動從上次位置繼續
- 執行中顯示逐年進度與即時日誌
- 完成後提供互動表格、趨勢圖、下載按鈕

**7. 錯誤處理要求**

- 找不到 BACI 檔案：拋出 `FileNotFoundError` 並告知具體要下載哪個版本+年份
- HTTP 下載失敗（台灣數據）：retry 3 次，指數退避，仍失敗則跳過該年並標記
- HS 對照表缺失：保留原碼，標記 `hs_mapped=False`，不中斷執行
- 任何非致命錯誤：寫入 SQLite error_log 表，繼續執行後續年份

**8. 執行環境**

- 作業系統：Windows 10/11 或 macOS 12+
- Python：3.10 以上
- 磁碟空間：至少 8GB（BACI 解壓縮後）

---

## 10. README 使用教學

---

# RCEP 農產品貿易分析系統 v3.0 — 使用說明

## 系統需求

- Python 3.10+（[下載](https://www.python.org/downloads/)）
- 穩定網路連線（BACI 下載用，程式執行時不需要）
- 至少 8GB 可用磁碟空間（BACI 年度 CSV 解壓縮後）
- **不需要任何付費帳號或 API Key**

## 安裝

```bash
git clone [repo_url]
cd rcep_agri_trade
pip install -r requirements.txt
```

## 首次使用：手動準備步驟（只需做一次）

### 步驟 P1（必做，5 分鐘）：確認台灣關務署欄位名稱

這是唯一一個需要你手動確認的技術細節，花 5 分鐘可以避免程式在 Stage 1 報錯。

1. 手動下載一個 2010 年的台灣關務署 CSV：
   `https://portal.sw.nat.gov.tw/PPL/OpenData/2010Y_ExportDetail.zip`
2. 解壓縮，用 Excel 打開 CSV
3. 確認第一行的欄位名稱
4. 對照 `config.yaml` 的 `column_mapping → "2010-2012"` 區塊，如有不符則修正

### 步驟 P2（5 分鐘）：CEPII 免費註冊

1. 前往 `http://www.cepii.fr/`
2. 點選右上角 Register（免費，不需信用卡）
3. 確認 email 後即可登入下載 BACI

### 步驟 P3–P5（60–120 分鐘，可背景執行）：下載 BACI

前往 `http://www.cepii.fr/CEPII/en/bdd_modele/bdd_modele_item.asp?id=37`

**版本 HS07**（選 202601）→ 下載 2010、2011 年（共 2 個 zip）
**版本 HS12**（選 202601）→ 下載 2012、2013、2014、2015、2016 年（共 5 個 zip）
**版本 HS17**（選 202601）→ 下載 2017、2018、2019、2020、2021、2022、2023、2024 年（共 8 個 zip）

> 若只分析部分年份，只需下載對應年份的 zip，不需全部下載。

### 步驟 P6（15 分鐘）：解壓縮，放入對應資料夾

```
data/raw/baci/hs07/  ← 放 HS07 的 CSV
data/raw/baci/hs12/  ← 放 HS12 的 CSV
data/raw/baci/hs17/  ← 放 HS17 的 CSV
```

> 解壓縮後每個 CSV 約 300–400MB，15 個 CSV 共約 5–7GB。

### 步驟 P7（5 分鐘）：下載 HS 對照表

1. 前往 `https://unstats.un.org/unsd/trade/classifications/correspondence-tables.asp`
2. 下載：**HS 2007 to HS 2017 Conversion** 和 **HS 2012 to HS 2017 Conversion**
3. 放入 `data/reference/` 資料夾

## 啟動程式

```bash
streamlit run app.py
```

瀏覽器自動開啟，系統會先執行環境檢查，確認所有 BACI 檔案就緒後才允許開始分析。

## 操作說明

1. **設定年份**：拖拉左側的年份滑桿選擇分析範圍（預設 2010–2024）
2. **檢查環境**：頁面上方顯示每個年份的 BACI 檔案狀態，若有紅色❌代表該年份 zip 尚未放入
3. **設定 Top N**：預設前 10 大品項，可調整為 5–20
4. **開始執行**：點選「▶ 開始執行」，約 1–1.5 小時完成（程式執行期間電腦不需要連網）
5. **下載報表**：完成後點選「📥 下載 Excel」

## 時間估計

| 分析範圍 | BACI 手動下載 | 程式執行 | 合計 |
|---------|------------|---------|------|
| 2017–2024（8年）| 1 個版本，約 30 分鐘 | 約 40 分鐘 | **~1.5 小時** |
| 2012–2024（13年）| 2 個版本，約 60 分鐘 | 約 55 分鐘 | **~2 小時** |
| 2010–2024（15年）| 3 個版本，約 90 分鐘 | 約 70 分鐘 | **~2.5 小時** |

## 常見問題

**Q：程式啟動後顯示某年份 BACI 檔案缺失，怎麼辦？**
A：回到 CEPII 網站補下載該年份的 zip，解壓縮後放入對應版本的子資料夾（hs07/hs12/hs17），重新點「▶ 開始執行」，程式會從缺失的地方繼續。

**Q：BACI 版本號不是 202601，而是 202501 或其他版本，怎麼辦？**
A：修改 `config.yaml` 中 `baci → filename_pattern` 的版本號部分，例如把 `V202601` 改成 `V202501`，即可正常讀取。

**Q：某些國家（汶萊/寮國/緬甸）的數據很少或全部是空白，正常嗎？**
A：正常。這三個小國在 BACI 本身的數據就不完整。報表中已自動標記 `data_quality='sparse'`，建議在商業報告中附注說明。

**Q：2023–2024 年的數據標記了「provisional（初步值）」，意思是什麼？**
A：CEPII 說明 BACI 最新一年的數據在未來版本可能被修正（通常修正幅度約 1–5%）。標記讓你知道這兩年數據可能不是最終值，未來可重新下載 BACI 新版本更新。

**Q：HS Code 在不同年份為什麼不一樣？**
A：HS 分類每 5–6 年更新一次，同一商品在 2012 年和 2017 年可能有不同的 6 碼。程式統一轉換至 HS2017 基準，原始代碼保留在 `HS6_Code_Original` 欄位供核對。

---

## 11. 已知風險與備用方案矩陣

| 風險 | 發生機率 | 影響 | 備用方案 |
|------|---------|------|---------|
| data.gov.tw URL 格式變更 | 中 | Stage 1 無法下載台灣數據 | 改手動下載 ZIP；或改用 BOFT 年度 Excel（精度略低）|
| 台灣 2010–2012 欄位名稱推估錯誤 | 中 | Stage 1 舊年份解析失敗 | 執行 README P1 步驟（5分鐘）手動確認，然後修正 config.yaml |
| CEPII 更新版本號（V202601→V202701）| 高（每年）| 程式找不到 BACI 檔案 | 修改 config.yaml 的 `filename_pattern` 即可 |
| BACI 2023–2024 初步值被修正 | 中 | 近兩年數據需重新下載 | 下載新版 BACI，覆蓋舊 CSV，重新執行（快取會自動更新）|
| HS 對照表找不到（P7 步驟未做）| 低 | HS07/HS12 數據代碼未轉換 | 保留原碼，標記 hs_mapped=False；對 2017–2024 分析無影響 |
| 小國數據缺失（BN/LA/MM）| 高 | 矩陣有 NULL | 標記 NULL，提供「ASEAN7」備用分組（自動排除三小國）|
| BACI 解壓縮後磁碟空間不足 | 低 | 部分年份無法讀入 | 只下載需要的年份；或分批分析（先 2010–2016，再 2017–2024）|
| Excel 單一工作表超過 100 萬行 | 低 | Excel 無法開啟長表 | 程式自動偵測，超過限制時改輸出 CSV + Parquet 雙格式 |

---

*計畫版本：v3.0 | 最後修訂：2026 年 3 月 | 適用平台：Windows / macOS / Linux*
*數據來源：財政部關務署（台灣）、CEPII BACI（RCEP 內部）*
*API 請求次數：0*
