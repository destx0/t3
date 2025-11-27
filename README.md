# Testbook PYQ Downloader

Download previous year question papers from Testbook with a simple TUI.

## Installation

**Option 1: pipx (recommended)**
```bash
pipx install git+https://github.com/YOUR_USERNAME/testbook-pyq-downloader.git
pyq
```

**Option 2: pip**
```bash
pip install git+https://github.com/YOUR_USERNAME/testbook-pyq-downloader.git
pyq
```

**Option 3: Run directly**
```bash
git clone https://github.com/YOUR_USERNAME/testbook-pyq-downloader.git
cd testbook-pyq-downloader
pip install -r requirements.txt
python downloader_tui.py
```

## Usage

Just run `pyq` and follow the prompts:
1. Search and select an exam
2. Select years to download
3. Papers are saved to `<exam_name>/cleaned/`

## Supported Exams

RRB Group D, SSC CGL, SSC CHSL, IBPS Clerk, SBI PO, RRB NTPC, SSC JE, and 80+ more.
