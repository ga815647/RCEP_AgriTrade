import os
import datetime
import zipfile
import io
import pandas as pd
from loguru import logger

def run_stage4(final_df: pd.DataFrame, top_n_dict: dict, start_year: int, end_year: int, cfg: dict):
    if final_df.empty:
        logger.warning("[Stage 4] 無任何資料可供輸出，跳過 Excel 生成")
        return None
        
    out_dir = cfg["output"]["output_dir"]
    os.makedirs(out_dir, exist_ok=True)
    
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"RCEP_AgriTrade_{start_year}_{end_year}_{timestamp}.xlsx"
    filepath = os.path.join(out_dir, filename)
    
    # 修正 3：強制 HS6_Code 與 HS6_Code_Original 為文字型態並補齊 6 碼
    if "HS6_Code" in final_df.columns:
        final_df["HS6_Code"] = final_df["HS6_Code"].astype(str).str.zfill(6)
    if "HS6_Code_Original" in final_df.columns:
        final_df["HS6_Code_Original"] = final_df["HS6_Code_Original"].astype(str).str.zfill(6)

    # 修正 1：依 Reporter_Group 過濾台灣資料
    tw_export_df = final_df[final_df["Reporter_Group"] == "Taiwan"]
    
    # 修正 2：依 Reporter_Group 排除台灣資料，再區分 RCEP->RCEP 和 RCEP->Taiwan
    rcep_export_df = final_df[(final_df["Reporter_Group"] != "Taiwan") & (final_df["Partner_ISO3"] != "TWN")]
    
    # 新增：RCEP 對台灣的出口（即台灣自 RCEP 的進口）
    rcep_to_tw_df = final_df[(final_df["Reporter_Group"] != "Taiwan") & (final_df["Partner_ISO3"] == "TWN")]
    custom_import_hs6 = [str(c).zfill(6) for c in cfg.get("custom_import_hs6", [])]
    if custom_import_hs6:
        rcep_to_tw_custom_df = rcep_to_tw_df[rcep_to_tw_df["HS6_Code"].isin(custom_import_hs6)]
    else:
        rcep_to_tw_custom_df = rcep_to_tw_df
    
    # Generate Top N DataFrame (修正 4：補強 HS6_Description_EN 和 Value_USD)
    top_n_records = []
    for yr, codes in top_n_dict.items():
        yr_df = tw_export_df[tw_export_df["Year"] == int(yr)]
        for i, code in enumerate(codes):
            code_str = str(code).zfill(6)
            match_rows = yr_df[yr_df["HS6_Code"] == code_str]
            desc = match_rows["HS6_Description_EN"].iloc[0] if not match_rows.empty else "N/A"
            val = float(match_rows["Value_USD"].sum()) if not match_rows.empty else 0.0
            
            top_n_records.append({
                "Year": int(yr), 
                "Rank": i+1, 
                "HS6_Code": code_str,
                "HS6_Description_EN": desc,
                "Value_USD": val
            })
    top_n_df = pd.DataFrame(top_n_records)

    # Generate Top N DataFrame for RCEP Internal
    rcep_top_n_records = []
    # top_n is in top_n_dict but we might not have a dict for RCEP top N, so we calculate it here
    top_n_val = cfg.get("top_n", 10)
    for yr in rcep_export_df["Year"].unique():
        yr_df = rcep_export_df[rcep_export_df["Year"] == yr]
        # Calculate Top N HS6 codes for this year in RCEP
        top_codes = yr_df.groupby("HS6_Code")["Value_USD"].sum().nlargest(top_n_val).index.tolist()
        
        for i, code in enumerate(top_codes):
            code_str = str(code).zfill(6)
            match_rows = yr_df[yr_df["HS6_Code"] == code_str]
            desc = match_rows["HS6_Description_EN"].iloc[0] if not match_rows.empty else "N/A"
            val = float(match_rows["Value_USD"].sum()) if not match_rows.empty else 0.0
            
            rcep_top_n_records.append({
                "Year": int(yr), 
                "Rank": i+1, 
                "HS6_Code": code_str,
                "HS6_Description_EN": desc,
                "Value_USD": val
            })
    rcep_top_n_df = pd.DataFrame(rcep_top_n_records)

    annual_summary = final_df.groupby(["Year", "Reporter"])["Value_USD"].sum().reset_index()
    quality_summary = final_df.groupby(["Year", "data_quality"]).size().reset_index(name="Record_Count")

    # 要求 1 與 2：數據品質報告說明
    if cfg["output"]["include_quality_sheet"]:
        quality_summary.loc[len(quality_summary)] = [
            "⚠️ 注意事項 1",
            "本報表 RCEP 內部矩陣涵蓋所有 RCEP 間農產品貿易資料。此矩陣用於評估區域內農產品貿易流向與競爭局勢。",
            pd.NA
        ]
        quality_summary.loc[len(quality_summary)] = [
            "⚠️ 注意事項 2",
            "2023–2024 年數據為 BACI 初步值，於輸出清單之 data_provisional 欄位標記為 True，未來版本可能有微幅修正。",
            pd.NA
        ]
    # 輸出格式判定
    out_format = cfg.get("output", {}).get("format", "auto")
    row_limit = cfg.get("output", {}).get("excel_row_limit", 1_000_000)

    top_n = cfg.get("top_n", 10)
    sheet_name_tw_top = f"台灣出口_Top{top_n}_HS6_清單"
    sheet_name_rcep_top = f"RCEP內部_Top{top_n}_HS6_清單"

    # 定義輸出的工作表順序
    sheets = [
        (annual_summary, "年度彙整_出口總額"),
        (top_n_df, sheet_name_tw_top),
        (tw_export_df, "台灣_RCEP出口明細"),
        (rcep_to_tw_custom_df, "RCEP對台灣自選項目進口明細"),
        (rcep_top_n_df, sheet_name_rcep_top),
        (rcep_export_df, "RCEP內部_出口矩陣"),
        (final_df, "長表_完整數據")
    ]
    if cfg["output"]["include_quality_sheet"]:
        sheets.append((quality_summary, "數據品質報告"))

    use_csv = False
    if out_format == "csv":
        use_csv = True
    elif out_format == "auto" and len(final_df) > row_limit:
        logger.warning(f"[Stage 4] 長表 {len(final_df):,} 行，超過門檻 {row_limit:,}，自動切換 CSV。")
        use_csv = True

    if use_csv:
        filepath_zip = filepath.replace(".xlsx", ".zip")
        logger.info(f"[Stage 4] 正在將多個工作表壓縮為 CSV ZIP: {filepath_zip}")
        with zipfile.ZipFile(filepath_zip, 'w', zipfile.ZIP_DEFLATED) as zf:
            for df, name in sheets:
                # 取得 CSV 字串
                csv_str = df.to_csv(index=False)
                # 為確保 Excel 繁體中文開啟不亂碼，手動加上 UTF-8 BOM (utf-8-sig)
                csv_bytes = "\ufeff".encode("utf-8") + csv_str.encode("utf-8")
                zf.writestr(f"{name}.csv", csv_bytes)
        
        logger.info(f"[Stage 4] 產出檔案成功: {filepath_zip}")
        return filepath_zip

    logger.info(f"[Stage 4] 寫入 Excel 以產出多工作表: {filepath}")
    
    with pd.ExcelWriter(filepath, engine="openpyxl") as writer:
        for df, name in sheets:
            df.to_excel(writer, sheet_name=name, index=False)

    logger.info(f"產出檔案成功: {filepath}")
    return filepath
