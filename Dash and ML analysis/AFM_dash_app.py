import os
import glob
import base64
import numpy as np
import cv2
import h5py
from PIL import Image
import SciFiReaders as sr
from ultralytics import YOLO
from dash import Dash, html, dcc, Input, Output, State
import plotly.express as px
from skimage.measure import label, regionprops
import pandas as pd

### Initialize Dash app #####
app = Dash(__name__)
app.title = "Bacteria Analysis Dashboard"

### YOLO model ######
model = YOLO("/home/cloud/microflow_sidpy_nomad_server/best_AFM.pt")

#### Directories #####
UPLOAD_FOLDER = "/home/cloud/afm_images"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

#### Helper functions ##########

def numpy_to_png(arr, out):
    norm = 255 * (arr - arr.min()) / (arr.max() - arr.min())
    Image.fromarray(norm.astype(np.uint8)).save(out)

def process_image_with_yolo(png, conf=0.25):
    gray    = cv2.imread(png, cv2.IMREAD_GRAYSCALE)
    resized = cv2.resize(gray, (640, 640))
    rgb     = cv2.cvtColor(resized, cv2.COLOR_GRAY2RGB)
    masks   = model.predict(rgb, conf=conf)[0].masks.data.cpu().numpy()  # N×H×W

    combined = np.max(masks.astype(np.uint8), axis=0)
    orig     = cv2.imread(png)
    h, w     = orig.shape[:2]
    combined = cv2.resize(combined, (w, h), interpolation=cv2.INTER_NEAREST)
    overlay  = cv2.addWeighted(orig,1,np.stack([combined*0,combined*255,combined*0],-1),0.5,0)

    props_list = []
    for i, m in enumerate(masks):
        m_full = cv2.resize(m.astype(np.uint8), (w, h), interpolation=cv2.INTER_NEAREST)
        for p in regionprops(label(m_full)):
            props_list.append({
                'mask_idx': i,
                'Area': p.area,
                'Perimeter': p.perimeter,
                'Orientation': p.orientation,
                'Eccentricity': p.eccentricity,
                'coords': p.coords
            })
    df = pd.DataFrame(props_list)
    return combined, overlay, masks, df

def to_b64_png(img):
    _, buf = cv2.imencode('.png', img)
    return base64.b64encode(buf).decode()

# ─── Layout ─────────────────────────────────────────────────────────────────────

app.layout = html.Div([
    html.H1("Bacteria Analysis Dashboard"),
    html.Div([
        "Data folder:",
        dcc.Input(id="path-input", type="text", value=UPLOAD_FOLDER, style={"width":"70%"}),
        html.Button("Load Files", id="load-files-btn")
    ], style={"margin":"20px 0"}),
    html.Div([
        "Select .h5 files:",
        dcc.Dropdown(id="file-dropdown", multi=True, style={"width":"70%"}),
        html.Button("Process Selected", id="process-btn")
    ], style={"margin":"20px 0"}),
    html.Div([
        "YOLO Confidence:",
        dcc.Slider(
            id="conf-slider", min=0.0, max=1.0, step=0.01, value=0.25,
            marks={0.0:"0.0",0.25:"0.25",0.5:"0.5",0.75:"0.75",1.0:"1.0"},
            tooltip={"placement":"bottom"}, updatemode="drag"
        )
    ], style={"margin":"20px 0"}),
    html.Div(id="output-content")
])

# ─── Callbacks ───────────────────────────────────────────────────────────────────

@app.callback(
    Output("file-dropdown","options"),
    Input("load-files-btn","n_clicks"),
    State("path-input","value")
)
def list_files(n, fld):
    if not n or not fld:
        return []
    return [{"label":os.path.basename(f),"value":f}
            for f in glob.glob(os.path.join(fld, "*.h5")) + glob.glob(os.path.join(fld, "*.h5.nxs"))]

