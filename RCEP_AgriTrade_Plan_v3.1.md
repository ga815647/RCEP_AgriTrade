# RCEP 農產品貿易動態數據分析計畫 v3.1
## 商業分析版 · 單一來源 BACI · 零 API 請求 · Streamlit GUI

> **版本變更記錄**
> - v1 → v2：修正台灣數據來源、WITS 請求量、HS 版本等 4 個致命錯誤
> - v2 → v3：BACI 改三版本路由（HS07/HS12/HS17）；移除 WITS；API 請求降為 0
> - v3 → v3.1：確認 portal.sw.nat.gov.tw 開放資料 URL 不存在，台灣數據改從 BACI（M49=490）取用
> - v3.1 修正：**確認 CEPII 下載不需要註冊帳號**；補充 HS22 不需下載的原因說明；更正下載網址為 https
>
> ⚠️ **v3.1 核心取捨**：台灣數據來自 BACI（M49=490，Chinese Taipei），BACI 已對
> 台灣申報數據做跨國調和，品質尚可，但部分年份可能有缺漏，輸出中會標記。
> 若商業報告需要官方原始數據，須另行手動下載財政部關務署統計年刊 Excel 補充。

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

### 完整問題修正記錄

| 問題 | 版本 | 原始錯誤假設 | 實際情況 | 最終修正 |
|------|------|------------|---------|---------|
| A | v1 | portal.sw.nat.gov.tw 有開放 API | 純 JavaScript 表單，無法程式存取 | 改用 BACI（見下）|
| B | v1 | WITS 可承受 33,750 次請求 | 需 67 天，不可行 | 改用 BACI 本地檔案 |
| C | v1 | 台灣在 Comtrade/WITS 數據完整 | 2020+ 數據缺口明顯 | 改用 BACI（含台灣）|
| D | v1 | HS Code 版本無需處理 | 2010–2024 跨三個版本 | 三版本路由 + HS2017 統一轉換 |
| E | v2 | BACI HS17 從 2010 開始 | HS17 只從 2017 開始 | HS07（2010–11）+ HS12（2012–16）+ HS17（2017–24）|
| F | v2 | BACI 最新到 2021 | BACI 202601 已有 2024 年 | 移除 WITS，純 BACI |
| **G** | **v3** | **portal.sw.nat.gov.tw/PPL/OpenData/ 存在** | **此 URL 根本不存在** | **台灣數據改從 BACI M49=490 取用** |

### 已知限制（v3.1 接受的取捨）

| 限制 | 說明 | 在輸出中的處理 |
|------|------|--------------|
| 台灣 BACI 數據品質 | BACI 的台灣（M49=490）數據源自 Comtrade，部分年份申報可能不完整 | 標記 `reporter_group='Taiwan'`，報表加附注 |
| 2023–2024 初步值 | BACI 最新兩年為初版，可能在未來版本修正 | 標記 `data_provisional=True` |
| 小國數據稀疏 | BN/LA/MM 在 BACI 中本身就有缺漏 | 標記 `data_quality='sparse'` |

---

## 2. 核心架構

```
┌─────────────────────────────────────────────────────────────────┐
│                      Streamlit GUI 前端                           │
│  [年份滑桿] [Top N] [RCEP 國家選擇] [▶執行] [⏸暫停] [🔄繼續]    │
└───────────────────────────┬─────────────────────────────────────┘
                            │  start_year, end_year, top_n
┌───────────────────────────▼─────────────────────────────────────┐
│                      主控 Pipeline（單一來源：BACI）               │
│                                                                   │
│  Stage 1                 Stage 2             Stage 3   Stage 4   │
│  台灣 Top10 計算  →    RCEP 內部矩陣  →   整合清理 → 輸出報表   │
│  (BACI TWN rows)         (BACI 三版本)       HS 統一    Excel    │
│                          路由過濾             轉換      多工作表  │
└──────────────────────────────┬──────────────────────────────────┘
                               │
          ┌────────────────────▼────────────────────────────────┐
          │             BACI 本地 CSV（手動下載）                 │
          │  HS07 版本：2010–2011  (M49=490 = 台灣也在其中)      │
          │  HS12 版本：2012–2016                                │
          │  HS17 版本：2017–2024（含 2024 初步值）               │
          └─────────────────────────────────────────────────────┘
                               │
          ┌────────────────────▼────────────────────────────────┐
          │              本地快取層 (SQLite)                      │
          │         進度記錄、斷點續傳、溯源日誌                   │
          └─────────────────────────────────────────────────────┘
```

**關鍵設計原則（v3.1）**：
- **單一數據來源**：所有數據（含台灣）均來自 BACI，不需要任何外部 API 或額外下載
- Stage 1 從 BACI 過濾出 `Reporter=TWN（490）`、`Partner∈RCEP_15` 的行，計算台灣 Top10
- Stage 2 從 BACI 過濾出 `Reporter∈RCEP_15`、`Partner∈RCEP_15` 的行，建立 RCEP 內部矩陣
- 兩個階段讀同一批 BACI 檔案，可合併為一次讀檔，避免重複 I/O

---

## 3. 數據來源策略

### 策略總覽

| 數據需求 | 來源 | 取得方式 | API 請求 |
|---------|------|---------|---------|
| 台灣 → RCEP 出口（目標 A，Top10 計算）| BACI（Reporter=TWN/490）| 手動下載，本地過濾 | **0** |
| RCEP 內部貿易 2010–2011（目標 B）| BACI HS07 | 手動下載 2 個 CSV | **0** |
| RCEP 內部貿易 2012–2016（目標 B）| BACI HS12 | 手動下載 5 個 CSV | **0** |
| RCEP 內部貿易 2017–2024（目標 B）| BACI HS17 | 手動下載 8 個 CSV | **0** |
| HS 說明文字 | BACI 附帶 nomenclature CSV | 隨 BACI 一起下載 | **0** |
| HS 版本對照表 | UN Stats 對照 Excel | 手動下載（2 個檔案）| **0** |

