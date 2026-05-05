"""
Automated multimodal microscopy data ingestion and standardization pipeline.

This script demonstrates how heterogeneous microscopy data formats
(e.g., IBW, MRC, GWY) can be automatically detected, standardized into
sidpy-compatible HDF5/NeXus structures, enriched with metadata, and
optionally forwarded to downstream data management systems.

The implementation is designed to illustrate workflow patterns and is
portable to any environment with centralized compute and storage
resources. Infrastructure-specific parameters (paths, servers,
credentials) are provided via configuration and can be adapted.
"""

import os
import time
import glob
import h5py
import pyNSID as nsid
import SciFiReaders as sr
import requests
import getpass
import numpy as np
import json
import mrcfile
import sidpy
from SciFiReaders.readers import MRCReader, IgorIBWReader, GwyddionReader
import SciFiReaders.readers.microscopy.em.tem.mrc_reader as mrc_reader
import sidpy
import warnings
# Readers
import SciFiReaders as sr
from SciFiReaders.readers import MRCReader, IgorIBWReader, GwyddionReader
import SciFiReaders.readers.microscopy.em.tem.mrc_reader as mrc_reader


# ========= Reduce noisy warnings (but keep errors visible) =========
warnings.filterwarnings(
    "ignore",
    message=r"main_data_name should not contain the \"-\" character.*",
    category=UserWarning,
    module=r"pyNSID\.io\.hdf_io"
)
warnings.filterwarnings(
    "ignore",
    message=r"validate_h5_dimension may be removed in a future version",
    category=FutureWarning,
    module=r"pyNSID\.io\.(hdf_io|hdf_utils)"
)

# ================================
# Monkey Patch: Safe SciFiReaders MRCReader to handle 2D images of EM 
# ================================
def safe_read(self):
    """Patched version of MRCReader.read() to handle 2D MRCs safely."""
    try:
        with mrcfile.open(self.file_path, permissive=True) as m:
            data = m.data
            if data.ndim == 2:
                data = np.expand_dims(data, 0)  # ensure (1, Y, X)
            print(f"[safe_read] Loaded {self.file_path} with shape {data.shape}")

            dataset = sidpy.Dataset.from_array(data, name="Channel_000")
            dataset.units = "intensity"
            dataset.data_type = "image"
            dataset.title = os.path.basename(self.file_path)
            return {"Channel_000": dataset}
    except Exception as e:
        print(f"[safe_read] Fallback error reading {self.file_path}: {e}")
        dummy = sidpy.Dataset.from_array(np.zeros((1, 1, 1), dtype=np.float32), name="Channel_000")
        dummy.units = "a.u."
        return {"Channel_000": dummy}

mrc_reader.MRCReader.read = safe_read

# ================================
# Global Variables
# ================================
UPLOADS_ENABLED = False
TOKEN = None
nomad_url = 'http://localhost/nomad-oasis/api/v1/'# Replace with user specific NOMAD endpoint 

# -------------------------------------------------------------------
# Authentication & NOMAD API helpers
# -------------------------------------------------------------------
def check_credentials(username, password):
    return bool(username and password)

def prompt_for_credentials():
    while True:
        username = input("Enter username (or press Enter to skip): ")
        if username == "":
            return None, None
        password = getpass.getpass("Enter password: ")
        if check_credentials(username, password):
            print("Credentials accepted.")
            return username, password
        else:
            choice = input("Invalid. Try again? (y/n): ")
            if choice.strip().lower() != 'y':
                return None, None

def get_authentication_token(nomad_url, username, password):
    try:
        response = requests.get(
            nomad_url + 'auth/token',
            params=dict(username=username, password=password), timeout=10)
        token = response.json().get('access_token')
        if token:
            return token
        print('Response missing token:', response.json())
    except Exception:
        print('Error getting authentication token')
    return None

