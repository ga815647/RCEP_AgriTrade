import os
import glob
from loguru import logger

def get_baci_version(year: int, cfg: dict) -> str:
    router = cfg["baci"]["version_router"]
    for yr_range, version in router.items():
        start, end = map(int, yr_range.split("-"))
        if start <= year <= end:
            return version
    raise ValueError(f"年份 {year} 超出 BACI 支援範圍 (目前的設定是 2007-2024)")

def check_environment(start_year: int, end_year: int, cfg: dict) -> dict:
    """掃描所有必要檔案是否存在，回傳狀態字典 (v4.0: 支援 glob)"""
    status = {}
    baci_dir = cfg["baci"]["baci_dir"]
    pattern = cfg["baci"]["filename_pattern"]
    
    for year in range(start_year, end_year + 1):
        try:
            version = get_baci_version(year, cfg)
            glob_pat = os.path.join(baci_dir, version.lower(), 
                                    pattern.format(version=version, year=year))
            matches = glob.glob(glob_pat)
            status[f"baci_{year}"] = "ok" if matches else "missing"
        except Exception as e:
            status[f"baci_{year}"] = "error"
            logger.error(f"Error checking baci path for {year}: {e}")
            
    # Check mappings
    ref_dir = "data/reference"
    for ref_file in ["HS2017toHS2007ConversionAndCorrelationTables.xlsx", "HS2017toHS2012ConversionAndCorrelationTables.xlsx"]:
        status[f"ref_{ref_file}"] = "ok" if os.path.exists(os.path.join(ref_dir, ref_file)) else "missing"
        
    # Check BACI Metadata using glob
    hs17_dir = os.path.join(baci_dir, "hs17")
    status["meta_country_codes"] = "ok" if glob.glob(os.path.join(hs17_dir, "country_codes_V*.csv")) else "missing"
    
    for ver in ["hs07", "hs12", "hs17"]:
        ver_upper = ver.upper()
        meta_pat = os.path.join(baci_dir, ver, f"product_codes_{ver_upper}_V*.csv")
        status[f"meta_products_{ver_upper}"] = "ok" if glob.glob(meta_pat) else "missing"
        
    return status
