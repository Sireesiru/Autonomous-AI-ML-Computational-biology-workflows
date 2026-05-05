# -*- coding: utf-8 -*-
"""
EM Thickness Dash (PNG pipeline)
- Scans a folder of PNGs converted from .h5/.nxs
- Loads YOLO .pt (classes: 0=IM, 1=OM)
- Computes shortest OM?IM distances, pole/side axes (PCA with circular override)
- Renders overlay; shows per-point, per-cell, and target-angle tables
- Exports CSVs

Run:
  python app_em_png.py

Config knobs are below (MODEL_PATH, DEFAULT_IMAGES_DIR, NM_PER_PX).
"""
import os, io, glob
import numpy as np
import pandas as pd
import cv2
import scipy.spatial
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from pathlib import Path
from ultralytics import YOLO
from typing import Optional

from dash import Dash, html, dcc, Input, Output, State, dash_table

# =========================
# CONFIG
# =========================
MODEL_PATH = "/home/cloud/microflow_sidpy_nomad_server/best_thickness.pt"  # YOLO model in current working directory
DEFAULT_IMAGES_DIR = "/home/cloud/afm_images/EM/pngs"  # folder with converted PNGs
DEFAULT_OUTPUT_DIR = "/home/cloud/afm_images/EM/outputs"  # where overlay + CSVs will be saved
ALLOWED_EXT = (".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp")
NM_PER_PX = 0.8986  # pixel size; expose in UI as well

# =========================
# Utilities
# =========================

def pca_axes(points: np.ndarray) -> np.ndarray:
    pts = points - points.mean(axis=0)
    cov = np.cov(pts.T)
    eigvals, eigvecs = np.linalg.eigh(cov)
    order = np.argsort(eigvals)[::-1]
    eigvecs = eigvecs[:, order]
    return eigvecs  # [0] major, [1] minor

def fig_to_base64(fig, save_path: Optional[str] = None) -> str:
    # Save to disk first (if requested), then buffer for UI
    if save_path:
        Path(save_path).parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(save_path, dpi=150, bbox_inches="tight")
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    import base64
    return "data:image/png;base64," + base64.b64encode(buf.read()).decode("utf-8")


def list_images(folder: str):
    p = Path(folder)
    if not p.is_dir():
        return []
    files = sorted(str(f) for f in p.iterdir() if f.suffix.lower() in ALLOWED_EXT)
    return files


def run_yolo_on_image(model: YOLO, image_rgb: np.ndarray, conf: float):
    res = model(image_rgb, conf=conf, verbose=False)[0]
    img_h, img_w = image_rgb.shape[:2]

    masks = []
    if res.masks is not None:
        masks = res.masks.data.cpu().numpy()
    class_ids = res.boxes.cls.cpu().numpy().astype(int) if res.boxes is not None else []

    om_masks, im_masks = [], []
    for i, mask in enumerate(masks):
        resized = cv2.resize(mask, (img_w, img_h), interpolation=cv2.INTER_NEAREST)
        binary = (resized > 0.5).astype(np.uint8) * 255
        if class_ids[i] == 1:   # OM
            om_masks.append(binary)
        elif class_ids[i] == 0: # IM
            im_masks.append(binary)
    return om_masks, im_masks

