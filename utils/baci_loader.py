import os
import glob
import pandas as pd
from loguru import logger
from utils.country_codes import ALL_M49, AGR_CHAPTERS

def get_baci_version(year: int, cfg: dict) -> str:
    router = cfg["baci"]["version_router"]
    # 新格式 (list of dicts) — v4.2+
    if isinstance(router, list):
        for entry in router:
            ys = entry["year_start"]
            ye = entry["year_end"] if entry["year_end"] is not None else cfg["time_range"]["end"]
            if ys <= year <= ye:
                return entry["hs_version"]
    # 舊格式 (dict: "2007-2011" -> "HS07") — 向下相容
    elif isinstance(router, dict):
        for yr_range, version in router.items():
            start, end = map(int, yr_range.split("-"))
            if start <= year <= end:
                return version
    raise ValueError(f"年份 {year} 超出 BACI 支援範圍 (請檢查 config.yaml 的 version_router)")

def build_baci_path(year: int, cfg: dict) -> str:
    """用 glob 匹配實際檔案，不依賴硬編碼版本號 (v4.0)"""
    ver      = get_baci_version(year, cfg)
    baci_dir = cfg["baci"]["baci_dir"]
    pattern  = cfg["baci"]["filename_pattern"]
    
    glob_pat = os.path.join(baci_dir, ver.lower(), 
                            pattern.format(version=ver, year=year))
    matches = glob.glob(glob_pat)
    
    if not matches:
        raise FileNotFoundError(
            f"找不到 BACI {ver} {year} 年檔案（已嘗試搜尋：{glob_pat}）"
        )
    return matches[0]

def load_country_codes(cfg: dict) -> dict:
    """從 hs17 目錄讀取 country_codes_V*.csv (全局一份)"""
    baci_dir = cfg["baci"]["baci_dir"]
    hs17_dir = os.path.join(baci_dir, "hs17")
    matches = glob.glob(os.path.join(hs17_dir, "country_codes_V*.csv"))
    
    if not matches:
        logger.warning("找不到 country_codes_V*.csv")
        return {}
        
    try:
        df = pd.read_csv(matches[0], encoding="utf-8")
        # 欄位：country_code, country_name, country_iso2, country_iso3
        return df.set_index("country_code")["country_name"].to_dict()
    except Exception as e:
        logger.error(f"Error loading country codes: {e}")
        return {}

def load_product_codes(baci_version: str, cfg: dict) -> dict:
    """從對應版本目錄讀取 product_codes_{ver}_V*.csv (版本專屬)"""
    baci_dir = cfg["baci"]["baci_dir"]
    ver_dir  = os.path.join(baci_dir, baci_version.lower())
    # 範例：product_codes_HS17_V202601.csv
    pattern = f"product_codes_{baci_version}_V*.csv"
    matches = glob.glob(os.path.join(ver_dir, pattern))
    
    if not matches:
        logger.warning(f"找不到 {baci_version} 的 product codes")
        return {}
        
    try:
        df = pd.read_csv(matches[0], encoding="utf-8", dtype={"code": str})
        df["code"] = df["code"].str.zfill(6)
        return df.set_index("code")["description"].to_dict()
    except Exception as e:
        logger.error(f"Error loading product codes for {baci_version}: {e}")
        return {}

def load_baci_year(year: int, cfg: dict) -> pd.DataFrame:
    """讀入單一年份 BACI CSV，保留 RCEP+台灣 相關行，農產品（HS01-24）"""
    path = build_baci_path(year, cfg)
    ver = get_baci_version(year, cfg)
    
    df = pd.read_csv(path, dtype={"k": str})
    df = df[df["i"].isin(ALL_M49) | df["j"].isin(ALL_M49)]   # 初步過濾，含台灣
    df["k"] = df["k"].str.zfill(6)
    df = df[df["k"].str[:2].isin(AGR_CHAPTERS)]               # 農產品
    df["baci_version"] = ver
    logger.info(f"[BACI] {year} 讀入，過濾後 {len(df):,} 筆 (路徑: {os.path.basename(path)})")
    return df
