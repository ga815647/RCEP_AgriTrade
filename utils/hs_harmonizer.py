import os
import pandas as pd

HS_VERSION_MAP = {"HS07": "HS2007", "HS12": "HS2012", "HS17": "HS2017"}

def load_concordance(cfg: dict = None) -> dict:
    """載入版本對照表，結構：{source_version: {old_hs6: [new_hs6, ...]}}"""
    concordance = {}
    ref_dir = "data/reference"
    for version, source in [("HS2007", "HS2017toHS2007ConversionAndCorrelationTables.xlsx"),
                             ("HS2012", "HS2017toHS2012ConversionAndCorrelationTables.xlsx")]:
        path = os.path.join(ref_dir, source)
        if os.path.exists(path):
            try:
                df = pd.read_excel(path, dtype=str)
                old_yr = version[-4:]  # "2007" or "2012"
                
                # Find columns
                col_2017 = next(c for c in df.columns if "2017" in str(c))
                col_old = next(c for c in df.columns if old_yr in str(c))
                
                df = df.rename(columns={col_old: 'old', col_2017: 'new'})
                df = df[['old', 'new']].dropna()
                
                # Cleanup and pad to 6 digits
                # replace('.0', '') in case pandas read some strings as float strings before
                df['old'] = df['old'].str.replace(r'\.0$', '', regex=True).str.zfill(6)
                df['new'] = df['new'].str.replace(r'\.0$', '', regex=True).str.zfill(6)
                
                # Reverse mapping: group by old, create list of news
                concordance[version] = df.groupby("old")["new"].apply(lambda x: list(set(x))).to_dict()
            except Exception as e:
                print(f"Error loading concordance for {version}: {e}")
    return concordance

def harmonize_to_hs2017(row: pd.Series, concordance: dict) -> list[dict]:
    version  = HS_VERSION_MAP.get(row["baci_version"], "HS2017")
    hs6_orig = str(row["HS6_Code_Original"]).zfill(6)
    
    if version == "HS2017":
        return [{**row.to_dict(), "HS6_Code": hs6_orig,
                 "hs_converted": False, "hs_split": False, "hs_mapped": True,
                 "weight": 1.0}]

    mapping = concordance.get(version, {}).get(hs6_orig)
    if not mapping:
        return [{**row.to_dict(), "HS6_Code": hs6_orig,
                 "hs_converted": True, "hs_split": False, "hs_mapped": False,
                 "weight": 1.0}]

    n = len(mapping)
    result = []
    for new_code in mapping:
        r = row.to_dict()
        r.update({"HS6_Code": str(new_code).zfill(6), "hs_converted": True,
                  "hs_split": (n > 1), "hs_mapped": True,
                  "Value_USD": row["Value_USD"] / n,
                  "Value_USD_1000": row["Value_USD_1000"] / n,
                  "weight": 1.0 / n})
        result.append(r)
    return result
