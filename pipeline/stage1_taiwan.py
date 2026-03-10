import pandas as pd
from loguru import logger
from utils.baci_loader import load_baci_year
from utils.country_codes import TAIWAN_M49, RCEP_15_M49
from utils.hs_harmonizer import load_concordance, harmonize_to_hs2017

def run_stage1(start_year: int, end_year: int, top_n: int, cfg: dict, cache_db, baci_cache: dict) -> tuple[dict, pd.DataFrame]:
    """
    從 BACI 計算台灣（M49=490）對 RCEP 15 國農產品出口的 Top N HS6。
    baci_cache: 已讀入的年份 DataFrame 快取（{year: df}），供 Stage 2 共用。
    回傳 (top10_dict, taiwan_all_df)
    """
    top10_dict = {}
    taiwan_frames = []
    concordance = load_concordance(cfg)

    for year in range(start_year, end_year + 1):
        cached_top10 = cache_db.get_taiwan_top10(year, top_n)
        cached_df = cache_db.get_taiwan_df(year)
        if cached_top10 is not None and cached_df is not None:
            logger.info(f"[Stage 1] {year} 從快取讀取 Top {top_n} 與 DataFrame")
            top10_dict[str(year)] = cached_top10
            taiwan_frames.append(cached_df)
            continue

        try:
            # 讀入（若尚未讀，先讀；若已讀，共用）
            if year not in baci_cache:
                baci_cache[year] = load_baci_year(year, cfg)
            df = baci_cache[year]

            # 台灣出口：i=490，j∈RCEP_15
            tw_df = df[(df["i"] == TAIWAN_M49) & (df["j"].isin(RCEP_15_M49))].copy()
            
            # v4.1: 要計算準確的 Top 10，必須先執行 HS2017 代碼轉換
            tw_harmonized = []
            for _, row in tw_df.iterrows():
                row_dict = row.to_dict()
                row_dict["HS6_Code_Original"] = str(row_dict["k"]).zfill(6)
                row_dict["Value_USD"] = row_dict["v"] * 1000
                row_dict["Value_USD_1000"] = row_dict["v"]
                row_dict["baci_version"] = row_dict.get("baci_version", "HS17") 
                tw_harmonized.extend(harmonize_to_hs2017(pd.Series(row_dict), concordance))
            
            tw_h_df = pd.DataFrame(tw_harmonized)
            
            # 排除轉口品項（不參與 Top-N 排名，但保留在明細表中）
            exclude_codes = set(str(c).zfill(6) for c in cfg.get("exclude_hs6", {}).get("codes", []))
            
            if not tw_h_df.empty:
                ranking_df = tw_h_df[~tw_h_df["HS6_Code"].isin(exclude_codes)] if exclude_codes else tw_h_df
                top_items = ranking_df.groupby("HS6_Code")["Value_USD"].sum().nlargest(top_n).index.tolist()
            else:
                top_items = []
                
            top_set = set(top_items)
            
            # 修正：保留台灣「全部」農產品出口，不用 Top10 過濾
            year_df = tw_df.copy()
            
            # 欄位映射為 stage3 相容的格式
            year_df = year_df.rename(columns={"t": "year", "k": "hs6", "j": "country", "v": "value_usd"})
            year_df["value_usd"] = year_df["value_usd"] * 1000  # 千美元 → 美元
            # M49 代碼轉回 ISO3，供 stage3 使用
            def m49_to_iso3(m49):
                from utils.country_codes import ALL_COUNTRIES
                for iso3, v in ALL_COUNTRIES.items():
                    if v["m49"] == m49:
                        return iso3
                return str(m49)
            year_df["country"] = year_df["country"].apply(m49_to_iso3)

            cache_db.set_taiwan_top10(year, top_n, top_items)
            cache_db.set_taiwan_df(year, year_df)
            top10_dict[str(year)] = top_items
            taiwan_frames.append(year_df)
            logger.info(f"[Stage 1] {year} Top {top_n}：{top_items}，全部台灣出口共 {len(year_df)} 筆")
            
        except Exception as e:
            logger.error(f"[Stage 1] {year} 處理失敗: {e}")
            top10_dict[str(year)] = []
    
    taiwan_all_df = pd.concat(taiwan_frames, ignore_index=True) if taiwan_frames else pd.DataFrame()
    return top10_dict, taiwan_all_df
