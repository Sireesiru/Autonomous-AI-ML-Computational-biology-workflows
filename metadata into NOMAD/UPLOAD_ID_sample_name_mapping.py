import os
import requests
import getpass

# ----------------------------
# CONFIG
# ----------------------------
API_BASE = "http://localhost/nomad-oasis/api/v1"
UPLOAD_ID = "g6EUS_grQLaeezM3kT5-GQ"

OUTFILE = "entry_id_to_sample_name.txt"

# ----------------------------
# AUTH (same as watcher)
# ----------------------------
def prompt_for_credentials():
    username = input("NOMAD username: ")
    password = getpass.getpass("NOMAD password: ")
    return username, password

def get_token(api_base, username, password):
    r = requests.get(
        f"{api_base}/auth/token",
        params={"username": username, "password": password},
        timeout=10
    )
    r.raise_for_status()
    return r.json()["access_token"]

# ----------------------------
# LOGIN
# ----------------------------
username, password = prompt_for_credentials()
token = get_token(API_BASE, username, password)

headers = {"Authorization": f"Bearer {token}"}

# ----------------------------
# GET ALL ENTRIES IN UPLOAD
# ----------------------------
resp = requests.get(
    f"{API_BASE}/uploads/{UPLOAD_ID}/entries",
    headers=headers,
    params={"page_size": 1000}
)
resp.raise_for_status()

entries = resp.json()["data"]
print(f"Found {len(entries)} entries")

# ----------------------------
# WRITE MAPPING FILE
# ----------------------------
with open(OUTFILE, "w") as f:
    f.write("sample_name\tentry_id\n")
    for e in entries:
        entry_id = e["entry_id"]

        # derive sample_name from mainfile
        mainfile = os.path.basename(e["mainfile"])
        sample_name = mainfile.replace(".archive.yaml", "")

        f.write(f"{sample_name}\t{entry_id}\n")

print(f"Mapping written to: {OUTFILE}")
