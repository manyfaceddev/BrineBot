from io import BytesIO
from pathlib import Path
from typing import Dict, Tuple, Union
from brine_models import BrineComposition, STANDARD_CATIONS, STANDARD_ANIONS


def normalize_manually_entered_composition(cations: Dict[str, float], anions: Dict[str, float]) -> BrineComposition:
    cleaned_cations = {ion: value for ion, value in cations.items() if ion and value is not None and value > 0}
    cleaned_anions = {ion: value for ion, value in anions.items() if ion and value is not None and value > 0}
    return BrineComposition(cations=cleaned_cations, anions=cleaned_anions, source="manual_input")


def parse_uploaded_file(file_obj: Union[BytesIO, str], filename: str = "") -> BrineComposition:
    """Parse a PDF or image file into a BrineComposition.

    Accepts either a file-like object (from st.file_uploader) or a file-path string.
    PDF / OCR extraction is a placeholder — replace with real logic in phase 2.
    """
    if isinstance(file_obj, str):
        path = Path(file_obj)
        if not path.exists():
            raise FileNotFoundError(f"Input file not found: {file_obj}")
        source_name = path.name
    else:
        source_name = filename or "uploaded_file"

    # ── Phase 2: insert pdfplumber / pytesseract extraction here ────────────
    return BrineComposition(
        cations={"Na": 0.1, "Ca": 0.02},
        anions={"Cl": 0.2, "HCO3": 0.01},
        source=source_name,
        notes="Placeholder composition — replace with real PDF/OCR extraction in phase 2.",
    )


def make_dropdown_options(custom_items: str) -> Tuple[list[str], list[str]]:
    cation_options = STANDARD_CATIONS.copy()
    anion_options = STANDARD_ANIONS.copy()

    for item in [token.strip() for token in custom_items.split(",") if token.strip()]:
        if item not in cation_options and item not in anion_options:
            if item[0].isupper():
                cation_options.append(item)
            else:
                anion_options.append(item)

    return cation_options, anion_options
