import streamlit as st
import yaml
import os
import io
import time
from loguru import logger

from pipeline.stage1_taiwan import run_stage1
from pipeline.stage2_baci import run_stage2
from pipeline.stage3_clean import run_stage3
from pipeline.stage4_export import run_stage4
from utils.validators import check_environment
from utils.country_codes import ALL_COUNTRIES

def load_config():
    with open("config.yaml", "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

cfg = load_config()

st.set_page_config(page_title="RCEP 農產品貿易分析系統", layout="wide")

st.markdown(
    """
    <style>
    [data-testid="stSidebar"] {
        min-width: 400px;
        max-width: 800px;
    }
    </style>
    """,
    unsafe_allow_html=True
)

st.title("🌾 RCEP 農產品貿易分析系統")

if "start_year" not in st.session_state:
    st.session_state["start_year"] = cfg["time_range"]["start"]
if "end_year" not in st.session_state:
    st.session_state["end_year"] = cfg["time_range"]["end"]

# ──────────── Sidebar ────────────
st.sidebar.header("⚙️ 參數設定")

# --- 年份範圍 ---
st.sidebar.subheader("📅 時間範圍")
col1, col2 = st.sidebar.columns(2)

years = list(range(cfg["time_range"]["start"], cfg["time_range"]["end"] + 1))

with col1:
    start_year = st.selectbox("起始年份", options=years, key="start_year")
    
with col2:
    end_year = st.selectbox("結束年份", options=years, key="end_year")

if start_year > end_year:
    st.sidebar.error("⚠️ 起始不得大於結束")

# --- Top N ---
top_n = st.sidebar.number_input("🔢 每年 Top N", min_value=1, max_value=20, value=cfg["top_n"], step=1)

# --- B-1：RCEP 成員國勾選 ---
st.sidebar.subheader("🌏 RCEP 成員國範圍")

# 從 config 建立預設選取清單（ISO2 → ISO3 映射）
_cfg_iso2_all = cfg["rcep_countries"]["asean10"] + cfg["rcep_countries"]["others"]
_default_iso3 = []
for iso3, v in ALL_COUNTRIES.items():
    if v["iso2"] in _cfg_iso2_all and v["group"] != "Taiwan":
        _default_iso3.append(iso3)

# 建立可選項（全部 15 國）
_rcep_options = []
_rcep_labels = {}
for iso3, v in ALL_COUNTRIES.items():
    if v["group"] != "Taiwan":
        label = f"{iso3} — {v['name_zh']}"
        _rcep_options.append(iso3)
        _rcep_labels[iso3] = label

with st.sidebar.expander("🌏 RCEP 成員國細部選取", expanded=True):
    selected_rcep_iso3 = []
    cols = st.columns(3)
    for i, iso3 in enumerate(_rcep_options):
        with cols[i % 3]:
            # 預設勾選與否來自 config 或之前的邏輯
            is_default = iso3 in _default_iso3
            if st.checkbox(iso3, value=is_default, key=f"rcep_{iso3}", help=_rcep_labels[iso3]):
                selected_rcep_iso3.append(iso3)

if len(selected_rcep_iso3) < 2:
    st.sidebar.warning("⚠️ 至少需選取 2 個 RCEP 成員國")

# --- B-2：農產品 HS 章節範圍 ---
st.sidebar.subheader("🌾 農產品定義範圍")

_default_chapters = cfg.get("agriculture_hs_chapters", list(range(1, 25)))

_preset_map = {
    "標準農產品 (01–24)": list(range(1, 25)),
    "含木材 (01–24, 44)": list(range(1, 25)) + [44],
    "含棉花 (01–24, 52)": list(range(1, 25)) + [52],
}

def get_initial_preset(chapters):
    chapters_set = set(chapters)
    for p_name, p_list in _preset_map.items():
        if set(p_list) == chapters_set:
            return p_name
    return "自訂"

if "preset_radio" not in st.session_state:
    st.session_state.preset_radio = get_initial_preset(_default_chapters)

for i in range(1, 98):
    key = f"hs_ch_{i}"
    if key not in st.session_state:
        st.session_state[key] = (i in _default_chapters)

def on_preset_change():
    preset = st.session_state.preset_radio
    if preset != "自訂":
        hs_list = _preset_map[preset]
        for i in range(1, 98):
            st.session_state[f"hs_ch_{i}"] = (i in hs_list)

def on_checkbox_change():
    selected_set = {i for i in range(1, 98) if st.session_state.get(f"hs_ch_{i}", False)}
    matched_preset = "自訂"
    for p_name, p_list in _preset_map.items():
        if selected_set == set(p_list):
            matched_preset = p_name
            break
    st.session_state.preset_radio = matched_preset

# 預設組合快捷鍵
_preset = st.sidebar.radio(
    "快速選取",
    options=["標準農產品 (01–24)", "含木材 (01–24, 44)", "含棉花 (01–24, 52)", "自訂"],
    key="preset_radio",
    on_change=on_preset_change,
    horizontal=True
)

with st.sidebar.expander("🌾 農產品詳細章節選取", expanded=False):
    selected_chapters = []
    cols = st.columns(4)
    for i in range(1, 98):
        with cols[(i-1) % 4]:
            if st.checkbox(f"{i:02d}", key=f"hs_ch_{i}", on_change=on_checkbox_change):
                selected_chapters.append(i)

# 動態提示
_hs_hints = []
if set(selected_chapters) == set(range(1, 25)):
    _hs_hints.append("📋 標準農產品定義")
else:
    _hs_hints.append(f"📋 已選 {len(selected_chapters)} 個章節")
if 44 in selected_chapters:
    _hs_hints.append("⚠️ 含木材 (Ch.44)")
if 52 in selected_chapters:
    _hs_hints.append("⚠️ 含棉花 (Ch.52)")
st.sidebar.caption("　".join(_hs_hints))

# --- B-3：輸出格式選擇 ---
st.sidebar.subheader("📄 輸出設定")

_format_options = {
    "auto": "自動（超過百萬列切換 CSV）",
    "excel": "強制 Excel (.xlsx)",
    "csv": "強制 CSV (.csv)"
}
_cfg_format = cfg.get("output", {}).get("format", "auto")
_format_index = list(_format_options.keys()).index(_cfg_format) if _cfg_format in _format_options else 0

output_format = st.sidebar.radio(
    "輸出檔案格式",
    options=list(_format_options.keys()),
    index=_format_index,
    format_func=lambda x: _format_options[x]
)

# ──────────── 執行按鈕 ────────────
start_button = st.sidebar.button("▶ 開始執行")

# ──────────── 主畫面 ────────────
col1, col2 = st.columns(2)

with col1:
    st.subheader("① 環境檢查")
    env_status = check_environment(st.session_state["start_year"], st.session_state["end_year"], cfg)
    all_ok = True
    for key, status in env_status.items():
        if status == "ok":
            st.write(f"✅ {key}")
        else:
            st.write(f"❌ {key} (缺失)")
            all_ok = False
            
    if not all_ok:
        st.error("環境檢查失敗，請依 README 指示補齊缺失的檔案。")

with col2:
    st.subheader("② 執行進度")
    progress_bar = st.progress(0)
    status_text = st.empty()
    download_area = st.empty()  # 預留給下載按鈕的空間

if start_button:
    if not all_ok:
        st.error("請先解決環境缺失問題！")
    elif len(selected_rcep_iso3) < 2:
        st.error("⚠️ 至少需選取 2 個 RCEP 成員國才能執行分析。")
    else:
        try:
            from utils.cache import cache_db
            from utils.baci_loader import load_country_codes, load_product_codes
            from utils.country_codes import AGR_CHAPTERS

            # === 將 GUI 選擇注入到 runtime config（不寫回 yaml 檔案） ===
            runtime_cfg = dict(cfg)  # shallow copy

            # 動態覆蓋 RCEP 成員國（將 ISO3 轉回 ISO2 放入 config 格式）
            _selected_iso2 = [ALL_COUNTRIES[iso3]["iso2"] for iso3 in selected_rcep_iso3 if iso3 in ALL_COUNTRIES]
            runtime_cfg["rcep_countries"] = {
                "asean10": [c for c in _selected_iso2 if ALL_COUNTRIES.get(next((k for k, v in ALL_COUNTRIES.items() if v["iso2"] == c), ""), {}).get("group") == "ASEAN10"],
                "others":  [c for c in _selected_iso2 if ALL_COUNTRIES.get(next((k for k, v in ALL_COUNTRIES.items() if v["iso2"] == c), ""), {}).get("group") == "RCEP5"]
            }

            # 動態覆蓋農產品 HS 章節
            runtime_cfg["agriculture_hs_chapters"] = selected_chapters
            
            # 動態覆蓋 Top_N (GUI 選項覆寫 config.yaml)
            runtime_cfg["top_n"] = top_n

            # 動態覆蓋輸出格式
            if "output" not in runtime_cfg:
                runtime_cfg["output"] = {}
            runtime_cfg["output"]["format"] = output_format

            # 同步更新 country_codes 模組的全局變數（RCEP_15_M49, AGR_CHAPTERS 等）
            import utils.country_codes as cc_mod
            _selected_m49 = {ALL_COUNTRIES[iso3]["m49"] for iso3 in selected_rcep_iso3 if iso3 in ALL_COUNTRIES}
            cc_mod.RCEP_15_M49 = _selected_m49
            cc_mod.ALL_M49 = _selected_m49 | {490}  # 加回台灣
            cc_mod.AGR_CHAPTERS = {f"{i:02d}" for i in selected_chapters}

            status_text.text("準備中：載入 BACI 元數據 (國家與各版本品項說明)...")
            metadata = {
                "countries": load_country_codes(runtime_cfg),
                "products_by_version": {
                    "HS07": load_product_codes("HS07", runtime_cfg),
                    "HS12": load_product_codes("HS12", runtime_cfg),
                    "HS17": load_product_codes("HS17", runtime_cfg)
                }
            }
            
            baci_cache = {}
            status_text.text("Stage 1: 台灣數據過濾與 Top N 計算...")
            progress_bar.progress(10)
            top_n_dict, taiwan_df = run_stage1(st.session_state["start_year"], st.session_state["end_year"], top_n, runtime_cfg, cache_db, baci_cache)
            
            status_text.text("Stage 2: BACI 數據解析...")
            progress_bar.progress(40)
            rcep_df = run_stage2(st.session_state["start_year"], st.session_state["end_year"], top_n_dict, runtime_cfg, cache_db, baci_cache)
            
            status_text.text("Stage 3: 數據清理與整合...")
            progress_bar.progress(70)
            final_df = run_stage3(rcep_df, taiwan_df, top_n_dict, st.session_state["start_year"], st.session_state["end_year"], runtime_cfg, metadata=metadata)
            
            status_text.text("Stage 4: 輸出報表...")
            progress_bar.progress(90)
            output_path = run_stage4(final_df, top_n_dict, st.session_state["start_year"], st.session_state["end_year"], runtime_cfg)
            
            progress_bar.progress(100)
            if output_path:
                status_text.text(f"✅ 執行完成！報表已儲存至 {output_path}")
                # 判斷 MIME type
                if output_path.endswith(".csv"):
                    mime_type = "text/csv"
                elif output_path.endswith(".zip"):
                    mime_type = "application/zip"
                else:
                    mime_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                
                with open(output_path, "rb") as file:
                    with download_area:
                        st.download_button(
                            label="📥 下載報表",
                            data=file,
                            file_name=os.path.basename(output_path),
                            mime=mime_type
                        )
            else:
                status_text.text("✅ 執行完成，但無有效資料可匯出。")
        except Exception as e:
            st.error(f"執行過程中發生錯誤: {e}")
            logger.exception("Pipeline Error")
