import pandas as pd
from loguru import logger
from utils.cache import cache_db
from utils.baci_loader import load_baci_year
import utils.country_codes as cc
from utils.hs_harmonizer import load_concordance
from pipeline.stage1_taiwan import get_config_hash

def run_stage2(start_year: int, end_year: int, top_n_dict: dict, cfg: dict, cache_db, baci_cache: dict) -> pd.DataFrame:
    """
    從 BACI 取出 RCEP 15 國之間（i∈RCEP_15，j∈RCEP_15）的 Top N 品項出口。
    baci_cache: 與 Stage 1 共用，避免重複 I/O。
    """
    frames = []
    concordance = load_concordance(cfg)
    config_hash = get_config_hash(cfg)
    top_n = cfg.get("top_n", 10)

    for year in range(start_year, end_year + 1):
        cached = cache_db.get_baci(year, top_n, config_hash)
        if cached is not None:
            frames.append(cached)
            logger.info(f"[Stage 2] {year} 從快取讀取，{len(cached)} 筆")
            continue

        try:
            if year not in baci_cache:
                baci_cache[year] = load_baci_year(year, cfg)
            df = baci_cache[year]

            rcep_df = df[
                df["i"].isin(cc.RCEP_15_M49) &
                (df["j"].isin(cc.RCEP_15_M49) | (df["j"] == cc.TAIWAN_M49))
            ].copy()

            # 標準化欄位
            rcep_df = rcep_df.rename(columns={"t": "Year", "i": "Reporter_M49",
                                     "j": "Partner_M49", "k": "HS6_Code_Original",
                                     "v": "Value_USD_1000"})
            rcep_df["Value_USD"]        = rcep_df["Value_USD_1000"] * 1000
            # Data Provisional
            rcep_df["data_provisional"] = (year >= 2023)
            rcep_df["data_source"]      = "baci"

            cache_db.set_baci(year, top_n, config_hash, rcep_df)
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
