                                ######## Convert Excel to yaml files#######
import pandas as pd
import yaml
import os
from datetime import datetime

# -----------------------------
# USER INPUTS
# -----------------------------
EXCEL_FILE = "BRaVE_Biological_Sample_Catalog_Sirisha.xlsx"  
OUTPUT_DIR = "nomad_yaml_outputs"
#SCHEMA_REF = "braveschemasecond.archive.yaml#Section_one"
SCHEMA_REF = "../upload/raw/braveschemasecond.archive.yaml#/definitions/sections/Section_one"

os.makedirs(OUTPUT_DIR, exist_ok=True)

# -----------------------------
# Helper: clean cell values
# -----------------------------
def clean_value(val):
    if pd.isna(val):
        return None
    if isinstance(val, pd.Timestamp):
        return val.isoformat()
    if isinstance(val, datetime):
        return val.isoformat()
    return val

# -----------------------------
# Read Excel (omit first row)
# -----------------------------
df = pd.read_excel(EXCEL_FILE, header=1)
display(df)

## -----------------------------
## Iterate rows → YAML
## -----------------------------
for idx, row in df.iterrows():
    sample_name = row["sample_name"]
    if pd.isna(sample_name):
        print(f"Skipping row {idx+2}: sample_name missing")
        continue

    yaml_dict = {
        "data": {
            "m_def": SCHEMA_REF
        }
    }

    # Add all schema quantities
    for col in df.columns:
        value = clean_value(row[col])
        if value is not None:
            yaml_dict["data"][col] = value

    # File name: sample_name.archive.yaml
    safe_sample_name = str(sample_name).replace(" ", "_")
    output_path = os.path.join(
        OUTPUT_DIR, f"{safe_sample_name}.archive.yaml"
    )

    with open(output_path, "w", encoding="utf-8") as f:
        yaml.dump(
            yaml_dict,
            f,
            sort_keys=False,
            allow_unicode=True
        )
    print(f" Written: {output_path}")
print("Conversion complete")