**總 API 請求次數：0 · 總外部下載：15 個 BACI CSV + 2 個對照表 Excel**

---

### BACI 三版本說明

**下載網址**：`https://www.cepii.fr/CEPII/en/bdd_modele/bdd_modele_item.asp?id=37`
**最新版本**：202601（2026 年 1 月，涵蓋至 2024 年）
**不需要註冊帳號**：直接進入頁面即可選版本下載

| BACI 版本 | 本計畫使用年份 | 台灣（M49=490）包含？| 檔案數 |
|-----------|------------|---------------------|-------|
| **HS07** | 2010–2011 | ✅ 含台灣 | 2 個 |
| **HS12** | 2012–2016 | ✅ 含台灣 | 5 個 |
| **HS17** | 2017–2024 | ✅ 含台灣 | 8 個 |

**BACI CSV 欄位**（三個版本格式相同）：

| 欄位 | 說明 | 備注 |
|------|------|------|
| `t` | 年份 | |
| `i` | 出口國 UN M49 | 台灣 = 490 |
| `j` | 進口國 UN M49 | |
| `k` | HS6 商品代碼 | **字串型別，保留前導零** |
| `v` | 貿易額（千美元）| 輸出時 × 1000 轉為美元 |
| `q` | 數量（噸）| 可選欄位 |

**RCEP + 台灣 M49 對照表**：

| ISO2 | ISO3 | M49 | 中文名 | 群組 |
|------|------|-----|-------|------|
| TW | TWN | **490** | 台灣 | Taiwan |
| BN | BRN | 96 | 汶萊 | ASEAN10 |
| KH | KHM | 116 | 柬埔寨 | ASEAN10 |
| ID | IDN | 360 | 印尼 | ASEAN10 |
| LA | LAO | 418 | 寮國 | ASEAN10 |
| MY | MYS | 458 | 馬來西亞 | ASEAN10 |
| MM | MMR | 104 | 緬甸 | ASEAN10 |
| PH | PHL | 608 | 菲律賓 | ASEAN10 |
| SG | SGP | 702 | 新加坡 | ASEAN10 |
| TH | THA | 764 | 泰國 | ASEAN10 |
| VN | VNM | 704 | 越南 | ASEAN10 |
| CN | CHN | 156 | 中國 | RCEP5 |
| JP | JPN | 392 | 日本 | RCEP5 |
| KR | KOR | 410 | 韓國 | RCEP5 |
| AU | AUS | 36 | 澳洲 | RCEP5 |
| NZ | NZL | 554 | 紐西蘭 | RCEP5 |

---

### HS Code 版本對照表

**下載網址**：`https://unstats.un.org/unsd/trade/classifications/correspondence-tables.asp`
- 下載：**HS 2007 to HS 2017 Conversion**（給 HS07 版數據用）
- 下載：**HS 2012 to HS 2017 Conversion**（給 HS12 版數據用）
- **HS17 版數據不需要轉換**（已是基準版本）

---

## 4. 執行階段詳細說明

### 階段 0：環境準備（一次性）

#### 套件安裝
```bash
pip install streamlit pandas openpyxl requests tqdm loguru pyyaml
# sqlite3 為 Python 內建，無需安裝
```

#### ✋ 手動操作清單

| 步驟 | 動作 | 預估時間 |
|------|------|---------|
| **M1** | 下載 BACI HS07（版本 202601，取 2010、2011 年，共 2 個 zip）| 15 分鐘 |
| **M2** | 下載 BACI HS12（版本 202601，取 2012–2016 年，共 5 個 zip）| 30 分鐘 |
| **M3** | 下載 BACI HS17（版本 202601，取 2017–2024 年，共 8 個 zip）| 60 分鐘 |
| **M4** | 解壓縮所有 zip，CSV 放入對應子資料夾（見第 7 節）| 15 分鐘 |
| **M5** | 下載 HS2007→HS2017、HS2012→HS2017 對照表，放入 `data/reference/` | 5 分鐘 |

**總手動時間：約 2 小時（主要是下載等待，可以同時做其他事）**
**不需要任何帳號或 API Key**

---

### 階段一：計算台灣 Top10 基準清單

**目的**：從 BACI 中取出台灣（M49=490）對 RCEP 的農產品出口，計算每年前 N 大 HS6 品項

**輸入**：`start_year`、`end_year`、`top_n`（全部來自 GUI session_state）
**輸出**：`top10_dict` = `{"2010": ["030389", "100190", ...], "2011": [...], ...}`

**執行邏輯**：
```
對每個年份 y in range(start_year, end_year + 1)：

  1. 查 SQLite 快取，若命中則跳過
  2. 若無快取：
     a. 判斷 BACI 版本（HS07/HS12/HS17）
     b. 讀入對應年份的 BACI CSV
     c. 過濾：i == 490（台灣出口）
     d. 過濾：j ∈ RCEP_15_M49_SET（對 RCEP 15 國）
     e. 過濾：k[:2] ∈ {'01','02',...,'24'}（農產品）
     f. 以 k（HS6）groupby 加總 v（千美元）
     g. 排序，取前 top_n 名
     h. 寫入 SQLite 快取
  3. 累積至 top10_dict
```

