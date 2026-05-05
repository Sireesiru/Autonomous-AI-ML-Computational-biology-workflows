import os
import requests
import qrcode
import getpass

# ----------------------------
# CONFIG
# ----------------------------
API_BASE = "http://localhost/nomad-oasis/api/v1"
GUI_BASE = "http://localhost/nomad-oasis"

UPLOAD_ID = "g6EUS_grQLaeezM3kT5-GQ"
QR_OUTDIR = "qr_codes"

os.makedirs(QR_OUTDIR, exist_ok=True)

# ----------------------------
# AUTH (same logic as watcher)
# ----------------------------
def check_credentials(username, password):
    return bool(username and password)

def prompt_for_credentials():
    username = input("NOMAD username: ")
    password = getpass.getpass("NOMAD password: ")
    return username, password if check_credentials(username, password) else (None, None)

def get_authentication_token(api_base, username, password):
    resp = requests.get(
        f"{api_base}/auth/token",
        params={"username": username, "password": password},
        timeout=10
    )
    resp.raise_for_status()
    return resp.json()["access_token"]

# ----------------------------
# LOGIN
# ----------------------------
username, password = prompt_for_credentials()
token = get_authentication_token(API_BASE, username, password)

headers = {"Authorization": f"Bearer {token}"}

# ----------------------------
# QUERY UNPUBLISHED UPLOAD *ENTRIES*
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
# GENERATE QR CODES
# ----------------------------
for e in entries:
    entry_id = e["entry_id"]
    entry_name = e.get("entry_name", entry_id)

    entry_url = (
        f"{GUI_BASE}/gui/user/uploads/upload/id/"
        f"{UPLOAD_ID}/entry/id/{entry_id}"
    )

    qr = qrcode.QRCode(
        version=2,
        error_correction=qrcode.constants.ERROR_CORRECT_Q,
        box_size=10,
        border=4,
    )
    qr.add_data(entry_url)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")
    img.save(os.path.join(QR_OUTDIR, f"{entry_name}_qr.png"))

print("Done. All QR codes generated.")