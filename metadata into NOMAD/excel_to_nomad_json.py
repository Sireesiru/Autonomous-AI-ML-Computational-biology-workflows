import pandas as pd
import json
import os
from datetime import datetime

# ============================================================
# CONFIG
# ============================================================

EXCEL_FILE = "BRaVE_Biological_Sample_Catalog_Sirisha.xlsx"
OUTPUT_FOLDER = "nomad_json_entries"

os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# ------------------------------------------------------------
# Column Mappings (EXACTLY matching your schema quantities)
# ------------------------------------------------------------

COLUMN_MAP = {
    # GENERAL
    "Name of Preparer": "preparer",
    "Date prepared": "date_prepared",
    "Sample": "sample_name",

    # CULTURE INFORMATION
    "Species": "species",
    "Medium": "medium",
    "Temp. (°C)": "temperature",
    "Culture Details": "culture_details",

    # PROTOCOL DETAILS
    "Biofilm?": "biofilm",
    "OD600": "od600",
    "Substrate": "substrate",
    "Replicates?": "replicates",
    "Vol. cells added": "volume_cells_added",
    "Incubation Temp. (°C)": "incubation_temp",
    "Medium Replaced?": "medium_replaced",
    "Incubation time": "incubation_time",
    "Washing": "washing",
    "Fixed?": "fixed",
    "Stains?": "stains",
    "Timecourse?": "timecourse",
    "ELN Link": "eln_link",

    # IMAGING #1
    "Type of Imaging": "imaging_1.imaging_type",
    "Date Imaged": "imaging_1.imaging_date",
    "Imaged By": "imaging_1.imaged_by",
    "Key Takeaways": "imaging_1.key_takeaways",
    "Image Data            (Link to folder)": "imaging_1.image_data_link",

    # IMAGING #2
    "Type of Imaging (#2)": "imaging_2.imaging_type",
    "Date Imaged (#2)": "imaging_2.imaging_date",
    "Imaged By (#2)": "imaging_2.imaged_by",
    "Key Takeaways (#2)": "imaging_2.key_takeaways",
    "Image Data (Link to folder) (#2)": "imaging_2.image_data_link",

    # IMAGING #3
    "Type of Imaging (#3)": "imaging_3.imaging_type",
    "Date Imaged (#3)": "imaging_3.imaging_date",
    "Imaged By (#3)": "imaging_3.imaged_by",
    "Key Takeaways (#3)": "imaging_3.key_takeaways",
    "Image Data (Link to folder) (#3)": "imaging_3.image_data_link",
}

# ============================================================
# Helper: assign nested imaging values
# ============================================================

def assign_nested(dictionary, nested_key, value):
    """Handle assignments such as imaging_1.imaging_type"""
    if "." not in nested_key:
        dictionary[nested_key] = value
        return

    section, key = nested_key.split(".", 1)

    if section not in dictionary:
        dictionary[section] = {}

    dictionary[section][key] = value


# ============================================================
# MAIN
# ============================================================

df = pd.read_excel(EXCEL_FILE)

for idx, row in df.iterrows():

    raw_sample_name = row.get("Sample")
    if pd.isna(raw_sample_name) or str(raw_sample_name).strip() == "":
        continue

    # Clean sample name for filenames
    entry_name = raw_sample_name.replace("/", "_").replace(" ", "_")

    # ======================================================
    # Build JSON Data Section
    # ======================================================

    data_section = {
        "m_def": "BraveSampleELN",
    }

    for col, schema_key in COLUMN_MAP.items():
        if col not in row:
            continue

        value = row[col]

        # Convert NaN or EMPTY to None (will show as blank fields)
        if pd.isna(value) or value == "NONE" or value == "":
            value = None

        # Convert Excel datetimes
        if isinstance(value, (pd.Timestamp, datetime)):
            value = value.isoformat()

        # Fill into JSON
        assign_nested(data_section, schema_key, value)

    # ======================================================
    # Build JSON Metadata
    # ======================================================

    archive = {
        "data": data_section,
        "metadata": {
            "entry_name": entry_name,
            "mainfile": f"{entry_name}.archive.json"
        }
    }

    # ======================================================
    # Save JSON
    # ======================================================

    output_path = os.path.join(OUTPUT_FOLDER, f"{entry_name}.archive.json")
    with open(output_path, "w") as f:
        json.dump(archive, f, indent=2)

    print(f" Created: {output_path}")
print("\n All entries generated successfully")