> **注意**：Stage 1 和 Stage 2 讀同一個 BACI 年份檔案。為避免重複 I/O，
> 程式應在讀入每個年份後，**一次同時**完成 Stage 1 過濾（TWN→RCEP）
> 和 Stage 2 過濾（RCEP→RCEP），再釋放記憶體。

---

### 階段二：建立 RCEP 內部貿易矩陣

**目的**：取得 RCEP 15 國之間在 Top10 品項上的完整方向性出口矩陣（如日→韓、泰→日）

**輸入**：`top10_dict`、`start_year`、`end_year`
**輸出**：`rcep_df`，長表格式

**BACI 版本路由**（HS 國際標準邊界，允許在程式中出現）：
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

  1. 查 SQLite 快取，若命中則跳過
  2. 若無快取（通常與 Stage 1 合併一次讀檔）：
     a. 讀入 BACI CSV（若 Stage 1 已讀，直接使用同一 DataFrame）
     b. 過濾：i ∈ RCEP_15_M49_SET AND j ∈ RCEP_15_M49_SET
     c. 過濾：k[:2] ∈ {'01','02',...,'24'}
     d. 過濾：k ∈ set(top10_dict[str(y)])（只保留當年 Top10）
     e. 標記 baci_version、data_provisional（y >= 2023）
     f. 寫入 SQLite 快取
  3. 累積至 rcep_df
```

---

### 階段三：數據清理與整合

#### 3.1 合併台灣出口與 RCEP 矩陣

```python
# Stage 1 產出的台灣出口 DataFrame（Reporter=Taiwan）
taiwan_df["Reporter"]       = "Taiwan"
taiwan_df["Reporter_ISO3"]  = "TWN"
taiwan_df["Reporter_M49"]   = 490
taiwan_df["Reporter_Group"] = "Taiwan"

# Stage 2 產出的 RCEP 矩陣 DataFrame
# Reporter_Group 依 M49 自動分配為 'ASEAN10' 或 'RCEP5'

final_df = pd.concat([taiwan_df, rcep_df], ignore_index=True)
```

#### 3.2 HS Code 版本統一（轉換至 HS2017 基準）

```python
# HS17 版資料（2017–2024）：無需轉換
# HS07 版資料（2010–2011）：從 HS2007 轉換至 HS2017
# HS12 版資料（2012–2016）：從 HS2012 轉換至 HS2017

def harmonize_to_hs2017(hs6: str, baci_version: str, concordance: dict) -> list[tuple]:
    """
    回傳 [(hs2017_code, weight), ...]
    一對一：[(code, 1.0)]
    一對多（拆分）：[(code1, 0.5), (code2, 0.5)]  金額等比分配
    """
    version_map = {"HS07": "HS2007", "HS12": "HS2012", "HS17": "HS2017"}
    source_ver  = version_map[baci_version]

    if source_ver == "HS2017":
        return [(hs6, 1.0)]

    mapping = concordance.get(source_ver, {}).get(hs6)
    if not mapping:
        return [(hs6, 1.0)]   # 無對照，保留原碼，hs_mapped=False

    n = len(mapping)
    return [(code, 1.0 / n) for code in mapping]
```

#### 3.3 遺失值處理策略

| 情況 | 處理方式 |
|------|---------|
| BACI 中該流向本年無數據 | 保留 `NULL`（不填 0） |
| 台灣 BACI 數據缺漏年份 | 標記 `data_quality='taiwan_baci_gap'` |
| 2023–2024 初步值 | 標記 `data_provisional=True` |
| HS 代碼無對照表 | 保留原碼，`hs_mapped=False` |
| 小國（BN/LA/MM）數據稀疏 | 標記 `data_quality='sparse'` |

---

### 階段四：輸出報表

**檔名**：`output/RCEP_AgriTrade_{start_year}_{end_year}_{timestamp}.xlsx`

**工作表清單**：

| 工作表 | 內容 | 對應目標 |
|--------|------|---------|
| `長表_完整數據` | 所有記錄、所有欄位，長格式 | 主表，可匯入任何分析工具 |
| `Top10_HS6_清單` | 每年台灣 Top10 品項（代碼+說明+金額）| 目標 A 快速查閱 |
| `台灣_RCEP出口明細` | 台灣 → 各 RCEP 國，逐年逐品項 | 目標 A 核心報表 |
| `RCEP內部_出口矩陣` | Reporter × Partner × 年份樞紐，Top10 加總 | 目標 B 核心報表 |
| `年度彙整_出口總額` | 各國各年度農產品出口至 RCEP 合計 | 趨勢分析 |
| `數據品質報告` | 每筆記錄的 BACI 版本、轉換旗標、可信度 | 商業報告引用聲明 |

**完整欄位定義**：

| 欄位 | 型態 | 說明 |
|------|------|------|
| `Year` | INT | 年份 |
| `HS6_Code` | STR(6) | HS6 代碼（統一為 HS2017）|
| `HS6_Code_Original` | STR(6) | 原始年份版本的 HS6 代碼 |
| `HS6_Description_EN` | STR | 英文說明 |
| `HS6_Description_ZH` | STR | 中文說明（對照表補入）|
| `HS_Chapter` | STR(2) | HS 前兩碼（01–24）|
| `Reporter` | STR | 出口國名稱 |
| `Reporter_ISO3` | STR(3) | 出口國 ISO3 |
| `Reporter_M49` | INT | 出口國 M49 代碼 |
| `Reporter_Group` | STR | `Taiwan` / `ASEAN10` / `RCEP5` |
| `Partner` | STR | 進口國名稱 |
| `Partner_ISO3` | STR(3) | 進口國 ISO3 |
| `Partner_M49` | INT | 進口國 M49 代碼 |
| `Value_USD` | FLOAT | 貿易額（美元）|
| `Value_USD_1000` | FLOAT | 貿易額（千美元，BACI 原始單位）|
| `data_source` | STR | 固定為 `baci` |
| `baci_version` | STR | `HS07` / `HS12` / `HS17` |
| `data_provisional` | BOOL | True = 2023–2024 初步值 |
| `hs_converted` | BOOL | True = 已做 HS 版本轉換 |
| `hs_split` | BOOL | True = 一對多轉換，金額等比分配 |
| `hs_mapped` | BOOL | False = 找不到對照表 |
| `data_quality` | STR | `ok` / `sparse` / `taiwan_baci_gap` / `provisional` |
| `Taiwan_Top10_Flag` | BOOL | True = 此品項為當年台灣 Top10 |

---

## 5. 請求量與時間估計

### 請求量

**API 請求次數：0**（全部為本地 BACI 解析，無任何網路 API 呼叫）

### 時間估計（預設 2010–2024）

```
T+0:00   ✋ M1–M3：直接前往 CEPII 下載 BACI 三版本，共 15 個 zip（60–120 分鐘，可背景執行）
T+2:00   ✋ M4：解壓縮，放入對應資料夾（15 分鐘）
T+2:15   ✋ M5：下載 HS 對照表（5 分鐘）

