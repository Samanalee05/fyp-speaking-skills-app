# FYP: AI-Assisted Audio Application for Enhancing English Communication Skills

## Project Overview
A mobile application that analyses spoken English audio and provides transparent and actionable feedback to help students improve their communication and public speaking skills.

## Pipelines
- **Pipeline A:** Audio spoof detection - classifies audio as bonafide (human) or AI-generated (spoof) using a custom CNN trained on log-mel spectograms (ASVspoof2019 LA dataset)
-**Pipeline B:** *(in progress)* Speech proficency classification and feedback generation

## Repository STructure
```
fyp-speaking-skills-app/
├── PipelineA_ASVspoof/
│   ├── notebooks/     # Jupyter notebooks
│   ├── models/        # Saved model checkpoints (not tracked by git)
│   └── outputs/       # Plots and evaluation results
├── PipelineB_SpeechAssessment/
├── App/
└── requirements.txt
```

## Dataset
Pipeline A uses the ASVspoof2019 Logical Access (LA) dataset.
Dataset is not included in this repository due to size.

## Setup
```
pip install -r requirements.txt
```

## Hardware
Trained locally on ASUS TUF Gaming F16 with NVIDIA GPU (CUDA).
```