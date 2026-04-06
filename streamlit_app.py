import streamlit as st
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from brine_models import STANDARD_CATIONS, STANDARD_ANIONS, ION_MOLAR_MASSES
from input_tools import (
    normalize_manually_entered_composition,
    make_dropdown_options,
    parse_uploaded_file,
)
from brine_calculations import (
    prepare_brine_instructions,
    split_brine,
    check_equal_mix,
    validate_charge_balance,
    mgl_to_moll,
    convert_composition_units,
)


# ── helpers ──────────────────────────────────────────────────────────────────

def _parse_manual_conc(ion: str, raw: float, unit: str) -> float:
    """Convert user-entered concentration to mol/L for internal storage."""
    if unit == "mg/L":
        if ion not in ION_MOLAR_MASSES:
            st.warning(f"No molar mass for '{ion}' — treating as mol/L.")
            return raw
        return mgl_to_moll(ion, raw)
    return raw


# ── UI sections ──────────────────────────────────────────────────────────────

def build_manual_composition(unit: str):
    st.header("Manual brine composition")

    custom_entries = st.text_input(
        "Add custom ions (comma-separated). Capitalise cations, lowercase anions.",
        value="",
    )
    cation_options, anion_options = make_dropdown_options(custom_entries)

    step = 1.0 if unit == "mg/L" else 0.01
    fmt = "%.2f" if unit == "mg/L" else "%.4f"

    st.markdown("**Cations**")
    cations_moll = {}
    for ion in cation_options:
        if ion and ion[0].isupper():
            raw = st.number_input(
                f"{ion} ({unit})", min_value=0.0, value=0.0, step=step, format=fmt, key=f"cat_{ion}"
            )
            if raw > 0:
                cations_moll[ion] = _parse_manual_conc(ion, raw, unit)

    st.markdown("**Anions**")
    anions_moll = {}
    for ion in anion_options:
        if ion:
            raw = st.number_input(
                f"{ion} ({unit})", min_value=0.0, value=0.0, step=step, format=fmt, key=f"an_{ion}"
            )
            if raw > 0:
                anions_moll[ion] = _parse_manual_conc(ion, raw, unit)

    return normalize_manually_entered_composition(cations_moll, anions_moll)


def show_composition(composition, unit: str):
    if unit == "mg/L":
        display = convert_composition_units(composition, "mg/L")
        st.text(display.format("mg/L"))
    else:
        st.text(str(composition))


# ── main app ─────────────────────────────────────────────────────────────────

def main():
    st.title("Brine Bot")

    # ── sidebar controls ──────────────────────────────────────────────────────
    task = st.sidebar.selectbox(
        "Select a task",
        ["Prepare brine instructions", "Split into cationic/anionic brines"],
    )
    volume_l = st.sidebar.number_input("Preparation volume (L)", min_value=0.1, value=1.0, step=0.1)
    unit = st.sidebar.radio("Concentration unit", ["mol/L", "mg/L"])
    input_type = st.sidebar.radio("Input type", ["Manual entry", "Upload PDF / image"])

    # ── composition input ─────────────────────────────────────────────────────
    composition = None

    if input_type == "Manual entry":
        composition = build_manual_composition(unit)
    else:
        uploaded = st.sidebar.file_uploader(
            "Upload brine analysis (PDF or image)",
            type=["pdf", "png", "jpg", "jpeg", "tiff"],
        )
        if uploaded is not None:
            try:
                composition = parse_uploaded_file(uploaded, filename=uploaded.name)
                st.sidebar.success(f"Loaded: {uploaded.name}")
                st.sidebar.info(
                    "PDF/image parsing is a placeholder. "
                    "Real extraction will be added in phase 2."
                )
            except Exception as exc:
                st.sidebar.error(f"Could not parse file: {exc}")

    if composition is None or composition.is_empty():
        st.info("Enter a composition or upload a file to continue.")
        return

    # ── composition summary ───────────────────────────────────────────────────
    st.subheader("Composition")
    show_composition(composition, unit)

    balanced, delta = validate_charge_balance(composition)
    if balanced:
        st.success("Charge balance: OK")
    else:
        st.warning(f"Charge balance: unbalanced (Δ = {delta:+.4g} eq/L). Results may be inconsistent.")

    st.divider()

    # ── task output ───────────────────────────────────────────────────────────
    if task == "Prepare brine instructions":
        st.subheader(f"Preparation instructions — {volume_l:.3g} L")
        instructions, warnings = prepare_brine_instructions(composition, volume_l=volume_l)

        if warnings:
            for w in warnings:
                st.warning(w)

        if instructions:
            for inst in instructions:
                st.write(f"- **{inst.salt_name}** ({inst.formula}): **{inst.grams:.2f} g** — {inst.notes}")
        else:
            st.info("No salts required (empty composition after filtering).")

    else:  # split task
        st.subheader("Split into cationic / anionic brines")
        cationic, anionic, split_warnings = split_brine(composition)

        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**Cationic brine**")
            show_composition(cationic, unit)
        with col2:
            st.markdown("**Anionic brine**")
            show_composition(anionic, unit)

        mix_ok = check_equal_mix(composition, cationic, anionic)
        if mix_ok:
            st.success("Equal-mix validation: PASS — mixing 50/50 reproduces the original.")
        else:
            st.error("Equal-mix validation: FAIL — check warnings below.")

        if split_warnings:
            for w in split_warnings:
                st.warning(w)

        st.divider()
        st.subheader(f"Preparation instructions — cationic brine ({volume_l:.3g} L)")
        c_instr, c_warn = prepare_brine_instructions(cationic, volume_l=volume_l)
        for w in c_warn:
            st.warning(w)
        for inst in c_instr:
            st.write(f"- **{inst.salt_name}** ({inst.formula}): **{inst.grams:.2f} g** — {inst.notes}")

        st.subheader(f"Preparation instructions — anionic brine ({volume_l:.3g} L)")
        a_instr, a_warn = prepare_brine_instructions(anionic, volume_l=volume_l)
        for w in a_warn:
            st.warning(w)
        for inst in a_instr:
            st.write(f"- **{inst.salt_name}** ({inst.formula}): **{inst.grams:.2f} g** — {inst.notes}")


if __name__ == "__main__":
    main()