T+2:20   ▶ 啟動程式（streamlit run app.py）
T+2:25   環境檢查：偵測所有 BACI 年份檔案是否就緒
T+3:10   Stage 1+2 完成：BACI 解析（三版本，合併讀檔，約 45 分鐘）
T+3:25   Stage 3 完成：HS 轉換、整合（15 分鐘）
T+3:30   Stage 4 完成：Excel 報表生成 ✅

總計：約 3.5 小時（含手動等待），程式執行約 70 分鐘
程式執行期間：不需要網路連線
```

**部分年份估計**：

| 分析範圍 | 需下載 BACI | 手動下載 | 程式執行 | 合計 |
|---------|-----------|---------|---------|------|
| 2017–2024（8年）| HS17 × 8 | ~30 分鐘 | ~35 分鐘 | **~1 小時** |
| 2012–2024（13年）| HS12 × 5 + HS17 × 8 | ~70 分鐘 | ~55 分鐘 | **~2 小時** |
| 2010–2024（15年）| HS07 × 2 + HS12 × 5 + HS17 × 8 | ~120 分鐘 | ~70 分鐘 | **~3.5 小時** |

---

## 6. HS Code 版本處理邏輯

### 版本對應（HS 國際標準定義，固定值）

| 年份 | BACI 版本 | HS 分類 | 需要轉換？ |
|------|----------|---------|---------|
| 2010–2011 | HS07 | HS2007 | ✅ 需要（→ HS2017）|
| 2012–2016 | HS12 | HS2012 | ✅ 需要（→ HS2017）|
| 2017–2024 | HS17 | HS2017 | 不需要（已是基準）|

### 為何不下載 BACI HS22？

「BACI 版本」和「現實世界申報用的 HS 版本」是兩件不同的事，容易混淆：

```
現實申報：
  2022–2024 年各國海關 → 用 HS2022 代碼向 Comtrade 申報

CEPII 的處理（BACI 發布時已做轉換）：
  BACI HS17 → 將 2017–2024 所有年份統一轉換為 HS2017 代碼後發布
              2022–2024 的數據已包含在內，代碼已是 HS2017 ✅
  BACI HS22 → 將 2022–2024 保留為 HS2022 代碼後發布
              只有 3 年，且若使用還需額外一道 HS2022→HS2017 轉換 ❌
```

**結論**：BACI HS17 已包含 2022–2024 且代碼即為本計畫基準版本（HS2017），下載 HS22 反而多一道工序，沒有必要。

### 農產品版本變動重要章節

| HS 章 | 主要變動 | 轉換必要性 |
|-------|---------|---------|
| 03（魚類）| HS2012→HS2017 大幅調整 | 高 |
| 02（肉類）| 部分重新分類 | 中 |
| 08（水果）| 新增數個 6 碼 | 低 |

---

## 7. 專案目錄結構

```
rcep_agri_trade/
│
├── app.py                          # Streamlit GUI 主程式
├── config.yaml                     # 設定檔
├── requirements.txt
├── README.md
│
├── pipeline/
│   ├── __init__.py
│   ├── stage1_top10.py             # 從 BACI 計算台灣 Top10（TWN→RCEP）
│   ├── stage2_rcep.py              # 從 BACI 建立 RCEP 內部貿易矩陣
│   ├── stage3_clean.py             # 整合、HS 版本轉換、品質標記
│   └── stage4_export.py            # Excel 多工作表輸出
│
├── utils/
│   ├── cache.py                    # SQLite 快取（斷點續傳）
│   ├── baci_loader.py              # BACI 版本路由、讀檔、過濾（Stage 1+2 共用）
│   ├── hs_harmonizer.py            # HS Code 版本轉換
│   └── country_codes.py            # M49 ↔ ISO3 ↔ 中文名對照（含台灣 490）
│
├── data/
│   ├── reference/
│   │   ├── HS2007_to_HS2017.xlsx
│   │   ├── HS2012_to_HS2017.xlsx
│   │   └── hs6_descriptions_zh.csv （可選，HS6 中文說明）
│   ├── raw/
│   │   └── baci/
│   │       ├── hs07/
│   │       │   ├── BACI_HS07_Y2010_V202601.csv
│   │       │   └── BACI_HS07_Y2011_V202601.csv
│   │       ├── hs12/
│   │       │   ├── BACI_HS12_Y2012_V202601.csv
│   │       │   ├── ...
│   │       │   └── BACI_HS12_Y2016_V202601.csv
│   │       └── hs17/
│   │           ├── BACI_HS17_Y2017_V202601.csv
│   │           ├── ...
│   │           └── BACI_HS17_Y2024_V202601.csv
│   └── cache/
│       └── trade_cache.db          # SQLite 快取（自動建立）
│
└── output/
    └── RCEP_AgriTrade_{start}_{end}_{ts}.xlsx