def process_and_draw_all(om_masks, im_masks, image_rgb, nm_per_px: float, N: int = 3000, save_overlay_path: Optional[str] = None):
#def process_and_draw_all(om_masks, im_masks, image_rgb, nm_per_px: float, N: int = 3000, save_overlay_path: str | None = None):
    fig, ax = plt.subplots(figsize=(6, 6))
    ax.imshow(image_rgb)
    ax.axis('off')
    ax.set_title("All Bacteria Membrane Thickness (Shortest OM to IM distances)", pad=10)

    all_dfs = []
    metrics_list = []
    angles_dfs = []
    used_ims = set()
    target_angles = [0, 36, 72, 108, 144, 180, 216, 252, 288, 324]

    for bid, om_mask_bin in enumerate(om_masks, start=1):
        # match OM?IM by overlap once per IM
        best_overlap, best_im_idx = 0, None
        for j, im_mask_bin in enumerate(im_masks):
            if j in used_ims:
                continue
            overlap = np.sum((om_mask_bin > 0) & (im_mask_bin > 0))
            if overlap > best_overlap:
                best_overlap, best_im_idx = overlap, j
        if best_im_idx is None:
            continue
        used_ims.add(best_im_idx)

        # contours
        cnts_om = cv2.findContours(om_mask_bin, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)[0]
        cnts_im = cv2.findContours(im_masks[best_im_idx], cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)[0]
        if len(cnts_om) == 0 or len(cnts_im) == 0:
            continue
        om_contour = max(cnts_om, key=cv2.contourArea).reshape(-1, 2).astype(np.float32)
        im_contour = max(cnts_im, key=cv2.contourArea).reshape(-1, 2).astype(np.float32)
        
        om_closed = np.vstack([om_contour, om_contour[:1]])
        im_closed = np.vstack([im_contour, im_contour[:1]])
        ax.plot(om_closed[:,0], om_closed[:,1], color='yellow', lw=1.2, alpha=0.9, label="OM Contour" if bid==1 else "")
        ax.plot(im_closed[:,0], im_closed[:,1], color='cyan',   lw=1.2, alpha=0.9, label="IM Contour" if bid==1 else "")

        # centroid from IM contour moments
        M = cv2.moments(im_contour)
        if abs(M["m00"]) < 1e-8:
            continue
        cent = np.array([M["m10"] / M["m00"], M["m01"] / M["m00"]], dtype=np.float32)
        ax.scatter(cent[0], cent[1], c='lime', s=80, edgecolors='black', label='Centroid' if bid == 1 else "", zorder=6)

        # uniform sampling along OM
        diffs = np.diff(om_contour, axis=0, append=om_contour[:1])
        seg_lens = np.hypot(diffs[:, 0], diffs[:, 1])
        cumlen = np.cumsum(seg_lens)
        total = cumlen[-1] if len(cumlen) > 0 else 0
        if total <= 0:
            continue
        targets = np.linspace(0, total, max(50, N), endpoint=False)
        idxs = np.searchsorted(cumlen, targets)
        idxs = np.clip(idxs, 0, len(om_contour) - 1)
        sampled_om_points = om_contour[idxs]

        # eccentricity (ellipse fit if possible)
        if len(im_contour) >= 5:
            (x, y), (MA, ma), angle = cv2.fitEllipse(im_contour.astype(np.float32))
            a, b = max(MA, ma) / 2.0, min(MA, ma) / 2.0
            eccentricity = float(np.sqrt(max(0.0, 1 - (b * b) / (a * a))))
        else:
            eccentricity = 1.0

        if eccentricity < 0.7:
            major_axis = np.array([1.0, 0.0])
            minor_axis = np.array([0.0, 1.0])
        else:
            eigvecs = pca_axes(om_contour)
            major_axis, minor_axis = eigvecs[:, 0], eigvecs[:, 1]

        # poles/sides
        projections_major = np.dot(om_contour - cent, major_axis)
        projections_minor = np.dot(om_contour - cent, minor_axis)
        p1 = cent + major_axis * projections_major.min()
        p2 = cent + major_axis * projections_major.max()
        s1 = cent + minor_axis * projections_minor.min()
        s2 = cent + minor_axis * projections_minor.max()

        # shortest distances
        measurements = []
        tree = scipy.spatial.cKDTree(im_contour)
        for pt in sampled_om_points:
            pt_f = pt.astype(float)
            dist, idx = tree.query(pt_f)
            imp = im_contour[idx]

            vec_pt_cent = cent - pt_f
            denom = np.linalg.norm(vec_pt_cent) + 1e-8
            cos_angle = np.dot(vec_pt_cent, major_axis) / denom
            angle = np.arccos(np.clip(cos_angle, -1, 1))
            if np.dot(pt_f - cent, minor_axis) < 0:
                angle = 2 * np.pi - angle

            measurements.append({"OM": pt_f, "IM": imp, "Thickness": dist, "Angle": angle})
            ax.plot([pt_f[0], imp[0]], [pt_f[1], imp[1]], color='red', lw=0.5, alpha=0.25, zorder=2)

        if not measurements:
            continue

        # normalize angles to start at pole1
        measurements.sort(key=lambda x: x["Angle"]) 
        pole1_angle = measurements[0]["Angle"]
        for m in measurements:
            m["Angle"] = (m["Angle"] - pole1_angle) % (2 * np.pi)

        # axes
        ax.plot([p1[0], cent[0], p2[0]], [p1[1], cent[1], p2[1]], 'deepskyblue', ls='--', lw=2, label="Pole Axis" if bid == 1 else "", zorder=3)
        ax.plot([s1[0], cent[0], s2[0]], [s1[1], cent[1], s2[1]], 'lime', ls='--', lw=2, label="Side Axis" if bid == 1 else "", zorder=3)

        # special points
        color_map = {"Pole 1": ('red', p1), "Pole 2": ('blue', p2),
                     "Side 1": ('green', s1), "Side 2": ('purple', s2)}
        for label, (col, pt) in color_map.items():
            ax.scatter(pt[0], pt[1], c=col, s=50, edgecolors='black', zorder=5)
            ax.text(pt[0], pt[1] - 20, f"{label} (B{bid})", fontsize=8, color='yellow',
                    ha='center', bbox=dict(facecolor='black', alpha=0.6, pad=2), zorder=7)

        distances_px = [m["Thickness"] for m in measurements]
        angles_deg = [np.degrees(m["Angle"]) for m in measurements]
        df = pd.DataFrame({
            "Bacterium": [bid] * len(distances_px),
            "Distance (px)": distances_px,
            "Distance (nm)": [d * nm_per_px for d in distances_px],
            "Angle (deg)": angles_deg
        })
        all_dfs.append(df)

        # per-cell metrics
        mean_t = df["Distance (nm)"].mean()
        var_t = df["Distance (nm)"].var()
        std_t = df["Distance (nm)"].std()
        cv_t = (std_t / mean_t) if mean_t > 0 else np.nan

        poles = df[(df["Angle (deg)"] < 20) | (df["Angle (deg)"] > 340) |
                   ((df["Angle (deg)"] > 160) & (df["Angle (deg)"] < 200))]
        sides = df[((df["Angle (deg)"] > 70) & (df["Angle (deg)"] < 110)) |
                   ((df["Angle (deg)"] > 250) & (df["Angle (deg)"] < 290))]
        mean_poles = poles["Distance (nm)"].mean()
        mean_sides = sides["Distance (nm)"].mean()

        metrics_list.append({
            "Bacterium": bid,
            "Mean Thickness (nm)": mean_t,
            "Variance (nm^2)": var_t,
            "Std (nm)": std_t,
            "CV": cv_t,
            "Pole Mean (nm)": mean_poles,
            "Side Mean (nm)": mean_sides,
            "Pole-Side Diff (nm)": (mean_poles - mean_sides) if (not np.isnan(mean_poles) and not np.isnan(mean_sides)) else np.nan
        })

        # thickness at target angles
        for target in target_angles:
            idx = (df["Angle (deg)"] - target).abs().idxmin()
            row_df = df.loc[[idx]].copy()
            row_df['Target_Angle'] = target
            angles_dfs.append(row_df)

    ax.legend(loc='upper right', fontsize=7)

    combined_df = pd.concat(all_dfs, ignore_index=True) if all_dfs else pd.DataFrame()
    metrics_df = pd.DataFrame(metrics_list) if metrics_list else pd.DataFrame()
    angles_df = pd.concat(angles_dfs, ignore_index=True) if angles_dfs else pd.DataFrame()

    return fig_to_base64(fig, save_overlay_path), combined_df, metrics_df, angles_df

