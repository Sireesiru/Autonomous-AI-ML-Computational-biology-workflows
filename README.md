# Facility-Scale AI/ML workflows for multimodal dataset integration and analysis 

This repository documents a facility-scale workflow for microscopy data acquisition, standardization, machine-learning–enabled analysis, and metadata management developed at the Center for Nanophase Materials Sciences (CNMS), Oak Ridge National Laboratory.The workflow is designed to operate under realistic scientific user-facility constraints, including network-isolated instruments, heterogeneous vendor-specific data formats, and the need for scalable, reproducible analysis pipelines. This repository provides a general, deployable framework for handling heterogeneous, multimodal scientific data across network boundaries, standardizing it, managing metadata, and enabling downstream ML workflows. We show reference implementations, architectural patterns, and portable analysis components that can be adapted to other shared experimental facilities. 

<img width="500" height="250" alt="image" src="https://github.com/user-attachments/assets/d7724ca1-aee5-4d6e-99fd-83ecd7d3dc56" />

## Scope and Design 
This repository focuses on:
- End-to-end workflow design from instrument data acquisition to ML-enabled analysis
- Standardization of heterogeneous microscopy data using sidpy and HDF5
- Automated preprocessing and metadata extraction
- Deployment of ML-based segmentation and quantitative analysis pipelines
- Interactive visualization of analysis outputs
- Human-guided refinement and incremental model updating

Components that depend on internal networking, security policies, or facility-specific services are documented architecturally rather than provided as executable code.

## High-Level Workflow
<img width="200" height="200" alt="image" src="https://github.com/user-attachments/assets/4447db65-1d3f-42ec-abf1-148b969e7a49" />

## 📁 Repository Structure

```
AI-ML-Computational-workflows/
├── Data/                        # Standardized reference datasets
├── Standardization/             # Scripts to convert vendor formats → HDF5
├── metadata into NOMAD/         # Metadata extraction and NOMAD upload tools
└── Dash and ML analysis/        # Interactive dashboards and ML segmentation

## ⚙️ Requirements

```bash
pip install sidpy h5py numpy matplotlib dash plotly


## Usage

### 1. Clone this repository
```bash
git clone https://github.com/Sireesiru/AI-ML-Computational-workflows.git
cd AI-ML-Computational-workflows
```

### 2. Standardize raw microscopy data
```bash
cd Standardization
python ibw_watcher_v2a.py
```

### 3. Extract and upload metadata to NOMAD
```bash
cd "metadata into NOMAD"
python excel_to_nomad_json.py
python UPLOAD_ID_sample_name_mapping.py
```

### 4. Generate QR codes for sample tracking
```bash
cd "metadata into NOMAD"
python get_QR.py
```

### 5. Launch the ML analysis dashboard
```bash
cd "Dash and ML analysis"
python gui.py
```

    