```

### config.yaml

```yaml
# ===== 預設值（GUI 啟動時載入，操作後以 session_state 為準）=====

time_range:
  start: 2010
  end: 2024

top_n: 10   # GUI 可調整 5–20

rcep_countries:
  asean10: [BN, KH, ID, LA, MY, MM, PH, SG, TH, VN]
  others:  [CN, JP, KR, AU, NZ]

taiwan_m49: 490   # Chinese Taipei 在 BACI 中的 M49 代碼

agriculture_hs_chapters: [1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24]

hs_base_version: "HS2017"

baci:
  baci_dir: "data/raw/baci"
  filename_pattern: "BACI_{version}_Y{year}_V202601.csv"
  # ↑ CEPII 更新版本號時（V202601 → V202701），只需修改此處
  version_router:
    "2010-2011": "HS07"
    "2012-2016": "HS12"
    "2017-2024": "HS17"

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
│  🌾 RCEP 農產品貿易分析系統  v3.1                              │
├──────────────────┬────────────────────────────────────────────┤
│  ⚙️ 側邊欄        │  主要內容區                                │
│                  │                                            │
│ 📅 時間範圍      │  ① 環境檢查（啟動時自動掃描）               │
│ ◀2010━━━━2024▶  │  ✅ HS07: 2010, 2011                       │
│                  │  ✅ HS12: 2012, 2013, 2014, 2015, 2016    │
│ 即時提示：        │  ✅ HS17: 2017 ~ 2024                     │
│ HS07×2+HS17×8   │  ✅ HS 對照表                              │
│ 程式約 70 分鐘   │  ─────────────────────────────────         │
│                  │  ② 執行進度                               │
│ 🔢 Top N         │  Stage 1 台灣Top10  ████████████ 100% ✅  │
│ [10  ▲▼]        │  Stage 2 RCEP矩陣   ████████░░░░  67% 🔄  │
│                  │  Stage 3 整合清理   ░░░░░░░░░░░░   0% ⏳  │
│ 🗺️ RCEP 國家     │  Stage 4 輸出報表   ░░░░░░░░░░░░   0% ⏳  │
│ ☑ 全選           │  ─────────────────────────────────         │
│ ☑ ASEAN10       │  ③ 即時日誌                               │
│ ☑ CN JP KR AU NZ│  [OK]  HS12 2015 讀入，過濾後 3,421 筆    │
│                  │  [OK]  TWN→RCEP Top10 2015 計算完成       │
│ [▶ 開始執行]     │  [WARN] BN 2015 數據稀疏（僅 2 筆）       │
│ [⏸ 暫停]        │  ─────────────────────────────────         │
│ [🔄 繼續]       │  ④ 完成後顯示                              │
│                  │  [互動表格] [趨勢圖] [熱力圖]              │
│ ─────────────── │  [📥 下載 Excel]  [📥 下載 CSV]           │
└──────────────────┴────────────────────────────────────────────┘
```

### 年份滑桿（核心控制項）

```python
start_year, end_year = st.slider(
    "📅 時間範圍",
    min_value=2010,
    max_value=2024,
    value=(2010, 2024),
    step=1
)
st.session_state["start_year"] = start_year
st.session_state["end_year"]   = end_year

