# Brine Bot

A Streamlit app (with a CLI companion) for reservoir brine calculations — preparation instructions and cationic/anionic split brines.

## What is included

- `streamlit_app.py`: Streamlit UI — manual entry or file upload, unit toggle, preparation instructions, and split-brine output with per-sub-brine preparation instructions.
- `app.py`: CLI entry point for scripted or VS Code use.
- `brine_models.py`: Standard cations/anions, ion charges, molar masses, salt database, and default salt mappings.
- `brine_calculations.py`: Core calculations — preparation instructions (4-step salt algorithm), split-brine math, charge-balance validation, and mol/L ↔ mg/L converters.
- `input_tools.py`: Manual composition normalisation and PDF/image file parsing (phase 2 placeholder).
- `requirements.txt`: Dependencies for Streamlit and PDF/image support.

## How to run

### Streamlit

```bash
streamlit run streamlit_app.py
```

The sidebar lets you:
- Choose **Manual entry** or **Upload PDF / image** (PDF/OCR extraction is a placeholder — see phase 2).
- Switch concentration units between **mol/L** and **mg/L**.
- Select a task: **Prepare brine instructions** or **Split into cationic/anionic brines**.
- Set the preparation volume (litres).

### CLI

```bash
python app.py --task prepare --volume 1.0 --cations Na=0.1,Ca=0.02 --anions Cl=0.2,HCO3=0.01
python app.py --task split   --volume 1.0 --cations Na=0.2,Ca=0.05 --anions Cl=0.3
python app.py --task prepare --pdf sample_brine.pdf
```

Concentrations are in **mol/L** on the CLI.

## Salt preparation algorithm

1. **Non-Cl anions** (HCO3, CO3, SO4, OH, Br) are delivered via their default Na-salt (NaHCO3, Na2CO3, Na2SO4, NaOH, NaBr). Na consumed is tracked.
2. **Non-Na cations** (Ca, Mg, K, Sr, Ba …) are delivered via their default chloride salt. Cl contributed is tracked.
3. **Remaining Na** is delivered as NaCl, which also contributes additional Cl.
4. A **Cl balance check** verifies that total Cl from all salts matches the target — a mismatch flags a charge-imbalanced input.

## Next steps (phase 2)

- Real PDF / OCR extraction of brine analysis reports (`pdfplumber` + `pytesseract` hooks are in place).
- Unit tests for preparation instructions and split-brine math.
- Support for additional ions and salts on request.