def upload_to_NOMAD(nomad_url, token, upload_files):
    if isinstance(upload_files, str):
        upload_files = [upload_files]
    results = {}
    for file_path in upload_files:
        try:
            with open(file_path, 'rb') as f:
                response = requests.post(
                    f'{nomad_url}uploads?file_name={os.path.basename(file_path)}',
                    headers={'Authorization': f'Bearer {token}', 'Accept': 'application/json'},
                    data=f, timeout=30
                )
                upload_id = response.json().get('upload_id')
                if upload_id:
                    results[file_path] = upload_id
                    print(f"[upload] Uploaded {file_path}, upload_id={upload_id}")
                else:
                    print(f"[upload] Failed for {file_path}, response={response.json()}")
        except Exception as e:
            print(f"[upload] Error with {file_path}: {e}")
    return results

def check_upload_status(nomad_url, token, upload_id):
    try:
        response = requests.get(
            nomad_url + 'uploads/' + upload_id,
            headers={'Authorization': f'Bearer {token}'}, timeout=30)
        return response.json().get('data', {}).get('last_status_message')
    except Exception:
        print('Error checking upload status:', upload_id)
    return None

def publish_upload(nomad_url, token, upload_id):
    try:
        response = requests.post(
            nomad_url + 'uploads/' + upload_id + '/action/publish',
            headers={'Authorization': f'Bearer {token}', 'Accept': 'application/json'},
            timeout=30)
        return response
    except Exception:
        print('Error publishing upload:', upload_id)
    return None

# -------------------------------------------------------------------
# Conversion
# -------------------------------------------------------------------
READER_CLASSES = {
    '.ibw': IgorIBWReader,
    '.mrc': MRCReader,
    '.gwy': GwyddionReader,
}

def convert_to_h5(file_path, metadata=None):
    ext = os.path.splitext(file_path)[1].lower()
    if ext not in READER_CLASSES:
        raise ValueError(f"No reader for extension {ext}. Supported: {list(READER_CLASSES.keys())}")

    reader_class = READER_CLASSES[ext]
    print(f"[convert] Reading {file_path} with {reader_class.__name__}")

    data_is_not_read = True
    while data_is_not_read:
        try:
            reader = reader_class(file_path)
            data = reader.read()
            data_is_not_read = False

        except PermissionError:
            time.sleep(1)

        except AssertionError as e:
            if "GWYP" in str(e) or "assert data[:4]" in str(e):
                print(f" Skipping corrupted GWY file: {file_path}")
                return None
            else:
                raise e

    if isinstance(data, list):
        data = {f"Channel_{i:03d}": d for i, d in enumerate(data)}

    h5_name = file_path.rsplit('.', 1)[0] + '.h5.nxs'

    with h5py.File(h5_name, 'w') as h5_f:
        h5_group = h5_f.create_group('Measurement_Nexus')
        def_dset = h5_group.create_dataset('definition', data="NXem")
        def_dset.attrs["url"] = "https://github.com/FAIRmat-NFDI/nexus_definitions"
        def_dset.attrs["version"] = "v2024.02"

        # attach any incoming metadata
        if metadata:
            for key, value in metadata.items():
                h5_group.attrs[key] = value

        # Add rich MRC header metadata if applicable
        if ext == ".mrc":
            try:
                with mrcfile.open(file_path, permissive=True) as m:
                    h5_group.attrs.update({
                        "Nx": int(m.header.nx),
                        "Ny": int(m.header.ny),
                        "Nz": int(m.header.nz),
                        "Mode": int(m.header.mode),
                        "Cell_X_Angstrom": float(m.header.cella.x),
                        "Cell_Y_Angstrom": float(m.header.cella.y),
                        "Cell_Z_Angstrom": float(m.header.cella.z),
                        "Min_Intensity": float(m.header.dmin),
                        "Max_Intensity": float(m.header.dmax),
                        "Mean_Intensity": float(m.header.dmean),
                        "Axis_Mapping": f"{m.header.mapc},{m.header.mapr},{m.header.maps}",
                        "Map": str(m.header.map),
                        "Machine_Stamp": str(m.header.machst),
                        "Version": int(m.header.nversion),
                        "Origin_XYZ": f"{m.header.origin.x},{m.header.origin.y},{m.header.origin.z}",
                    })
                    labels = []
                    if hasattr(m.header, "label"):
                        for l in m.header.label:
                            txt = l.decode("utf-8", errors="ignore").strip()
                            if txt:
                                labels.append(txt)
                    if labels:
                        h5_group.attrs["Labels"] = "; ".join(labels)
            except Exception as e:
                print(f"[convert][warn] Failed to extract MRC header metadata: {e}")

        # write datasets
        for key in list(data.keys()):
            h5_g = h5_group.create_group(key)
            nsid.hdf_io.write_nsid_dataset(data[key], h5_g)
            h5_g.attrs["NX_class"] = "NXdata"

            if "generic" in h5_g:
                try:
                    h5_g['generic'].copy("x", "axis_i")
                    h5_g['generic'].copy("y", "axis_j")
                    h5_g['generic'].attrs.update({
                        "signal": "generic",
                        "axes": np.array(['axis_j', 'axis_i'], dtype='object'),
                        "axis_i_indices": 0,
                        "axis_j_indices": 1,
                    })
                except Exception as e:
                    print(f"[convert][warn] AFM generic block issue: {e}")
            else:
                axis_i = h5_g.create_dataset("axis_i", data=np.arange(data[key].shape[-1]))
                axis_j = h5_g.create_dataset("axis_j", data=np.arange(data[key].shape[-2]))
                axis_i.attrs.update({"units": "pixels", "long_name": "Width"})
                axis_j.attrs.update({"units": "pixels", "long_name": "Height"})

    # ----- NEW: Success banners per file type -----
    if ext == ".ibw":
        print("---Converted IBW file to h5 successfully---")
    elif ext == ".mrc":
        print("---Converted MRC file to h5 successfully---")
    elif ext == ".gwy":
        print("---Converted GWY file to h5 successfully---")

    print(f"[convert] Converted {file_path} ? {h5_name}")
    return h5_name