# 滑桿下方即時提示（不依賴網路，純本地計算）
versions = get_required_baci_versions(start_year, end_year)  # 計算需要哪些版本
est_min  = estimate_runtime_minutes(start_year, end_year)
st.caption(f"需要：{versions} | 程式預估執行時間：約 {est_min} 分鐘")
```

### 🚫 程式碼硬編碼禁止規則

- 業務邏輯中**不得出現任何年份數字**
- 所有迴圈使用 `st.session_state["start_year"]` / `["end_year"]`
- **允許例外**：`config.yaml` 預設值、BACI 版本路由邊界

---

## 9. 給 AI Agent 的最終指令（可直接複製）

---

> **請根據以下規格，使用 Python 3.10+ 編寫完整的自動化腳本與 Streamlit GUI。**

### 🚫 絕對禁止事項（最高優先級）

> 業務邏輯的 Python 程式碼中，**嚴禁將分析年份寫死**。
> 禁止寫法：`range(2010, 2025)`、`year == 2024`、`for y in [2010,2011,...]` 等。
> 所有年份迴圈必須使用 `st.session_state["start_year"]` 和 `st.session_state["end_year"]`。
>
> **允許出現固定年份的情況（僅此兩種）**：
> 1. `config.yaml` 中的預設值
> 2. BACI 版本路由表中的邊界（屬於 HS 國際標準，非業務邏輯）

---

### 任務目標

建立可執行的 Python 應用程式，從 BACI 本地 CSV 檔案解析：
1. **目標 A**：台灣（M49=490）對 RCEP 15 國出口的農產品每年前 N 大 HS6 品項
2. **目標 B**：上述品項中，RCEP 15 國之間任意方向的出口數據（完整 15×15 矩陣）

輸出為標準化 Excel 報表，供商業分析使用。
**單一數據來源：BACI。不需要任何外部 API 請求。**

---

### 技術規格

**1. 套件需求**
```
Python 3.10+
streamlit >= 1.32
pandas >= 2.0
openpyxl >= 3.1
tqdm >= 4.66
loguru >= 0.7
pyyaml >= 6.0
sqlite3（內建）
```

**2. 國家代碼定義（完整，含台灣）**

```python
# 所有 RCEP 成員 + 台灣，M49 代碼為 BACI 使用的主鍵
ALL_COUNTRIES = {
    "TWN": {"m49": 490, "iso2": "TW", "name_zh": "台灣",   "group": "Taiwan"},
    "BRN": {"m49":  96, "iso2": "BN", "name_zh": "汶萊",   "group": "ASEAN10"},
    "KHM": {"m49": 116, "iso2": "KH", "name_zh": "柬埔寨", "group": "ASEAN10"},
    "IDN": {"m49": 360, "iso2": "ID", "name_zh": "印尼",   "group": "ASEAN10"},
    "LAO": {"m49": 418, "iso2": "LA", "name_zh": "寮國",   "group": "ASEAN10"},
    "MYS": {"m49": 458, "iso2": "MY", "name_zh": "馬來西亞","group": "ASEAN10"},
    "MMR": {"m49": 104, "iso2": "MM", "name_zh": "緬甸",   "group": "ASEAN10"},
    "PHL": {"m49": 608, "iso2": "PH", "name_zh": "菲律賓", "group": "ASEAN10"},
    "SGP": {"m49": 702, "iso2": "SG", "name_zh": "新加坡", "group": "ASEAN10"},
    "THA": {"m49": 764, "iso2": "TH", "name_zh": "泰國",   "group": "ASEAN10"},
    "VNM": {"m49": 704, "iso2": "VN", "name_zh": "越南",   "group": "ASEAN10"},
    "CHN": {"m49": 156, "iso2": "CN", "name_zh": "中國",   "group": "RCEP5"},
    "JPN": {"m49": 392, "iso2": "JP", "name_zh": "日本",   "group": "RCEP5"},
    "KOR": {"m49": 410, "iso2": "KR", "name_zh": "韓國",   "group": "RCEP5"},
    "AUS": {"m49":  36, "iso2": "AU", "name_zh": "澳洲",   "group": "RCEP5"},
    "NZL": {"m49": 554, "iso2": "NZ", "name_zh": "紐西蘭", "group": "RCEP5"},
}

TAIWAN_M49   = 490
RCEP_15_M49  = {v["m49"] for iso3, v in ALL_COUNTRIES.items() if v["group"] != "Taiwan"}
ALL_M49      = {v["m49"] for v in ALL_COUNTRIES.values()}   # 含台灣，共 16 個
AGR_CHAPTERS = {f"{i:02d}" for i in range(1, 25)}           # '01'~'24'
```

**3. BACI 版本路由與讀檔（核心模組：utils/baci_loader.py）**

```python
import os, pandas as pd
from loguru import logger

BACI_VERSION_ROUTER = {
    range(2010, 2012): "HS07",
    range(2012, 2017): "HS12",
    range(2017, 2025): "HS17",
}

def get_baci_version(year: int) -> str:
    for yr_range, ver in BACI_VERSION_ROUTER.items():
        if year in yr_range:
            return ver
    raise ValueError(f"年份 {year} 超出 BACI 支援範圍（2010–2024）")

def build_baci_path(year: int, cfg: dict) -> str:
    ver      = get_baci_version(year)
    pattern  = cfg["baci"]["filename_pattern"]
    filename = pattern.format(version=ver, year=year)
    return os.path.join(cfg["baci"]["baci_dir"], ver.lower(), filename)

def load_baci_year(year: int, cfg: dict) -> pd.DataFrame:
    """讀入單一年份 BACI CSV，保留 RCEP+台灣 相關行，農產品（HS01-24）"""
    path = build_baci_path(year, cfg)
    if not os.path.exists(path):
        ver = get_baci_version(year)
        raise FileNotFoundError(
            f"找不到 BACI {ver} {year} 年檔案：\n{path}\n"
            f"請依 README 步驟 M2–M5 下載並解壓縮 BACI {ver} 版的 {year} 年 zip。"
        )
    df = pd.read_csv(path, dtype={"k": str})
    df = df[df["i"].isin(ALL_M49) | df["j"].isin(ALL_M49)]   # 初步過濾，含台灣
    df = df[df["k"].str[:2].isin(AGR_CHAPTERS)]               # 農產品
    df["baci_version"] = get_baci_version(year)
    logger.info(f"[BACI] {year} 讀入，農產品相關行：{len(df):,}")
    return df
```

**4. Stage 1：台灣 Top10 計算**

```python
def run_stage1(start_year: int, end_year: int, top_n: int, cfg: dict,
               cache_db, baci_cache: dict) -> dict:
    """
    從 BACI 計算台灣（M49=490）對 RCEP 15 國農產品出口的 Top N HS6。
    baci_cache: 已讀入的年份 DataFrame 快取（{year: df}），供 Stage 2 共用。
    """
    top10_dict = {}

    for year in range(start_year, end_year + 1):
        cached = cache_db.get_top10(year)
        if cached:
            top10_dict[str(year)] = cached
            continue

        # 讀入（若 Stage 2 尚未讀，先讀；若已讀，共用）
        if year not in baci_cache:
            baci_cache[year] = load_baci_year(year, cfg)
        df = baci_cache[year]

        # 台灣出口：i=490，j∈RCEP_15
        tw_df = df[(df["i"] == TAIWAN_M49) & (df["j"].isin(RCEP_15_M49))]
        top_items = (tw_df.groupby("k")["v"].sum()
                         .nlargest(top_n).index.tolist())

        cache_db.set_top10(year, top_items)
        top10_dict[str(year)] = top_items
        logger.info(f"[Stage1] {year} Top{top_n}：{top_items}")

    return top10_dict
