# 🌾 RCEP 農產品貿易分析系統

> **Taiwan's Agricultural Export Competitiveness under RCEP: A HS6-Level Trade Flow Analysis System**

本系統基於 CEPII BACI 雙邊貿易資料庫，以 HS6 六位碼層級分析台灣（M49=490）對 RCEP 15 國之農產品出口結構，並建構 RCEP 內部同品項貿易矩陣，以評估台灣農產品在區域整合架構下之競爭替代風險。

---

## 1. 研究動機與分析目標

RCEP（Regional Comprehensive Economic Partnership）於 2022 年 1 月 1 日生效，涵蓋 ASEAN 10 國及中國、日本、韓國、澳洲、紐西蘭等 15 個經濟體，形成全球最大的自由貿易區（佔全球 GDP 約 30%、貿易總額約 28%）。

台灣非 RCEP 締約方。隨 RCEP 逐步推進關稅減讓（目標為 10-20 年內達成 90% 以上品項零關稅），台灣農產品出口將面臨以下結構性衝擊：

1. **關稅差異劣勢**（Tariff Margin Erosion）：RCEP 成員國間互享優惠稅率，台灣同類商品須適用 MFN（最惠國）稅率，價格競爭力遞減。
2. **市場替代效應**（Trade Diversion）：進口國傾向轉向 RCEP 內部供應來源，壓縮台灣出口份額。

本系統旨在量化上述風險，具體回答以下問題：

- **Q1**：台灣對 RCEP 出口之農產品中，金額前 *N* 名品項（HS6 碼層級）為何？其時間序列趨勢如何？
- **Q2**：上述重點品項，RCEP 成員國之間是否存在大量內部貿易？（即：是否已有替代供應來源？）
- **Q3**：RCEP 內部該品項之貿易規模相對台灣出口額的比例為何？趨勢方向為何？

---

## 2. 資料來源

### 2.1 BACI（Base pour l'Analyse du Commerce International）

| 項目 | 內容 |
|------|------|
| **維護機構** | CEPII（Centre d'Études Prospectives et d'Informations Internationales） |
| **原始資料** | UN Comtrade（聯合國商品貿易統計資料庫） |
| **調和方法** | 以出口國申報值（FOB）與進口國申報值（CIF）進行交叉比對，透過統計推估法（Gaulier & Zignago, 2010）產出單一調和貿易流量值 |
| **空間涵蓋** | ≈ 200 國/地區 |
| **時間涵蓋** | 1995–2024（依版本而異） |
| **品項涵蓋** | HS6 六位碼，約 5,000 個品項 |
| **單位** | 千美元（Thousands of USD） |
| **取得方式** | https://www.cepii.fr/CEPII/en/bdd_modele/bdd_modele_item.asp?id=37 ，免費下載，無需帳號 |

> **引用格式**：Gaulier, G. and Zignago, S. (2010), "BACI: International Trade Database at the Product-Level. The 1994-2007 Version", *CEPII Working Paper*, N°2010-23.

### 2.2 HS 版本對照表

