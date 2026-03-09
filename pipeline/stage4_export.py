import os
import datetime
import pandas as pd
from loguru import logger

def run_stage4(final_df: pd.DataFrame, taiwan_top10: dict, start_year: int, end_year: int, cfg: dict):
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
    
    # 修正 2：依 Reporter_Group 排除台灣資料，且限定只輸出 Top10 品項 (避免拆分過程產生的無關附帶代碼混入矩陣)
    rcep_export_df = final_df[(final_df["Reporter_Group"] != "Taiwan") & (final_df["Taiwan_Top10_Flag"] == True)]
    
    # Generate Top10 DataFrame (修正 4：補強 HS6_Description_EN 和 Value_USD)
    top10_records = []
    for yr, codes in taiwan_top10.items():
        yr_df = tw_export_df[tw_export_df["Year"] == int(yr)]
        for i, code in enumerate(codes):
            code_str = str(code).zfill(6)
            match_rows = yr_df[yr_df["HS6_Code"] == code_str]
            desc = match_rows["HS6_Description_EN"].iloc[0] if not match_rows.empty else "N/A"
            val = float(match_rows["Value_USD"].sum()) if not match_rows.empty else 0.0
            
            top10_records.append({
                "Year": int(yr), 
                "Rank": i+1, 
                "HS6_Code": code_str,
                "HS6_Description_EN": desc,
                "Value_USD": val
            })
    top10_df = pd.DataFrame(top10_records)

    annual_summary = final_df.groupby(["Year", "Reporter"])["Value_USD"].sum().reset_index()
    quality_summary = final_df.groupby(["Year", "data_quality"]).size().reset_index(name="Record_Count")

    # 要求 1 與 2：數據品質報告說明
    if cfg["output"]["include_quality_sheet"]:
        quality_summary.loc[len(quality_summary)] = [
            "⚠️ 注意事項 1",
            "本報表 RCEP 內部矩陣僅涵蓋台灣 Top10 品項，各國其他農產品出口（如澳洲小麥、牛肉）不在分析範圍內，不代表各國農產品出口全貌。此矩陣專門用於評估台灣主力農產品在 RCEP 內的競爭局勢。",
            pd.NA
        ]
        quality_summary.loc[len(quality_summary)] = [
            "⚠️ 注意事項 2",
            "2023–2024 年數據為 BACI 初步值，於輸出清單之 data_provisional 欄位標記為 True，未來版本可能有微幅修正。",
            pd.NA
        ]

    if len(final_df) > 1_000_000:
        logger.warning("[Stage 4] 長表大於一百萬行，Excel 無法容納，將輸出 CSV 格式。")
        filepath_csv = filepath.replace(".xlsx", ".csv")
        final_df.to_csv(filepath_csv, index=False, encoding="utf-8-sig")
        logger.info(f"產出檔案: {filepath_csv}")
        return filepath_csv

    logger.info(f"[Stage 4] 寫入 Excel 以產出多工作表: {filepath}")
    with pd.ExcelWriter(filepath, engine="openpyxl") as writer:
        final_df.to_excel(writer, sheet_name="長表_完整數據", index=False)
        top10_df.to_excel(writer, sheet_name="Top10_HS6_清單", index=False)
        tw_export_df.to_excel(writer, sheet_name="台灣_RCEP出口明細", index=False)
        rcep_export_df.to_excel(writer, sheet_name="RCEP內部_出口矩陣", index=False)
        annual_summary.to_excel(writer, sheet_name="年度彙整_出口總額", index=False)
        if cfg["output"]["include_quality_sheet"]:
            quality_summary.to_excel(writer, sheet_name="數據品質報告", index=False)

    logger.info(f"產出檔案成功: {filepath}")
    return filepath