# =========================
# Dash App
# =========================
app = Dash(__name__)
app.title = "EM Thickness Viewer (PNG)"

app.layout = html.Div([
    html.H2("EM Thickness Dash (Shortest OM toIM)PNGs"),

    html.Div([
        html.Div([
            html.Label("Images folder"),
            dcc.Input(id="images-dir", type="text", value=DEFAULT_IMAGES_DIR, style={"width": "100%"}),
        ], style={"flex": "3", "paddingRight": "10px"}),
        html.Div([
            html.Button("Scan Folder", id="scan-btn", n_clicks=0, style={"width": "100%"})
        ], style={"flex": "1"}),
    ], style={"display": "flex", "gap": "8px", "alignItems": "end", "marginBottom": "8px"}),

    html.Div([
        html.Div([
            html.Label("Select image"),
            dcc.Dropdown(id="image-dropdown", options=[], value=None, placeholder="Choose an image", style={"width": "100%"}),
        ], style={"flex": "3", "paddingRight": "10px"}),
        html.Div([
            html.Label("YOLO conf"),
            dcc.Slider(id="conf-slider", min=0.1, max=0.9, step=0.05, value=0.25,
            marks={0.1:"0.1", 0.25:"0.25", 0.5:"0.5", 0.75:"0.75", 0.9:"0.9"},
            tooltip={"placement": "bottom", "always_visible": False})
        ], style={"flex": "2"}),
        html.Div([
            html.Label("Sampling N (OM points)"),
            dcc.Slider(id="N-slider", min=500, max=15000, step=500, value=3000,
            marks={500:"500", 3000:"3k", 6000:"6k", 10000:"10k", 15000:"15k"}, 
                       tooltip={"placement": "bottom", "always_visible": False})
        ], style={"flex": "3", "paddingLeft": "10px"}),
        html.Div([
            html.Label("nm/px"),
            dcc.Input(id="nmppx", type="number", value=NM_PER_PX, step=0.01, style={"width": "100%"}),
        ], style={"flex": "1", "paddingLeft": "10px"}),
        html.Div([
            html.Button("Run", id="run-btn", n_clicks=0, style={"width": "100%", "marginTop": "18px"})
        ], style={"flex": "1", "paddingLeft": "10px"}),
    ], style={"display": "flex", "gap": "8px", "alignItems": "end"}),

    html.Div([
        html.Div([
            html.Label("Output folder"),
            dcc.Input(id="output-dir", type="text", value=DEFAULT_OUTPUT_DIR, style={"width": "100%"}),
        ], style={"flex": "3", "paddingRight": "10px"}),
        html.Div([
            dcc.Checklist(id="save-check",
                          options=[{"label": " Save overlay + CSVs", "value": "save"}],
                          value=["save"],
                          style={"marginTop": "8px"})
        ], style={"flex": "2"}),
    ], style={"display": "flex", "gap": "8px", "alignItems": "end", "marginTop": "6px"}),

    html.Hr(),

    dcc.Tabs([
        dcc.Tab(label="Viewer", children=[
            html.Div(id="overlay-holder", children=[
                html.Div("Load an image and click Run.", id="overlay-msg")
            ], style={"marginTop": "10px"})
        ]),
        dcc.Tab(label="Metrics", children=[
            html.Div([
                html.H4("Per-cell metrics"),
                dash_table.DataTable(id="metrics-table", page_size=8, style_table={"overflowX": "auto"}, style_cell={"fontFamily": "monospace", "fontSize": "12px"}),
                html.Br(),
                html.Div([
                    html.Button("Download per-cell metrics CSV", id="dl-metrics-btn"),
                    dcc.Download(id="dl-metrics")
                ]),
                html.Hr(),
                html.H4("All thickness samples"),
                dash_table.DataTable(id="combined-table", page_size=10, style_table={"overflowX": "auto"}, style_cell={"fontFamily": "monospace", "fontSize": "12px"}),
                html.Br(),
                html.Div([
                    html.Button("Download all samples CSV", id="dl-combined-btn"),
                    dcc.Download(id="dl-combined")
                ]),
                html.Hr(),
                html.H4("Thickness at target angles"),
                dash_table.DataTable(id="angles-table", page_size=10, style_table={"overflowX": "auto"}, style_cell={"fontFamily": "monospace", "fontSize": "12px"}),
                html.Br(),
                html.Div([
                    html.Button("Download angle rows CSV", id="dl-angles-btn"),
                    dcc.Download(id="dl-angles")
                ]),
            ], style={"padding": "10px"})
        ]),
    ]),

    dcc.Store(id="store-combined"),
    dcc.Store(id="store-metrics"),
    dcc.Store(id="store-angles"),
])