| 對照表 | 來源 |
|--------|------|
| HS2017 ↔ HS2007 | [UN Stats Conversion Tables](https://unstats.un.org/unsd/classifications/Econ/tables/HS2017toHS2007ConversionAndCorrelationTables.xlsx) |
| HS2017 ↔ HS2012 | [UN Stats Conversion Tables](https://unstats.un.org/unsd/classifications/Econ/tables/HS2017toHS2012ConversionAndCorrelationTables.xlsx) |

### 2.3 BACI 版本與時間涵蓋

| BACI Dataset | HS Nomenclature | Years Covered（CEPII 實際提供） | 本系統實際使用年份段 |
|-------------|-----------------|-------------------------------|-------------------|
| BACI_HS07 | HS Revision 2007 | 2007–2024（CEPII 實際涵蓋）| 本系統取 2007–2011 |
| BACI_HS12 | HS Revision 2012 | 2012–2024（CEPII 實際涵蓋）| 本系統取 2012–2016 |
| BACI_HS17 | HS Revision 2017 | 2017–2024（CEPII 實際涵蓋）| 本系統取 2017–2024 |

各 BACI 版本實際均涵蓋至 2024 年，CEPII 透過將較新 HS 版本回推轉換至該版本代碼的方式實現。本系統採各版本取其原生年份段的策略，原因是：(1) HS17 原生年份（2017–2024）無需轉換，最大限度減少品項合併損失；(2) 使用較舊 HS 版本分析近期資料時，因新→舊轉換跨度更大，品項損失更多，誤差也更大。

> **設計決策：各版本取其原生年份段（Native Period Routing）**
>
> CEPII 每個 BACI 版本實際上均涵蓋至 2024 年（例如 BACI_HS07 本身亦包含 2017–2024 年的資料，只是以 HS2007 命名慣例編碼）。本系統刻意選擇讓各版本只負責其「原生年份段」，原因如下：
>
> 1. **最小化 1:N 等比分配誤差**：HS17 版本的 2017–2024 年資料使用 HS2017 原生代碼，完全無需任何版本轉換（`hs_converted = False`），避免 1:N 拆分帶來的等比稀釋誤差。
> 2. **避免引入不必要的不確定性**：若改用 BACI_HS07 全段（2007–2024），則 2017–2024 年的所有品項仍須執行 HS2007→HS2017 轉換，反而讓 HS17 時期的資料增添不必要的映射不確定性。
> 3. **版本邊界與實際分類修訂一致**：每次 HS 改版（如 2012、2017）本身代表 UN 對商品分類的實質修訂。讓各版本負責自己改版後的原生年份，可使資料庫內部的分類一致性最高。
>
> 因此，若需分析 2018 年的某品項貿易，本系統一律從 BACI_HS17 讀取，而非 BACI_HS07 或 BACI_HS12，即便後兩者在技術上也包含該年度資料。

---

## 3. 分析方法論

### 3.1 Pipeline 總覽

```
                    ┌──────────────┐
                    │   BACI CSV   │  raw trade flows (t, i, j, k, v, q)
                    └──────┬───────┘
                           │
              ┌────────────┴────────────┐
              ▼                         ▼
     ┌─────────────────┐      ┌─────────────────┐
      │   Stage 1       │      │   Stage 2       │
      │ Taiwan Exports  │      │ RCEP Matrix     │
      │ M49=490 → RCEP  │      │ RCEP₁₅ → RCEP/TW│
      │ HS Harmonize    │      │ All Agr. Products│
      │ Top-N Ranking   │      │                 │
      └────────┬────────┘      └────────┬────────┘
              │                        │
              └───────────┬────────────┘
                          ▼
                 ┌─────────────────┐
                 │   Stage 3       │
                 │ Merge & Clean   │
                 │ HS → HS2017     │
                 │ Metadata Join   │
                 │ Quality Flags   │
                 └────────┬────────┘
                          ▼
                 ┌─────────────────┐
                 │   Stage 4       │
                 │ Excel Export    │
                 │ 8 Worksheets   │
                 └─────────────────┘
```

### 3.2 Stage 1：台灣出口 Top-N 計算

**輸入**：BACI CSV（各年度）

**步驟**：

1. 從各年度 BACI 原始資料中，篩選 `i = 490`（台灣 M49 代碼）且 `j ∈ RCEP₁₅`（15 個 RCEP 成員國之 M49 集合）的紀錄。

2. 進一步限縮為農產品範圍：預設為標準農產品 HS Chapter 01–24（可由 GUI 增減，如擴充含木材 Ch.44 或棉花 Ch.52）。

3. **HS 版本同步轉換（Harmonization）**：由於不同年份的 BACI 資料使用不同 HS 版本（HS07/HS12/HS17），為確保跨年度可比性，在計算排名前，先將所有 HS6 代碼統一轉換至 **HS2017 基準**。

4. **排除轉口特殊品項與排名**：排除 `config.yaml` 中所列之轉口干擾品項（`exclude_hs6`），再以轉換後之 HS2017 代碼進行 `groupby` 加總，取出口金額前 *N* 名形成 `top_n_dict`。

5. **保留全量數據**：本階段除了產出 Top-N 清單外，也完整保留台灣（對 RCEP）的所有農產品出口紀錄，送交後續階段（Stage 3）統一轉換與標記。

**輸出**：
- `top_n_dict = { "2007": ["030617", "210690", ...], "2008": [...], ... }`
- `taiwan_df`（包含台灣對 RCEP 各年份全量農產品出口紀錄）

> **設計決策**：Top-N 必須在 HS 同步轉換之後計算（v4.1 修正）。
> 若在轉換前計算，則：(a) HS07 時代的 `030379`（一個大類）可能排名第一，但轉換後被拆成 13 個 HS17 代碼，每個代碼的金額僅為原始的 1/13，不再具有 Top-N 資格；(b) 跨年度排名基準不一致，2015 年的 Top 1 與 2020 年的 Top 1 可能代表不同分類粒度的商品。

### 3.3 HS Nomenclature Harmonization

本系統使用 UN Stats 提供之 HS 版本對照表（Conversion & Correlation Tables），建立映射字典：

```
concordance = {
    "HS2007": { old_code → [new_code_1, new_code_2, ...] },
    "HS2012": { old_code → [new_code_1, new_code_2, ...] }
}
```

**映射類型與處理邏輯**：

| 映射類型 | 範例 | 處理方式 |
|---------|------|---------|
| **1:1**（代碼不變） | `010121` → `010121` | 直接對應，`weight = 1.0` |
| **1:N**（一碼拆多碼） | `030749` → `{030743, 030749}` | 等比分配：`Value_new = Value_old / N` |
| **N:1**（多碼合一碼） | `{040110, 040120}` → `040110` | 各自獨立映射，加總後即為合併值 |
| **Unmapped**（無對應） | 新版本才出現的代碼 | 保留原碼，標記 `hs_mapped = False` |

**等比分配公式**（適用於 1:N 拆分）：

$$V_{new_i} = \frac{V_{old}}{N}, \quad \forall\, i \in \{1, 2, \ldots, N\}$$

其中 $V_{old}$ 為舊代碼之原始貿易值，$N$ 為該舊代碼對應的新代碼數量。

> **已知限制**：等比分配假設各子類別之貿易金額相等，此假設在實務上通常不成立。理想情況下應使用各子類別在目標年份（HS2017 年份）中的實際貿易金額比例作為權重（Proportional Allocation），但此方法需要額外的校準資料集，目前版本尚未實作。

### 3.4 Stage 2：RCEP 內部矩陣擷取

**目標**：擷取 RCEP 15 國之間，以及 RCEP 15 國對台灣的農產品貿易流量。

**全量擷取與後行過濾機制（v4.1+ 架構）**：

自 v4.1 版起，系統為避免前置過濾可能造成的歷史代碼遺漏，改採更強健的**全量擷取**策略：

1. 在 Stage 2 階段，系統會完整撈取所有 RCEP 國家出口至 RCEP 及台灣的農產品（依設定之 HS 章節，預設 01-24）全量數據。
2. 此階段**不進行**任何 HS6 排序或過濾。
3. 所有歷史原始數據將統一交由 Stage 3 執行 HS2017 同步轉換。待代碼統一後，再藉由 `top_n_dict` 全局標註 `Taiwan_TopN_Flag`。

此架構消除了不同 HS 版本落差導致的比較誤差，更能輕易產出「台灣自選項目進口比對」等高關聯性報表，且不干擾台灣原有的出口排名。

### 3.5 Stage 3：資料清理、轉換與標記

1. **RCEP 原始資料**（含內部互貿與對台出口）：逐筆經過 `harmonize_to_hs2017()` 轉換為 HS2017 代碼。
2. **台灣出口資料**：同樣逐筆經過 `harmonize_to_hs2017()` 轉換（v4.1 修正）。
3. **Metadata 合併**：
   - 英文商品說明（`HS6_Description_EN`）：從 BACI 附帶之 `product_codes_HS{ver}_V*.csv` 讀取，若目標版本無對應則 fallback 至 HS17。
   - 國家名稱：從 `country_codes_V*.csv` 讀取。
4. **品質標記**：
   - `data_provisional = True`：2023–2024 年（BACI 初步估計值）
   - `data_quality = "sparse"`：BRN（汶萊）、LAO（寮國）、MMR（緬甸）
5. **Taiwan_TopN_Flag**：所有記錄（不論台灣或 RCEP）在轉換為最終 HS2017 代碼後，統一對照 `top_n_dict` 標記。

### 3.6 Stage 4：報表產出

產出包含 8 個工作表的 `.xlsx` 檔案（詳見第 5 節「結果判讀」）。

若資料量超過 1,000,000 列（Excel 上限）或手動選擇 CSV，系統將產出一個 **.zip 壓縮檔**，內含上述 8 個工作表對應的獨立 `.csv` 檔案。

---

## 4. 系統使用指南

### 4.1 環境需求

| 項目 | 要求 |
|------|------|
| Python | ≥ 3.10 |
| 磁碟空間 | ≥ 8 GB（BACI 三版約 6 GB） |
| 網路 | 僅首次下載資料時需要 |
| 付費服務 | 無（不需要 API Key） |

### 4.2 安裝步驟

```bash
# 1. 取得程式碼
git clone https://github.com/ga815647/RCEP_AgriTrade.git
cd RCEP_AgriTrade

# 2. 安裝 Python 相依套件
pip install -r requirements.txt
```

### 4.3 資料準備（僅需執行一次）

#### Step 1：下載 BACI 資料（約 30-60 分鐘）

前往 https://www.cepii.fr/CEPII/en/bdd_modele/bdd_modele_item.asp?id=37

下載最新版本的三個 ZIP 壓縮檔，解壓縮至對應目錄：

```
data/raw/baci/
├── hs07/    ← BACI_HS07_V*.zip 解壓縮內容
│   ├── BACI_HS07_Y2007_V202601.csv
│   ├── BACI_HS07_Y2008_V202601.csv
│   ├── ...
│   └── product_codes_HS07_V202601.csv
├── hs12/    ← BACI_HS12_V*.zip 解壓縮內容
│   ├── BACI_HS12_Y2012_V202601.csv
│   ├── ...
│   ├── product_codes_HS12_V202601.csv
│   └── country_codes_V202601.csv
└── hs17/    ← BACI_HS17_V*.zip 解壓縮內容
    ├── BACI_HS17_Y2017_V202601.csv
    ├── ...
    ├── product_codes_HS17_V202601.csv
    └── country_codes_V202601.csv   ← 系統從此處讀取國家代碼
```

> 系統使用 `glob` 萬用字元匹配（`BACI_{version}_Y{year}_V*.csv`），CEPII 更新版本號時無需修改任何程式碼。

#### Step 2：下載 HS 版本對照表（約 5 分鐘）

下載以下兩個 Excel 檔案，放入 `data/reference/` 目錄：

1. [HS2017toHS2007ConversionAndCorrelationTables.xlsx](https://unstats.un.org/unsd/classifications/Econ/tables/HS2017toHS2007ConversionAndCorrelationTables.xlsx)
2. [HS2017toHS2012ConversionAndCorrelationTables.xlsx](https://unstats.un.org/unsd/classifications/Econ/tables/HS2017toHS2012ConversionAndCorrelationTables.xlsx)

> 請保持原始檔名。系統會自動偵測欄位並反轉映射方向（原始檔案為 HS2017 → 舊版，系統反轉為 舊版 → HS2017）。

### 4.4 啟動與操作

```bash
streamlit run app.py
```

瀏覽器自動開啟後：

1. **環境檢查**：畫面上方以 ✅/❌ 清單顯示各必要檔案是否就位。
2. **參數設定**（左側邊欄）：
   - **📅 時間範圍**：兩個下拉式選單（起始與結束年份），範圍由 `config.yaml` 的 `time_range.start` / `time_range.end` 動態決定（預設 2007–2024）。
   - **🔢 Top N**：預設 10（可調整 5–20）
   - **🌏 RCEP 成員國範圍**：多選清單，預設全部 15 國。可取消勾選不感興趣的國家（最少需保留 2 國）。*選擇僅在當次執行生效，不會寫回 config.yaml。*
   - **🌾 農產品定義範圍**：多選標籤（Multiselect）並搭配「快速選取」按鈕。預設為 01–24（標準農產品）。可透過按鈕快速切換為含木材（Ch.44）或含棉花（Ch.52）的組合，亦可手動增減個別章節，**支援非連續選取**。
   - **📄 輸出格式**：`自動`（超過門檻切換 CSV）/ `強制 Excel` / `強制 CSV`
3. **執行**：點選「▶ 開始執行」，進度條會顯示目前執行進度。
4. **輸出**：執行 100% 完成後，進度條下方會自動出現「📥 下載報表」按鈕。

---

## 5. 結果判讀

### 5.1 輸出工作表結構

| # | 工作表名稱 | 內容 | 用途 |
|---|-----------|------|------|
| 1 | `年度彙整_出口總額` | 按國家×年份加總 | 趨勢與市佔率比較 |
| 2 | `台灣出口_Top{N}_HS6_清單` | 每年台灣出口前 N 品項 | **核心摘要（台灣）** |
| 3 | `台灣_RCEP出口明細` | 台灣全部農產品出口（全量） | 台灣出口全貌 |
| 4 | `RCEP對台灣自選項目進口明細` | RCEP 到台灣的自選 HS6 貿易流 | **台灣進口替代分析** |
| 5 | `RCEP內部_Top{N}_HS6_清單` | 每年 RCEP 內部互貿前 N 品項 | **核心摘要（RCEP 內部）** |
| 6 | `RCEP內部_出口矩陣` | RCEP 15 國間全量貿易 | **區域內競爭分析** |
| 7 | `長表_完整數據` | 台灣 + RCEP 所有紀錄 | 進階分析用原始資料 |
| 8 | `數據品質報告` | 各年品質標記統計 | 資料可信度評估 |

### 5.2 關鍵欄位說明

| 欄位 | 型態 | 說明 |
|------|------|------|
| `HS6_Code` | str(6) | 統一後的 HS2017 六位碼。前導零保留（如 `030617`）。 |
| `HS6_Code_Original` | str(6) | 轉換前的原始代碼（HS07 或 HS12 版本）。若無轉換，與 HS6_Code 相同。 |
| `HS6_Description_EN` | str | BACI metadata 提供的英文品項說明。 |
| `Value_USD` | float | 貿易金額（美元）。注意 BACI 原始單位為千美元，系統已乘以 1000 轉換。 |
| `baci_version` | str | 原始資料所屬 BACI 版本：`HS07` / `HS12` / `HS17`。 |
| `Taiwan_TopN_Flag` | bool | 該品項（以 HS2017 代碼判定）是否為當年度台灣出口的前 N 名。 |
| `hs_converted` | bool | 是否經過 HS 版本轉換。若為 True，代表原始代碼 ≠ 最終代碼。 |
| `hs_split` | bool | 是否經過 1:N 拆分。若為 True，金額已被等比稀釋。 |
| `hs_mapped` | bool | 是否在對照表中找到有效映射。若為 False，代表可能是新增代碼或對照缺失。 |
| `data_provisional` | bool | 是否為 BACI 初步值（通常為最近兩年）。 |
| `data_quality` | str | `verified`（正式值）/ `provisional`（初步值）/ `sparse`（小國稀疏資料）。 |

### 5.3 解讀範例

#### 範例 A：辨識台灣核心出口品項

在 `台灣出口_Top{N}_HS6_清單` 中觀察：
- 若 `030617`（冷凍蝦）從 2007 到 2024 年**每年都在 Top N**，代表這是台灣對 RCEP 的**結構性核心出口品項**。
- 若 `210690`（其他食品調製品）在 2018 年後排名驟升，可能反映台灣食品加工業的出口轉型。

#### 範例 B：評估競爭替代風險

在 `RCEP內部_出口矩陣` 中篩選 `HS6_Code = "030617"`：
- 若越南（VNM）→ 日本（JPN）的 `030617` 出口金額從 2015 年的 5,000 萬美元增長到 2024 年的 2 億美元，而同期台灣對日本的同品項出口持平或下降，此 **交叉趨勢** 強烈暗示越南正在替代台灣的市場份額。
- 可進一步計算台灣的**市場佔有率**：

$$\text{Market Share}_{TW \to JP}^{030617}(t) = \frac{V_{TW \to JP}^{030617}(t)}{\sum_{\forall\, c \in \{TW, \text{RCEP}_{15}\}} V_{c \to JP}^{030617}(t)}$$

#### 範例 C：識別 HS 拆分對數據的影響

若在 `長表_完整數據` 中發現某品項 2010-2011 年的 `hs_split = True`：
- 代表該筆金額是來自一個更大的舊代碼類別按 1/N 均分的結果。
- 若 N 值很大（如 13），單筆金額的估計誤差可能很高，建議改用 `HS6_Code_Original` 回溯原始類別金額。

---

## 6. 已知限制

| 項目 | 說明 | 影響程度 |
|------|------|---------|
| **矩陣範圍** | RCEP 內部矩陣僅篩選台灣 Top-N 品項，非各國農產品出口全貌 | ⚠️ 中 |
| **等比分配假設** | 1:N HS 拆分時假設各子類別金額相等 | ⚠️ 中（個別品項可能高估或低估） |
| **初步值** | 2023-2024 為 BACI 暫估值 | ⚠️ 低（趨勢方向通常可靠） |
| **M49=490** | 台灣在 UN Comtrade 中歸類為 "Other Asia, nes"，部分國家可能未申報對台進口 | ⚠️ 中 |
| **不含服務貿易** | 僅分析 HS 編碼涵蓋之商品（貨物）貿易 | ℹ️ 系統邊界 |
| **無加權拆分** | 未使用 Proportional Allocation 校準 1:N 拆分權重 | ℹ️ 改進方向 |
| **農產品定義** | 預設為標準農產品 HS Chapter 01-24，不含 Chapter 44（木材）或 Chapter 52（棉花）等廣義農林產品 | ℹ️ 系統預設（可於 GUI 勾選擴充） |
| **HS22 隱藏轉換** | BACI_HS17 中 2022–2024 年資料由 CEPII 內部完成 HS22→HS17 回推轉換，存在版本轉換的固有誤差，資料品質與 2017–2021 年原生資料略有差異 | ℹ️ 低 |
| **新→舊轉換品項損失** | 各 BACI 版本對近期年份均採新版→舊版回推轉換，此方向轉換會造成部分細分品項被合併而消失；使用越舊的 HS 版本分析越近期的資料，品項損失越大 | ⚠️ 中（使用 HS07 分析 2020 年後資料時尤為明顯） |

### 6.1 報表判讀注意事項（來自實際產出的觀察）

以下三項為實際執行後觀察到的現象，非程式錯誤，但引用數據時須留意：

#### 🟡 注意 1：同一 HS6 代碼可能出現多個英文說明

**現象**：例如 `030344`（大目鮪，Bigeye tunas）在 Excel 長表中，不同年份的 `HS6_Description_EN` 欄位可能出現兩到三種略有差異的文字描述。

**成因**：系統從各 BACI 版本的 `product_codes` 檔案讀取商品說明。HS07、HS12、HS17 三個版本對同一代碼的英文措辭可能微有不同（例如 "Tunas, bigeye" vs "Bigeye tunas, frozen"）。當該代碼在 HS2017 對照表中無需轉換（1:1 映射），系統直接沿用原始版本的說明文字。

**影響**：**不影響任何數值計算**。僅視覺上不統一。若需一致化，可在 Excel 中以 `HS6_Code` 做 VLOOKUP，統一替換為 HS17 版本的說明。

#### 🟡 注意 2：最新年份的數值波動需謹慎引用

**現象**：例如台灣→中國 2024 年之出口總額可能較 2022-2023 年出現明顯反彈或波動。

**成因**：
1. BACI 的 2023-2024 年數據標記為 `data_provisional = True`，為 CEPII 基於已接收申報的初步估計值，後續版本可能修正 5-15%。
2. BACI 的調和方法（Reconciliation）涉及出口方與進口方的交叉比對。對於台灣（M49=490），由於部分進口國可能未單獨申報對台貿易，CEPII 的統計推估可能將經第三方轉口的貿易流量計入，導致數字偏高或偏低。

**建議**：引用最新年份數據時，應標注「BACI 初步值，可能隨後續版本修正」。可在報表中以 `data_provisional` 欄位識別此類紀錄。

#### 🟢 註記 3：RCEP 矩陣已更新為「農產品全量矩陣」(v4.1+)

**現象**：在 `RCEP內部_出口矩陣` 中，現在可以看到澳洲的小麥 (`1001`)、牛肉 (`0202`) 或越南的咖啡 (`0901`) 等主力產品，出口金額與市佔率表現正常。

**成因**：自 v4.1 版起，系統已改採全量擷取策略。這意味著 RCEP 15 國之間的所有農產品貿易流（依設定之 HS 章節）都會被完整收錄，不再僅限於台灣出口項目的切面。

**影響**：**此矩陣現在可用於評估 RCEP 各國在農產品貿易上的整體規模與競爭對比**。這有助於您除了觀察台灣出口強項外，也能同時掌握區域內整體的農產供需流向與各國核心版圖。

### 6.2 資料品質風險揭露（來自實際產出的深度分析）

以下為透過實際產出數據交叉驗證後發現的結構性風險，**非程式錯誤**，但直接影響研究結論的可靠性。

#### 🔴 風險 1：轉口貿易品項佔據 Top-N 排名（Re-export Contamination）

**具體案例**：
- `220820`（白蘭地/干邑）長年位居台灣 Top 10，其中對越南的累計出口高達 **USD 11.4 億**。然而台灣本身不生產干邑白蘭地，這幾乎確定是法國產品經台灣中轉後出口越南的轉口貿易。
- `240220`（香菸）2016 年後每年排名 Top 2–7，2021 年甚至達 **USD 2.47 億**。

**成因**：BACI 的統計調和方法（Gaulier & Zignago, 2010）在進行出口方與進口方金額比對時，會將轉口（re-export）計入中轉國的出口值。台灣（M49=490）作為亞太地區的物流樞紐，部分高價商品的轉口貿易被計入台灣出口統計。

**衍伸影響**：
1. **Top-N 排名失真**：若 220820 和 240220 各佔一席，實際的台灣農產品 Top 10 只剩 8 個名額，真正的台灣農業出口品項（如水產、茶葉）可能被擠出排名。
2. **RCEP 競爭矩陣偏誤**：系統會去查 RCEP 國家之間的白蘭地和香菸貿易——這些國家的確有大量出口，但這種「競爭」與台灣農業的實質競爭力無關。
3. **趨勢分析誤判**：轉口貿易量受國際供應鏈調整影響劇烈，可能產生與農產品毫無關係的數值波動。

**系統處置與預設設定**：`config.yaml` 提供 `exclude_hs6` 排除清單機制。系統預設已排除以下品項，研究者可自行決定是否調整（還原或新增）：

```yaml
exclude_hs6:
  codes: ["220820", "240220", "050510"]   # 預設排除：白蘭地、香菸、羽毛
  reason: "轉口貿易嫌疑"
```

排除後，這些品項**不參與 Top-N 計算**（Top 10 會由後面的品項遞補），但**仍保留在台灣出口明細表中**，確保資料完整性。

#### 🟡 風險 2：HS 版本切換年份的數值斷層（Version Seam Artifact）

**具體案例**：`220820`（白蘭地）在 2011 年金額為 **USD 1.17 億**，2012 年驟降至 **USD 57,368**（跌幅 99.95%），2013 年又回升至 **USD 1.52 億**。

**成因**：2011→2012 年恰為 HS07→HS12 的 BACI 版本切換邊界。不同版本的 BACI 資料在統計調和時使用的基準國申報年份不同，可能導致特定國家/品項組合在接縫年份出現異常值。此現象非系統轉換錯誤，而是 BACI 數據本身的版本拼接問題。

**受影響年份**：**2011↔2012**（HS07→HS12）、**2016↔2017**（HS12→HS17）

**建議**：
- 進行時間序列分析時，應對版本邊界年份標記為「接縫觀測值」（Seam Observation），不宜單獨引用。
- 若需連續趨勢線，可考慮對邊界年份取前後 2 年的移動平均值。

#### 🟡 風險 3：1:N 拆分稀釋對 Top-N 排名的影響（Split Dilution Effect）

**實測數據**：2010–2016 年（HS07/HS12 時期）的台灣出口中，約 **11.2% 的筆數**經過 1:N 等比拆分（`hs_split = True`）。

**具體影響**：
- 若某個 HS07 的大類代碼（如 `030379`）在 HS2017 中被拆成 13 個子類代碼，則每個子類僅獲得原始金額的 1/13 ≈ 7.7%。
- 這些被稀釋的子代碼各自的金額可能不足以進入 Top-N，即使原始大類代碼的總金額本來可以排名第一。
- 反向效果：若某個 HS17 品項大部分金額來自一個被 13 等分的舊代碼，其在 2010–2016 年的排名和金額精確度都會顯著下降。

**建議**：對 `hs_split = True` 的紀錄，研究者可使用 `HS6_Code_Original` 回溯原始類別金額，以驗證拆分後的金額是否合理。

#### ℹ️ 風險 4：研究邊界定義問題（Scope Definition）

| 品項 | 歸類 | 爭議 |
|------|------|------|
| `050510` 羽毛及羽絨 | HS Chapter 05（動物產品）| 技術上屬 HS 01–24，但非食品農業 |
| `240220` 香菸 | HS Chapter 24（菸草）| 標準農產品定義涵蓋，但是否屬於農業政策關注範圍有爭議 |
| `220820` 白蘭地 | HS Chapter 22（飲料）| 屬農產品，但轉口性質使其不代表台灣農業競爭力 |

這些品項是否應被分析取決於研究目的。系統提供兩種處置方式：
1. **HS 章節範圍調整**：在 GUI 的「🌾 農產品定義範圍」中縮小範圍（如改為 01–21 排除飲料與菸草）
2. **品項個別排除**：在 `config.yaml` 的 `exclude_hs6.codes` 中指定（**強烈建議使用者執行前，先檢視 `config.yaml` 中的預設排除品項**，不想要的排除設定可以清空或註解掉）

#### ⚠️ 風險 5：複合效應（Compound Risk）

上述風險可疊加：

```
轉口品項 (風險1)
  + 恰好在版本邊界年份 (風險2)
  + 且經歷代碼拆分 (風險3)
  → 三重不確定性
```

**範例**：若 `220820` 在 HS07→HS12 切換時既出現版本接縫斷層，又有部分子代碼需要拆分，則 2012 年的數值不確定性極高（數據消失 + 轉口波動 + 拆分稀釋）。

**建議**：在正式研究報告中，應對同時觸發多項風險的數據點（可透過 `hs_split`、`hs_converted`、`data_provisional` 等欄位交叉篩選）進行敏感度分析（Sensitivity Analysis），或在圖表中以不同符號標記其可信度等級。

## 7. 技術風險矩陣

| 風險事件 | 發生條件 | 影響 | 處置方式 |
|---------|---------|------|---------|
| CEPII 版本號更新 | BACI 釋出新版（如 V202702） | 舊版的 V202601 不再更新 | `glob` 匹配，無需改碼 |
| HS2022 版本出現 | BACI 未來可能推出 HS22 Dataset | 需新增轉換規則 | 新增 `HS22→HS17` 對照表，加入 `version_router` |
| Excel 行數上限 | 分析範圍或 Top-N 過大 | 超過 1,048,576 列 | 自動切換 CSV 輸出 |
| 記憶體不足 | 大量年份同時載入 | OOM Error | `baci_cache` 讀後即釋放，同一年只保留到 Stage 2 完成 |

---

## 8. 專案結構

```
RCEP_AgriTrade/
├── app.py                 # Streamlit entry point
├── config.yaml            # Runtime configuration (year range, RCEP countries, routing)
├── requirements.txt       # Python dependencies
├── README.md              # This file
│
├── pipeline/
│   ├── stage1_taiwan.py   # Taiwan exports extraction + HS harmonization + Top-N
│   ├── stage2_baci.py     # RCEP & Taiwan trade flows extraction (Full Agricultural Matrix)
│   ├── stage3_clean.py    # Merge, harmonize, metadata join, quality flags
│   └── stage4_export.py   # Multi-sheet export (8 Worksheets/CSVs in ZIP)
│
├── utils/
│   ├── baci_loader.py     # BACI CSV reader with glob matching (v4.0)
│   ├── hs_harmonizer.py   # HS concordance table loader & harmonization engine
│   ├── country_codes.py   # M49/ISO3/ISO2 country code mappings
│   ├── validators.py      # Pre-flight environment checks
│   └── cache.py           # SQLite-based pipeline cache
│
└── data/                  # (Not tracked in Git)
    ├── raw/baci/          # BACI CSV files (hs07/, hs12/, hs17/)
    └── reference/         # UN Stats HS conversion Excel tables
```

---

## 9. 設定檔說明（`config.yaml`）

```yaml
time_range:
  start: 2007              # 分析起始年份（GUI 起始預設值）
  end: 2024                # 分析終止年份（GUI 終止預設值）

top_n: 10                  # 每年取前 N 大品項（GUI 可調整 5–20）

rcep_countries:
  asean10: [BN, KH, ID, LA, MY, MM, PH, SG, TH, VN]
  others:  [CN, JP, KR, AU, NZ]

agriculture_hs_chapters: [1..24]   # 農產品 HS 章節範圍（GUI 可擴大）

hs_base_version: "HS2017"

baci:
  version_router:                  # 動態結構 (v4.2+)
    - hs_version: "HS07"           # year_end: null 代表延伸至 time_range.end
      year_start: 2007
      year_end: 2011
    - hs_version: "HS12"
      year_start: 2012
      year_end: 2016
    - hs_version: "HS17"
      year_start: 2017
      year_end: null               # ← 自動跟隨 time_range.end，不需手動同步
  baci_dir: "data/raw/baci"
  filename_pattern: "BACI_{version}_Y{year}_V*.csv"

taiwan_m49: 490

exclude_hs6:
  codes: ["220820", "240220", "050510"] # 預設排除品項（如白蘭地）。若不排除請設為空陣列 []
  reason: "轉口貿易嫌疑"           # 排除原因標記

custom_import_hs6: ["210690", "030344", "030343", "030342", "030341", "230990", "060290", "071029", "030192", "190590"] # RCEP對台灣自選進口品項 (以 HS2017 為準)

output:
  format: auto                     # auto | excel | csv
  output_dir: "output"
  include_quality_sheet: true
  excel_row_limit: 1000000         # auto 模式下觸發 CSV 切換的門檻
```

> **向下相容**：若 `version_router` 仍為舊的 dict 格式（如 `"2007-2011": "HS07"`），系統可自動識別並正常運作。
> **GUI 覆蓋**：GUI 中對 RCEP 成員國、HS 章節、輸出格式的修改僅在當次執行時生效，不會寫回 `config.yaml`。
> **快取機制**：系統會自動根據 `config.yaml` 內的設定（如 `exclude_hs6`、RCEP 國家等）計算 Config Hash。若修改這些過濾規則，程式將自動捨棄舊快取並重新計算，無需手動刪除快取檔。

---

## 10. 常見問題

| 問題 | 回答 |
|------|------|
| 需要網路嗎？ | 首次下載資料後，所有分析均在本機離線完成。 |
| 台灣數據從哪來？ | 從 BACI CSV 中以 `i=490` 過濾，同一資料庫、同一統計方法。 |
| 跟海關數據不一致？ | BACI 使用出進口交叉調和；海關為單方申報。方法論不同、數字有差異，趨勢通常一致。 |
| 新版 BACI 怎麼更新？ | 重新下載 ZIP → 解壓縮覆蓋 → 無需改碼（glob 匹配）。 |
| 可以分析 Top 20 嗎？ | GUI 左側邊欄直接調整。 |
| 為何不用 HS2022？ | BACI HS17 已涵蓋至 2024 年，尚無需要。 |
| GUI 修改會儲存嗎？ | 不會。GUI 調整僅影響當次執行，原始 `config.yaml` 不被改動。 |
| 可以只分析部分國家嗎？ | 可以。在 GUI 的「🌏 RCEP 成員國範圍」中取消勾選不需要的國家即可。 |
| 可以把木材/棉花納入嗎？ | 可以。在「🌾 農產品定義範圍」中擴大 HS 章節到 44 或 52 即可。 |

---

## 11. 授權與引用

本專案之分析結果基於 CEPII BACI 資料庫。學術使用時請引用：

> Gaulier, G. and Zignago, S. (2010), "BACI: International Trade Database at the Product-Level. The 1994-2007 Version", *CEPII Working Paper*, N°2010-23.

HS 版本對照表來源：UN Statistics Division, *Classifications Registry*.
