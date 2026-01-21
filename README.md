# Facility-Scale AI/ML workflows for autonomous multimodal data analysis 
AI/ML Workflows for multimodal datasets integration and analysis 

This repository documents a facility-scale workflow for microscopy data acquisition, standardization, machine-learning–enabled analysis, and metadata management developed at the Center for Nanophase Materials Sciences (CNMS), Oak Ridge National Laboratory.The workflow is designed to operate under realistic scientific user-facility constraints, including network-isolated instruments, heterogeneous vendor-specific data formats, and the need for scalable, reproducible analysis pipelines. This repository provides a general, deployable framework for handling heterogeneous, multimodal scientific data across network boundaries, standardizing it, managing metadata, and enabling downstream ML workflows. We show reference implementations, architectural patterns, and portable analysis components that can be adapted to other shared experimental facilities. 

<img width="500" height="500" alt="image" src="https://github.com/user-attachments/assets/d7724ca1-aee5-4d6e-99fd-83ecd7d3dc56" />

## Scope and Design Philosophy

This repository focuses on:
- End-to-end workflow design from instrument data acquisition to ML-enabled analysis
- Standardization of heterogeneous microscopy data using sidpy and HDF5
- Automated preprocessing and metadata extraction
- Deployment of ML-based segmentation and quantitative analysis pipelines
- Interactive visualization of analysis outputs
- Human-guided refinement and incremental model updating

Components that depend on internal networking, security policies, or facility-specific services are documented architecturally rather than provided as executable code.

## High-Level Workflow
<img width="742" height="531" alt="image" src="https://github.com/user-attachments/assets/1bc670f1-fa55-4e84-b274-e7d11899af2a" />
    