```

**5. Stage 2：RCEP 內部矩陣**

```python
def run_stage2(start_year: int, end_year: int, top10_dict: dict, cfg: dict,
               cache_db, baci_cache: dict) -> pd.DataFrame:
    """
    從 BACI 取出 RCEP 15 國之間（i∈RCEP_15，j∈RCEP_15）的 Top10 品項出口。
    baci_cache: 與 Stage 1 共用，避免重複 I/O。
    """
    frames = []

    for year in range(start_year, end_year + 1):
        cached = cache_db.get_rcep(year)
        if cached is not None:
            frames.append(cached)
            continue

        if year not in baci_cache:
            baci_cache[year] = load_baci_year(year, cfg)
        df = baci_cache[year]

        top10_set = set(top10_dict[str(year)])
        rcep_df = df[
            df["i"].isin(RCEP_15_M49) &
            df["j"].isin(RCEP_15_M49) &
            df["k"].isin(top10_set)
        ].copy()

        rcep_df["Year"]             = year
        rcep_df["data_provisional"] = (year >= 2023)
        rcep_df["Value_USD"]        = rcep_df["v"] * 1000

        cache_db.set_rcep(year, rcep_df)
        frames.append(rcep_df)

        # 讀完 Stage 1 + Stage 2 後，釋放當年記憶體
        if year in baci_cache:
            del baci_cache[year]

    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
```

**6. Stage 1+2 主流程呼叫方式**

```python
def run_pipeline(start_year: int, end_year: int, top_n: int, cfg: dict, cache_db):
    baci_cache = {}   # 跨 Stage 共用的記憶體快取，避免重複讀檔

    # Stage 1：台灣 Top10（同時預載 BACI，供 Stage 2 共用）
    top10_dict = run_stage1(start_year, end_year, top_n, cfg, cache_db, baci_cache)

    # Stage 2：RCEP 矩陣（優先使用 baci_cache 中已有的年份）
    rcep_df    = run_stage2(start_year, end_year, top10_dict, cfg, cache_db, baci_cache)

    # Stage 3：整合台灣出口 + RCEP 矩陣，HS 版本統一
    final_df   = run_stage3(top10_dict, rcep_df, cfg)

    # Stage 4：輸出 Excel
    run_stage4(final_df, start_year, end_year, cfg)
```

**7. HS Code 版本轉換（utils/hs_harmonizer.py）**

```python
def load_concordance(ref_dir: str) -> dict:
    concordance = {}
    for src_ver, filename in [("HS2007", "HS2007_to_HS2017.xlsx"),
                               ("HS2012", "HS2012_to_HS2017.xlsx")]:
        path = os.path.join(ref_dir, filename)
        if os.path.exists(path):
            df = pd.read_excel(path)
            concordance[src_ver] = df.groupby("old")["new"].apply(list).to_dict()
        else:
            logger.warning(f"找不到對照表 {filename}，HS 轉換將保留原碼")
    return concordance

def harmonize_row(hs6_orig: str, baci_version: str, concordance: dict) -> list[dict]:
    version_map = {"HS07": "HS2007", "HS12": "HS2012", "HS17": "HS2017"}
    src_ver = version_map[baci_version]
    if src_ver == "HS2017":
        return [{"HS6_Code": hs6_orig, "weight": 1.0,
                 "hs_converted": False, "hs_split": False, "hs_mapped": True}]
    mapping = concordance.get(src_ver, {}).get(hs6_orig)
    if not mapping:
        return [{"HS6_Code": hs6_orig, "weight": 1.0,
                 "hs_converted": True, "hs_split": False, "hs_mapped": False}]
    n = len(mapping)
    return [{"HS6_Code": code, "weight": 1.0/n,
             "hs_converted": True, "hs_split": (n>1), "hs_mapped": True}
            for code in mapping]
```

**8. 輸出規格**

```python
REQUIRED_COLUMNS = [
    "Year", "HS6_Code", "HS6_Code_Original", "HS6_Description_EN", "HS6_Description_ZH",
    "HS_Chapter", "Reporter", "Reporter_ISO3", "Reporter_M49", "Reporter_Group",
    "Partner",  "Partner_ISO3",  "Partner_M49",
    "Value_USD", "Value_USD_1000",
    "data_source", "baci_version", "data_provisional",
    "hs_converted", "hs_split", "hs_mapped", "data_quality", "Taiwan_Top10_Flag"
]

