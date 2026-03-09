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

@st.cache_resource
def load_config():
    with open("config.yaml", "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

cfg = load_config()

st.set_page_config(page_title="RCEP 農產品貿易分析系統 v4.0", layout="wide")

st.title("🌾 RCEP 農產品貿易分析系統 v4.0")

if "start_year" not in st.session_state:
    st.session_state["start_year"] = cfg["time_range"]["start"]
if "end_year" not in st.session_state:
    st.session_state["end_year"] = cfg["time_range"]["end"]

st.sidebar.header("⚙️ 參數設定")
start_year, end_year = st.sidebar.slider(
    "📅 時間範圍",
    min_value=2007,
    max_value=2024,
    value=(st.session_state["start_year"], st.session_state["end_year"]),
    step=1
)
st.session_state["start_year"] = start_year
st.session_state["end_year"] = end_year

top_n = st.sidebar.number_input("🔢 每年 Top N", min_value=5, max_value=20, value=cfg["top_n"], step=1)
start_button = st.sidebar.button("▶ 開始執行")

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
    
st.subheader("③ 即時日誌")
log_area = st.empty()

if start_button:
    if not all_ok:
        st.error("請先解決環境缺失問題！")
    else:
        try:
            from utils.cache import cache_db
            from utils.baci_loader import load_country_codes, load_product_codes
            
            status_text.text("準備中：載入 BACI 元數據 (國家與各版本品項說明)...")
            metadata = {
                "countries": load_country_codes(cfg),
                "products_by_version": {
                    "HS07": load_product_codes("HS07", cfg),
                    "HS12": load_product_codes("HS12", cfg),
                    "HS17": load_product_codes("HS17", cfg)
                }
            }
            
            baci_cache = {}
            status_text.text("Stage 1: 台灣數據過濾與 Top10 計算...")
            progress_bar.progress(10)
            top10_dict, taiwan_df = run_stage1(st.session_state["start_year"], st.session_state["end_year"], top_n, cfg, cache_db, baci_cache)
            
            status_text.text("Stage 2: BACI 數據解析...")
            progress_bar.progress(40)
            rcep_df = run_stage2(st.session_state["start_year"], st.session_state["end_year"], top10_dict, cfg, cache_db, baci_cache)
            
            status_text.text("Stage 3: 數據清理與整合...")
            progress_bar.progress(70)
            final_df = run_stage3(rcep_df, taiwan_df, top10_dict, st.session_state["start_year"], st.session_state["end_year"], cfg, metadata=metadata)
            
            status_text.text("Stage 4: 輸出報表...")
            progress_bar.progress(90)
            output_path = run_stage4(final_df, top10_dict, st.session_state["start_year"], st.session_state["end_year"], cfg)
            
            progress_bar.progress(100)
            if output_path:
                status_text.text(f"✅ 執行完成！報表已儲存至 {output_path}")
                with open(output_path, "rb") as file:
                    st.download_button(
                        label="📥 下載 Excel 報表",
                        data=file,
                        file_name=os.path.basename(output_path),
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
            else:
                status_text.text("✅ 執行完成，但無有效資料可匯出。")
        except Exception as e:
            st.error(f"執行過程中發生錯誤: {e}")
            logger.exception("Pipeline Error")