@app.callback(
    Output("output-content","children"),
    Input("process-btn","n_clicks"),
    [State("file-dropdown","value"), State("conf-slider","value")]
)
def process(n, files, conf):
    if not n or not files:
        return "No files selected."

    panels = []
    for fp in files:
        base_name = os.path.basename(fp).replace(".h5", "")
        with h5py.File(fp,'r') as hf:
            pxnm = next((v for k, v in hf.attrs.items() if "pixel" in k.lower()), 1.0)
        psum = pxnm / 1000.0

        # Read dataset
        arr = np.array(sr.NSIDReader(fp).read()['Channel_000'])

        # --- Safely derive PNG and overlay paths (handles .h5, .h5.nxs, etc.) ---
        root, ext1 = os.path.splitext(fp)       # removes .nxs if present
        root, ext2 = os.path.splitext(root)     # removes .h5 if present
        png = root + ".png"
        ovp = root + "_overlay.png"

        # Convert and run YOLO
        numpy_to_png(arr, png)
        combined, ov, raw_masks, df = process_image_with_yolo(png, conf)

        # physical units
        df['Area_μm2']        = df['Area'] * psum**2
        df['Perimeter_μm']    = df['Perimeter'] * psum
        df['Orientation_deg'] = df['Orientation'] * 180 / np.pi

        # save overlay
        cv2.imwrite(ovp, ov)
        b64_ov = base64.b64encode(open(ovp, 'rb').read()).decode()

        # Histograms
        specs=[("Area (μm²)", "Area_μm2", "lightgreen"),
               ("Perimeter (μm)", "Perimeter_μm", "lightblue"),
               ("Eccentricity", "Eccentricity", "lightsalmon"),
               ("Orientation (°)", "Orientation_deg", "lightgrey")]
        histos=[]
        for title, col, color in specs:
            fig=px.histogram(df, x=col, nbins=20, color_discrete_sequence=[color])
            fig.update_traces(marker_line_width=0.5, marker_line_color='white')
            fig.update_layout(
                bargap=0.05, plot_bgcolor='white', paper_bgcolor='white',
                margin=dict(l=30,r=20,t=30,b=30),
                xaxis=dict(showline=True,linewidth=1,linecolor='black',mirror=True),
                yaxis=dict(showline=True,linewidth=1,linecolor='black',mirror=True),
                showlegend=False, width=200, height=200, title_x=0.5
            )
            histos.append(dcc.Graph(figure=fig, style={"display":"inline-block"}))

        # Scatter plots
        fig_ae = px.scatter(df, x='Area_μm2', y='Eccentricity',
            title='Area vs Eccentricity', color='Eccentricity', color_continuous_scale='Viridis',
            labels={'Area_μm2':'Area (µm²)','Eccentricity':'Eccentricity'})
        fig_ae.update_layout(plot_bgcolor='white', paper_bgcolor='white',
            margin=dict(l=40,r=20,t=40,b=40),
            xaxis=dict(showline=True,linewidth=1,linecolor='black',mirror=True),
            yaxis=dict(showline=True,linewidth=1,linecolor='black',mirror=True),
            title_x=0.5, width=400, height=300)

        fig_ao = px.scatter(df, x='Area_μm2', y='Orientation_deg',
            title='Area vs Orientation', color='Area_μm2', color_continuous_scale='Viridis',
            labels={'Area_μm2':'Area (µm²)','Orientation_deg':'Orientation (°)'})
        fig_ao.update_layout(plot_bgcolor='white', paper_bgcolor='white',
            margin=dict(l=40,r=20,t=40,b=40),
            xaxis=dict(showline=True,linewidth=1,linecolor='black',mirror=True),
            yaxis=dict(showline=True,linewidth=1,linecolor='black',mirror=True),
            title_x=0.5, width=400, height=300)

        # 3D Scatter
        fig3 = px.scatter_3d(df,
            x='Area_μm2', y='Perimeter_μm', z='Orientation_deg',
            title='3D: Area vs Perimeter vs Orientation',
            color='Area_μm2', color_continuous_scale='Viridis',
            labels={'Area_μm2':'Area (µm²)','Perimeter_μm':'Perimeter (µm)','Orientation_deg':'Orientation (°)'}
        )
        fig3.update_traces(marker=dict(size=4,line=dict(width=0.5,color='white')))
        fig3.update_layout(
            title_x=0.5, margin=dict(l=0,r=0,t=40,b=0), width=500, height=450,
            scene=dict(
                aspectmode='cube',
                xaxis=dict(showbackground=True,backgroundcolor='rgba(230,230,230,0.5)',
                           showgrid=True,gridcolor='lightgrey',showline=True,linecolor='black',mirror=True),
                yaxis=dict(showbackground=True,backgroundcolor='rgba(230,230,230,0.5)',
                           showgrid=True,gridcolor='lightgrey',showline=True,linecolor='black',mirror=True),
                zaxis=dict(showbackground=True,backgroundcolor='rgba(230,230,230,0.5)',
                           showgrid=True,gridcolor='lightgrey',showline=True,linecolor='black',mirror=True)
            )
        )

        # Mask property maps
        H, W = raw_masks.shape[1], raw_masks.shape[2]
        area_map = np.zeros((H, W)); ecc_map = np.zeros((H, W)); ori_map = np.zeros((H, W))
        for idx, row in df.iterrows():
            m_full = cv2.resize(raw_masks[int(row['mask_idx'])].astype(np.uint8), (W, H),
                                interpolation=cv2.INTER_NEAREST).astype(bool)
            area_map[m_full] = row['Area']
            ecc_map[m_full]  = row['Eccentricity']
            ori_map[m_full]  = row['Orientation_deg']

        area_map[area_map == 0] = np.nan
        ecc_map[ecc_map == 0]   = np.nan
        ori_map[ori_map == 0]   = np.nan

        fig_mask_area = px.imshow(area_map, color_continuous_scale="Viridis",
            title="Mask → Area", labels={'color':'Area (pixels)'}, origin='upper')
        fig_mask_ecc = px.imshow(ecc_map, color_continuous_scale="Plasma",
            title="Mask → Eccentricity", labels={'color':'Eccentricity'}, origin='upper')
        fig_mask_ori = px.imshow(ori_map, color_continuous_scale="Cividis",
            title="Mask → Orientation (°)", labels={'color':'Orientation (°)'}, origin='upper')

        for fig in (fig_mask_area, fig_mask_ecc, fig_mask_ori):
            fig.update_layout(
                margin=dict(l=20, r=20, t=30, b=20),
                width=300, height=300,
                plot_bgcolor='white', paper_bgcolor='white'
            )
            fig.update_xaxes(showticklabels=False).update_yaxes(showticklabels=False)

        # Final layout panel
        panels.append(html.Div([
            html.Img(
                src=f"data:image/png;base64,{b64_ov}",
                style={"maxWidth":"500px","border":"1px solid #ccc","marginBottom":"20px"}
            ),
            html.Div(histos, style={"textAlign":"center","gap":"10px","marginBottom":"30px"}),
            html.Div([
                dcc.Graph(figure=fig_ae, style={"display":"inline-block","verticalAlign":"top"}),
                dcc.Graph(figure=fig_ao, style={"display":"inline-block","verticalAlign":"top"}),
                dcc.Graph(figure=fig3,  style={"display":"inline-block","verticalAlign":"top"})
            ], style={"textAlign":"center","gap":"40px","marginBottom":"30px"}),
            html.Div([
                dcc.Graph(figure=fig_mask_area, style={
                    "display":"inline-block","border":"2px solid black","border-radius":"4px","margin":"5px"}),
                dcc.Graph(figure=fig_mask_ecc, style={
                    "display":"inline-block","border":"2px solid black","border-radius":"4px","margin":"5px"}),
                dcc.Graph(figure=fig_mask_ori, style={
                    "display":"inline-block","border":"2px solid black","border-radius":"4px","margin":"5px"})
            ], style={"textAlign":"center","gap":"20px"})
        ], style={"margin":"40px 0","textAlign":"center"}))

    return panels

if __name__=='__main__':
    app.run(debug=True, port=8051)
