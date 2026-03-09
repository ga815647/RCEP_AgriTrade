ALL_COUNTRIES = {
    "TWN": {"m49": 490, "iso2": "TW", "name_zh": "台灣",   "group": "Taiwan"},
    "BRN": {"m49":  96, "iso2": "BN", "name_zh": "汶萊",   "group": "ASEAN10"},
    "KHM": {"m49": 116, "iso2": "KH", "name_zh": "柬埔寨", "group": "ASEAN10"},
    "IDN": {"m49": 360, "iso2": "ID", "name_zh": "印尼",   "group": "ASEAN10"},
    "LAO": {"m49": 418, "iso2": "LA", "name_zh": "寮國",   "group": "ASEAN10"},
    "MYS": {"m49": 458, "iso2": "MY", "name_zh": "馬來西亞","group": "ASEAN10"},
    "MMR": {"m49": 104, "iso2": "MM", "name_zh": "緬甸",   "group": "ASEAN10"},
    "PHL": {"m49": 608, "iso2": "PH", "name_zh": "菲律賓", "group": "ASEAN10"},
    "SGP": {"m49": 702, "iso2": "SG", "name_zh": "新加坡", "group": "ASEAN10"},
    "THA": {"m49": 764, "iso2": "TH", "name_zh": "泰國",   "group": "ASEAN10"},
    "VNM": {"m49": 704, "iso2": "VN", "name_zh": "越南",   "group": "ASEAN10"},
    "CHN": {"m49": 156, "iso2": "CN", "name_zh": "中國",   "group": "RCEP5"},
    "JPN": {"m49": 392, "iso2": "JP", "name_zh": "日本",   "group": "RCEP5"},
    "KOR": {"m49": 410, "iso2": "KR", "name_zh": "韓國",   "group": "RCEP5"},
    "AUS": {"m49":  36, "iso2": "AU", "name_zh": "澳洲",   "group": "RCEP5"},
    "NZL": {"m49": 554, "iso2": "NZ", "name_zh": "紐西蘭", "group": "RCEP5"},
}

TAIWAN_M49   = 490
RCEP_15_M49  = {v["m49"] for iso3, v in ALL_COUNTRIES.items() if v["group"] != "Taiwan"}
ALL_M49      = {v["m49"] for v in ALL_COUNTRIES.values()}   # 含台灣，共 16 個
AGR_CHAPTERS = {f"{i:02d}" for i in range(1, 25)}           # '01'~'24'

# backward compatibility with earlier code (for stage 3 if needed)
RCEP_COUNTRY_MAPPING = {v["iso2"]: {"m49": v["m49"], "iso3": iso3, "name_zh": v["name_zh"]} 
                        for iso3, v in ALL_COUNTRIES.items() if v["group"] != "Taiwan"}

def get_country_info(identifier, metadata: dict = None) -> dict | None:
    res = None
    if isinstance(identifier, int) or str(identifier).isdigit():
        for iso3, v in ALL_COUNTRIES.items():
            if v["m49"] == int(identifier):
                res = {"iso2": v["iso2"], "iso3": iso3, **v}
                break
    
    if not res:
        identifier = str(identifier).upper()
        for iso3, v in ALL_COUNTRIES.items():
            if v["iso2"] == identifier or iso3 == identifier:
                res = {"iso2": v["iso2"], "iso3": iso3, **v}
                break
    
    # 若有動態 metadata 且匹配 M49，則更新名稱
    if res and metadata and "countries" in metadata:
        m49_str = int(res["m49"])
        if m49_str in metadata["countries"]:
            res["name_en_baci"] = metadata["countries"][m49_str]
            
    return res

def get_reporter_group(iso2: str, cfg: dict) -> str:
    for iso3, v in ALL_COUNTRIES.items():
        if v["iso2"] == iso2:
            return v["group"]
    return "Unknown"
