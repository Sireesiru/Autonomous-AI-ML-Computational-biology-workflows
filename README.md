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

## Repository Structure
```
AI-ML-Computational-workflows/
├── Data/                        # Standardized reference datasets
├── Standardization/             # Scripts to convert vendor formats → HDF5
├── metadata into NOMAD/         # Metadata extraction and NOMAD upload tools
└── Dash and ML analysis/        # Interactive dashboards and ML segmentation
```
## Requirements

```bash
pip install sidpy h5py numpy matplotlib dash plotly
```
## Usage

> This workflow runs within the **CNMS Virtual Machines at Oak Ridge National Laboratory**. External replication requires equivalent cloud infrastructure. The workflow uses a client-server architecture.

### 1. Set up NOMAD-Oasis
Deploy a local NOMAD instance and containerize its components using Docker Compose.

### 2. Clone this repository
```bash
git clone https://github.com/Sireesiru/AI-ML-Computational-workflows.git
```
### 3. Start the server
```bash
cd Standardization
python server_1b.py
```
Note the **port number** printed in the terminal — you will need it in the next step.

### 4. Launch the GUI
```bash
python gui.py
```
Enter the port number from Step 3, your NOMAD credentials, and the folder path to watch. Once submitted, the server authenticates your credentials and initiates `ibw_watcher_v2a.py`, which monitors the specified folder continuously. Every new incoming file is converted to HDF5, uploaded to NOMAD, and its metadata extracted from raw image headers and pushed automatically.

### 5. Capture sample-specific metadata using a Custom Schema
As a prerequisite, import **braveschemasecond.archive.yaml** into your NOMAD instance, then run:
```bash
cd "metadata into NOMAD"
python excel_to_nomad_yaml.py
python UPLOAD_ID_sample_name_mapping.py
```
`excel_to_nomad_yaml.py` converts an Excel sheet of sample metadata into YAML files rendered via the custom schema. `UPLOAD_ID_sample_name_mapping.py` generates a mapping file linking sample names to their NOMAD upload IDs.

### 6. Generate QR codes for sample tracking
```bash
cd "metadata into NOMAD"
python get_QR.py
```
Generates QR codes from NOMAD URLs, linking physical samples to their complete digital records.

### 7. Launch the ML analysis dashboards
```bash
cd "Dash and ML analysis"
python AFM_dash_app.py
python EM_dash_app_thickness.py
```
Launches interactive Dash apps to visualize quantitative plots of AFM and electron microscopy datasets.

### 8. Human-in-the-Loop model refinement
To improve segmentation performance, fine-tune your models using additional synthetic bacterial images from [SimuScan](https://github.com/Rmillansol/SimuScan-AFMtools) and evaluate for improvement.

## Author
Developed at the Center for Nanophase Materials Sciences (CNMS), Oak Ridge National Laboratory.

Contact: **Sita Sirisha Madugula** — (mailto:madugulas@ornl.gov) | [ORCID]([https://orcid.org/your-orcid](https://orcid.org/0000-0001-9944-117X)

## License
The contents of this repository are licensed under the [MIT License](LICENSE).  