REQUIRED_SHEETS = [
    "長表_完整數據", "Top10_HS6_清單", "台灣_RCEP出口明細",
    "RCEP內部_出口矩陣", "年度彙整_出口總額", "數據品質報告"
]
```

**9. Streamlit GUI 要求**

- 開啟時自動環境檢查：掃描所有需要的 BACI 年份 CSV 是否存在，以清單顯示 ✅/❌
- 年份滑桿改變時，即時計算並顯示需要哪些 BACI 版本 + 預估執行時間
- `baci_cache` 字典在 pipeline 執行期間跨 Stage 1/2 共用（不重複讀檔）
- 斷點續傳：Stage 1 和 Stage 2 各自快取進 SQLite，重啟後從中斷處繼續
- 每處理完一個年份，立即更新進度條和日誌

**10. 錯誤處理**

- 找不到 BACI 檔案 → `FileNotFoundError`，顯示具體版本與年份，**停止執行**（非跳過）
- HS 對照表不存在 → `Warning`，保留原碼，繼續執行
- 某年份無台灣出口數據 → `Warning`，記錄至 error_log，繼續下一年
- 所有非致命錯誤寫入 SQLite error_log 表

---

## 10. README 使用教學

---

# RCEP 農產品貿易分析系統 v3.1 — 使用說明

## 系統需求

- Python 3.10+（[下載](https://www.python.org/downloads/)）
- 網路連線（BACI 下載用，程式執行時不需要）
- 至少 8GB 可用磁碟空間
- **不需要任何付費帳號或 API Key**

## 安裝

```bash
git clone [repo_url]
cd rcep_agri_trade
pip install -r requirements.txt
```

## 首次使用：手動下載步驟（只需做一次）

### M1–M3（60–120 分鐘）：下載 BACI 三版本

前往 `https://www.cepii.fr/CEPII/en/bdd_modele/bdd_modele_item.asp?id=37`
**不需要註冊帳號**，直接選版本下載。選擇版本 **202601**（2026 年 1 月最新版）。

| 選擇版本 | 下載哪些年份 | 說明 |
|---------|-----------|------|
| **BACI HS07** | 2010、2011（2 個 zip）| 涵蓋 2010–2011 |
| **BACI HS12** | 2012–2016（5 個 zip）| 涵蓋 2012–2016 |
| **BACI HS17** | 2017–2024（8 個 zip）| 涵蓋 2017–2024，含 2022–2024 |

> 若只分析部分年份，只下載對應年份即可。

### M4（15 分鐘）：解壓縮，放入對應資料夾

```
data/raw/baci/hs07/  ← 放 HS07 的 CSV（BACI_HS07_Y2010_V202601.csv 等）
data/raw/baci/hs12/  ← 放 HS12 的 CSV
data/raw/baci/hs17/  ← 放 HS17 的 CSV
```

### M5（5 分鐘）：下載 HS 版本對照表

1. 前往 `https://unstats.un.org/unsd/trade/classifications/correspondence-tables.asp`
2. 下載 **HS 2007 to HS 2017** 和 **HS 2012 to HS 2017**
3. 放入 `data/reference/` 資料夾

## 啟動

```bash
streamlit run app.py
```

系統自動掃描所有 BACI 年份是否就緒，顯示 ✅/❌ 清單，確認後開始執行。

## 操作步驟

1. 拖拉年份滑桿選擇分析範圍（預設 2010–2024）
2. 確認環境檢查全為 ✅
3. 點選「▶ 開始執行」
4. 等待完成（程式執行期間無需網路）
5. 點選「📥 下載 Excel」

## 常見問題

**Q：程式顯示某年份 BACI 檔案缺失（❌）**
A：回 CEPII 網站補下載對應版本的 zip，解壓縮後放入正確子資料夾，頁面會自動更新。

**Q：BACI 版本號不是 V202601**
A：修改 `config.yaml` 中 `baci → filename_pattern` 的版本號即可。

**Q：台灣數據和官方公布數字有出入**
A：BACI 的台灣數據（M49=490）來自 Comtrade，部分年份申報可能不完整，與財政部關務署統計年刊可能有差異。報表的「數據品質報告」工作表中會標記台灣數據的可信度。若需最高精度，可參考報告附注建議對照財政部原始資料。

**Q：2023–2024 標記了「provisional」**
A：BACI 最新兩年為初步值，CEPII 說明未來版本可能微調。更新時重新下載 BACI 新版本並覆蓋舊 CSV 即可，快取會自動更新。

**Q：汶萊/寮國/緬甸數據很少**
A：這三國在 BACI 本身就數據稀疏，已自動標記 `data_quality='sparse'`，建議在商業報告中附注說明。

---

## 11. 已知風險與備用方案矩陣

| 風險 | 發生機率 | 影響 | 備用方案 |
|------|---------|------|---------|
| **CEPII 版本號更新**（V202601→V202701）| 高（每年）| 程式找不到 BACI 檔案 | 修改 `config.yaml` 的 `filename_pattern` |
| **BACI 台灣數據缺漏**（M49=490 部分年份空白）| 中 | 台灣 Top10 某年份數據不完整 | 標記 `taiwan_baci_gap`；可手動補充財政部統計年刊 |
| **BACI 2023–2024 初步值被修正** | 中 | 近兩年數據需更新 | 下載新版 BACI，覆蓋舊 CSV，重執行（快取自動失效）|
| **HS 對照表未下載（M6 未做）** | 低 | HS07/HS12 數據代碼未轉換 | 保留原碼，標記 hs_mapped=False；對 2017–2024 完全無影響 |
| **小國數據稀疏**（BN/LA/MM）| 高（本來就稀疏）| 矩陣部分為 NULL | 標記 `sparse`，提供「ASEAN7」備用分組 |
| **磁碟空間不足** | 低 | 部分 CSV 無法解壓 | 分批分析（先 2017–2024，再擴展歷史年份）|
| **Excel 單表超過 100 萬行** | 低 | Excel 無法開啟 | 自動改輸出 CSV + Parquet，附閱讀腳本 |

---

*計畫版本：v3.1 | 最後修訂：2026 年 3 月*
*數據來源：CEPII BACI（台灣 + RCEP 全部）*
*API 請求次數：0 · 手動下載：15 個 CSV + 2 個 Excel*