# =========================
# Callbacks
# =========================
@app.callback(
    Output("image-dropdown", "options"),
    Output("image-dropdown", "value"),
    Input("scan-btn", "n_clicks"),
    State("images-dir", "value"),
    prevent_initial_call=False
)
def scan_images(n, folder):
    files = list_images(folder or "")
    opts = [{"label": os.path.basename(p), "value": p} for p in files]
    value = files[0] if files else None
    return opts, value

_model = None

def get_model():
    global _model
    if _model is None:
        _model = YOLO(MODEL_PATH)
    return _model

@app.callback(
    Output("overlay-holder", "children"),
    Output("store-combined", "data"),
    Output("store-metrics", "data"),
    Output("store-angles", "data"),
    Input("run-btn", "n_clicks"),
    State("image-dropdown", "value"),
    State("conf-slider", "value"),
    State("N-slider", "value"),
    State("nmppx", "value"),
    State("output-dir", "value"),
    State("save-check", "value"),
    prevent_initial_call=True
)
def run_pipeline(n_clicks, image_path, conf, N, nm_per_px, out_dir, save_flags):
    if not image_path or not os.path.isfile(image_path):
        return html.Div("Please select a valid image."), None, None, None

    img_bgr = cv2.imread(image_path)
    if img_bgr is None:
        return html.Div("Failed to read image."), None, None, None
    image_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)

    model = get_model()
    om_masks, im_masks = run_yolo_on_image(model, image_rgb, conf=conf)

    if len(om_masks) == 0 or len(im_masks) == 0:
        return html.Div("No OM/IM masks detected. Adjust conf or choose another image."), None, None, None

    # Prepare output paths
    base = Path(image_path).stem
    out_dir = out_dir or DEFAULT_OUTPUT_DIR
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    overlay_path = str(Path(out_dir) / f"{base}_thickness.png")
    samples_csv = str(Path(out_dir) / f"{base}_thickness.csv")
    metrics_csv = str(Path(out_dir) / f"{base}_metrics.csv")
    angles_csv  = str(Path(out_dir) / f"{base}_angles.csv")

    overlay_uri, combined_df, metrics_df, angles_df = process_and_draw_all(
        om_masks, im_masks, image_rgb, nm_per_px=float(nm_per_px or NM_PER_PX),
        N=int(N), save_overlay_path=overlay_path if (save_flags and "save" in save_flags) else None
    )

    # Save CSVs if requested
    if save_flags and "save" in save_flags:
        if combined_df is not None and not combined_df.empty:
            combined_df.to_csv(samples_csv, index=False)
        if metrics_df is not None and not metrics_df.empty:
            metrics_df.to_csv(metrics_csv, index=False)
        if angles_df is not None and not angles_df.empty:
            angles_df.to_csv(angles_csv, index=False)

    saved_note = html.Small(
        f"Saved to: {overlay_path if (save_flags and 'save' in save_flags) else '(not saved)'}",
        style={"display": "block", "color": "#666", "marginTop": "6px"}
    )

    img_comp = html.Div([
        html.Img(src=overlay_uri, style={"maxWidth": "85%", "border": "1px solid #ccc", "borderRadius": "8px", "boxShadow": "0 2px 8px rgba(0,0,0,0.1)"}),
        saved_note
    ])

    return img_comp, (
        combined_df.head(10).to_json(orient="split") if (combined_df is not None and not combined_df.empty) else None
    ), (
        metrics_df.head(10).to_json(orient="split") if (metrics_df is not None and not metrics_df.empty) else None
    ), (
        angles_df.head(10).to_json(orient="split") if (angles_df is not None and not angles_df.empty) else None
    )

