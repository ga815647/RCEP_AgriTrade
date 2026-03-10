import pandas as pd
from loguru import logger
from utils.cache import cache_db
from utils.baci_loader import load_baci_year
from utils.country_codes import RCEP_15_M49
from utils.hs_harmonizer import load_concordance

def run_stage2(start_year: int, end_year: int, top_n_dict: dict, cfg: dict, cache_db, baci_cache: dict) -> pd.DataFrame:
    """
    從 BACI 取出 RCEP 15 國之間（i∈RCEP_15，j∈RCEP_15）的 Top10 品項出口。
    baci_cache: 與 Stage 1 共用，避免重複 I/O。
    """
    frames = []
    concordance = load_concordance(cfg)

    for year in range(start_year, end_year + 1):
        cached = cache_db.get_baci(year)
        if cached is not None:
            frames.append(cached)
            logger.info(f"[Stage 2] {year} 從快取讀取，{len(cached)} 筆")
            continue

        try:
            if year not in baci_cache:
                baci_cache[year] = load_baci_year(year, cfg)
            df = baci_cache[year]

            top_n_hs17 = set(top_n_dict.get(str(year), []))
            
            # v4.1: 反查 top10_hs17 在該年度 BACI 版本中的所有可能舊代碼
            ver = df["baci_version"].iloc[0] if not df.empty and "baci_version" in df.columns else "HS17"
            hs_ver_mapped = {"HS07": "HS2007", "HS12": "HS2012", "HS17": "HS2017"}.get(ver, "HS2017")
            
            allowed_raw_codes = set(top_n_hs17) # 預設包含自己 (fallback)
            if hs_ver_mapped != "HS2017":
                mapping = concordance.get(hs_ver_mapped, {})
                for old_code, new_codes in mapping.items():
                    if any(nc in top_n_hs17 for nc in new_codes):
                        allowed_raw_codes.add(old_code)

            rcep_df = df[
                df["i"].isin(RCEP_15_M49) &
                df["j"].isin(RCEP_15_M49) &
                df["k"].isin(allowed_raw_codes)
            ].copy()

            # 標準化欄位
            rcep_df = rcep_df.rename(columns={"t": "Year", "i": "Reporter_M49",
                                     "j": "Partner_M49", "k": "HS6_Code_Original",
                                     "v": "Value_USD_1000"})
            rcep_df["Value_USD"]        = rcep_df["Value_USD_1000"] * 1000
            # Data Provisional
            rcep_df["data_provisional"] = (year >= 2023)
            rcep_df["data_source"]      = "baci"

            cache_db.set_baci(year, rcep_df)
            frames.append(rcep_df)
            logger.info(f"[Stage 2] {year} 完成，{len(rcep_df)} 筆")
            
        except Exception as e:
            logger.error(f"[Stage 2] {year} 處理失敗: {e}")
            raise # BACI 解析失敗為致命錯誤，由上層捕獲
        finally:
            # 讀完 Stage 1 + Stage 2 後，釋放當年記憶體
            if year in baci_cache:
                del baci_cache[year]

    if frames:
        return pd.concat(frames, ignore_index=True)
    return pd.DataFrame()
