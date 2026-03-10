import os
import pandas as pd
from loguru import logger
from utils.hs_harmonizer import harmonize_to_hs2017, load_concordance
from utils.country_codes import ALL_COUNTRIES, get_reporter_group, get_country_info

def run_stage3(rcep_df: pd.DataFrame, taiwan_df: pd.DataFrame, top_n_dict: dict, start_year: int, end_year: int, cfg: dict, metadata: dict = None) -> pd.DataFrame:
    logger.info("[Stage 3] 載入 HS 對照表...")
    concordance = load_concordance(cfg)
    
    logger.info("[Stage 3] 處理 RCEP 內部貿易數據 (HS轉換)...")
    if not rcep_df.empty:
        harmonized_records = []
        for _, row in rcep_df.iterrows():
            harmonized_records.extend(harmonize_to_hs2017(row, concordance))
        rcep_mapped_df = pd.DataFrame(harmonized_records)
        
        def apply_country_names(m49_code):
            info = get_country_info(m49_code, metadata)
            if info:
                # 優先用 BACI 名稱，次之繁中名，最後 ISO3
                return info.get("name_en_baci") or info.get("name_zh") or info.get("iso3")
            return f"M49:{m49_code}"

        def get_iso3(m49_code):
            info = get_country_info(m49_code)
            return info["iso3"] if info else "Unknown"

        rcep_mapped_df["Reporter"]      = rcep_mapped_df["Reporter_M49"].apply(apply_country_names)
        rcep_mapped_df["Reporter_ISO3"] = rcep_mapped_df["Reporter_M49"].apply(get_iso3)
        rcep_mapped_df["Reporter_Group"]= rcep_mapped_df["Reporter_ISO3"].apply(lambda x: get_reporter_group(get_country_info(x)["iso2"], cfg) if get_country_info(x) else "Unknown")
        
        rcep_mapped_df["Partner"]      = rcep_mapped_df["Partner_M49"].apply(apply_country_names)
        rcep_mapped_df["Partner_ISO3"] = rcep_mapped_df["Partner_M49"].apply(get_iso3)
    else:
        rcep_mapped_df = pd.DataFrame()

    logger.info("[Stage 3] 整合並轉換台灣貿易數據...")
    if not taiwan_df.empty:
        # 重大修正：台灣匯出資料也必須經過 HS 版本轉換 (v4.0)
        tw_harmonized = []
        for _, row in taiwan_df.iterrows():
            # 需要補齊一些基底欄位讓 harmonizer 讀取
            row_dict = row.to_dict()
            row_dict["HS6_Code_Original"] = str(row_dict["hs6"]).zfill(6)
            row_dict["Value_USD"] = row_dict["value_usd"]
            row_dict["Value_USD_1000"] = row_dict["Value_USD"] / 1000.0
            row_dict["baci_version"] = row_dict.get("baci_version", "HS17") 
            tw_harmonized.extend(harmonize_to_hs2017(pd.Series(row_dict), concordance))
            
        tw = pd.DataFrame(tw_harmonized)
        tw["Year"] = tw["year"]
        
        tw_info = get_country_info(490, metadata)
        tw_name = "Taiwan"
        if tw_info:
            tw_name = tw_info.get("name_en_baci") or tw_info.get("name_zh") or "Taiwan"

        tw["Reporter"] = tw_name
        tw["Reporter_ISO3"] = "TWN"
        tw["Reporter_M49"] = 490
        tw["Reporter_Group"] = "Taiwan"
        
        def partner_to_name(iso3):
            info = get_country_info(iso3, metadata)
            if info:
                return info.get("name_en_baci") or info.get("name_zh") or info.get("iso3")
            return iso3

        tw["Partner"] = tw["country"].apply(partner_to_name)
        tw["Partner_ISO3"] = tw["country"]
        
        tw["data_source"] = "baci"
        # data_provisional 根據年份判定 (BACI 的初步值通常是最新兩年，但 Stage2 應該有些判斷了？其實直接設False，因為稍後會由 stage4 或者直接算)
        tw["data_provisional"] = tw["Year"].apply(lambda y: int(y) >= 2023)
        
        final_df = pd.concat([rcep_mapped_df, tw], ignore_index=True)
    else:
        final_df = rcep_mapped_df

    if final_df.empty:
        return final_df

    final_df["HS_Chapter"] = final_df["HS6_Code"].str[:2].astype(str).str.zfill(2)
    
    # 動態補入商品說明 (v4.0: 支援分版本說明與 fallback 至基準 HS17)
    if metadata and "products_by_version" in metadata:
        def get_hs_desc(row):
            ver = row.get("baci_version", "HS17") 
            code = row["HS6_Code"]
            ver_dict = metadata["products_by_version"].get(ver, {})
            desc = ver_dict.get(code)
            
            # 如果本版找不到，去 HS17 找 (因為所有代碼已在上方 harmonization 轉為 2017 基準)
            if not desc or pd.isna(desc):
                desc = metadata["products_by_version"].get("HS17", {}).get(code, "N/A")
            return desc
            
        final_df["HS6_Description_EN"] = final_df.apply(get_hs_desc, axis=1)
    else:
        final_df["HS6_Description_EN"] = "BACI Descriptions Not Loaded"

    def determine_quality(row):
        if row["Partner_ISO3"] in ["BRN", "LAO", "MMR"]:
            return "sparse"
        elif row["data_provisional"]:
            return "provisional"
        return "verified"

    final_df["data_quality"] = final_df.apply(determine_quality, axis=1)

    # v4.1: 所有記錄 (無論台灣或 RCEP)，皆在轉換為最終 HS2017 後
    # 統一對照 top_n_dict 來標記是否屬於當年的 Top N 品項
    def is_taiwan_top_n(row):
        yr = str(int(row["Year"]))
        code = row["HS6_Code"]
        return yr in top_n_dict and code in top_n_dict[yr]
        
    final_df["Taiwan_TopN_Flag"] = final_df.apply(is_taiwan_top_n, axis=1)

    REQUIRED_COLUMNS = [
        "Year", "HS6_Code", "HS6_Code_Original", "HS6_Description_EN",
        "HS_Chapter", "Reporter", "Reporter_ISO3", "Reporter_Group",
        "Partner", "Partner_ISO3",
        "Value_USD", "Value_USD_1000",
        "data_source", "baci_version", "data_provisional",
        "hs_converted", "hs_split", "hs_mapped",
        "data_quality", "Taiwan_TopN_Flag"
    ]
    for col in REQUIRED_COLUMNS:
        if col not in final_df.columns:
            final_df[col] = None

    return final_df[REQUIRED_COLUMNS]