@app.callback(
    Output("combined-table", "data"),
    Output("combined-table", "columns"),
    Input("store-combined", "data")
)
def show_combined(data_json):
    if not data_json:
        return [], []
    df = pd.read_json(data_json, orient="split")
    cols = [{"name": c, "id": c} for c in df.columns]
    return df.to_dict("records"), cols

@app.callback(
    Output("metrics-table", "data"),
    Output("metrics-table", "columns"),
    Input("store-metrics", "data")
)
def show_metrics(data_json):
    if not data_json:
        return [], []
    df = pd.read_json(data_json, orient="split")
    cols = [{"name": c, "id": c} for c in df.columns]
    return df.to_dict("records"), cols

@app.callback(
    Output("angles-table", "data"),
    Output("angles-table", "columns"),
    Input("store-angles", "data")
)
def show_angles(data_json):
    if not data_json:
        return [], []
    df = pd.read_json(data_json, orient="split")
    cols = [{"name": c, "id": c} for c in df.columns]
    return df.to_dict("records"), cols

# Downloads
from dash import dcc

@app.callback(
    Output("dl-combined", "data"),
    Input("dl-combined-btn", "n_clicks"),
    State("store-combined", "data"),
    prevent_initial_call=True
)
def dl_combined(n, data_json):
    if not data_json:
        return dcc.send_string("", "combined.csv")
    df = pd.read_json(data_json, orient="split")
    return dcc.send_string(df.to_csv(index=False), "combined_thickness_samples_head.csv")

@app.callback(
    Output("dl-metrics", "data"),
    Input("dl-metrics-btn", "n_clicks"),
    State("store-metrics", "data"),
    prevent_initial_call=True
)
def dl_metrics(n, data_json):
    if not data_json:
        return dcc.send_string("", "metrics.csv")
    df = pd.read_json(data_json, orient="split")
    return dcc.send_string(df.to_csv(index=False), "per_cell_metrics_head.csv")

@app.callback(
    Output("dl-angles", "data"),
    Input("dl-angles-btn", "n_clicks"),
    State("store-angles", "data"),
    prevent_initial_call=True
)
def dl_angles(n, data_json):
    if not data_json:
        return dcc.send_string("", "angles.csv")
    df = pd.read_json(data_json, orient="split")
    return dcc.send_string(df.to_csv(index=False), "target_angle_rows_head.csv")

if __name__ == "__main__":
    #app.run_server(debug=True, host="127.0.0.1", port=8050)
    app.run(debug=True, host="127.0.0.1", port=8050)