# ------------------------------------------------------------
# Watcher logic
# ------------------------------------------------------------
# This loop illustrates how newly generated instrument files are detected, converted into standardized HDF5/NeXus formats,enriched with metadata, and optionally forwarded to external data management systems.
# ------------------------------------------------------------

def start_watcher(directory, metadata, credentials):
    directory = directory if directory.startswith("/home/cloud/") else "/home/cloud/" + directory
    print(f"[file_watcher] Watching: {directory}")
    print(f"[file_watcher] Metadata: {metadata}")

    global UPLOADS_ENABLED, TOKEN
    username = credentials['Username']
    password = credentials['Password']

    if username and password:
        UPLOADS_ENABLED = True
        TOKEN = get_authentication_token(nomad_url, username, password)
        while TOKEN is None:
            print('Wrong credentials. Retry.')
            TOKEN = get_authentication_token(nomad_url, username, password)
            print(f"[debug] Your NOMAD token: {TOKEN}")
    else:
        UPLOADS_ENABLED = False
        TOKEN = None
        print("Uploads disabled: missing credentials.")

    print(f"[file_watcher] Uploads enabled: {UPLOADS_ENABLED}")
    try:
        watch_folder(directory, UPLOADS_ENABLED, TOKEN, metadata)
    except KeyboardInterrupt:
        print("\n[file_watcher] Stopped.")

def watch_folder(folder_path, uploads_enabled, TOKEN, metadata):
    processed_files = set()

    while True:
        files = []
        for ext in READER_CLASSES.keys():
            files.extend(glob.glob(os.path.join(folder_path, f"*{ext}")))

        for file in files:
            if file not in processed_files:
                processed_files.add(file)
                h5_name = convert_to_h5(file, metadata=metadata)
                print(f"[file_watcher] Converted {file} ? {h5_name}")

                if uploads_enabled:
                    upload_results = upload_to_NOMAD(nomad_url, TOKEN, h5_name)
                    for f, upload_id in upload_results.items():
                        print(f"[file_watcher] Uploaded {f}, upload_id={upload_id}")
                        status = check_upload_status(nomad_url, TOKEN, upload_id)
                        print(f"[file_watcher] Status: {status}")
                        publish_upload(nomad_url, TOKEN, upload_id)
                time.sleep(0.5)

        time.sleep(2)
