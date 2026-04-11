import streamlit as st
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from brine_models import STANDARD_CATIONS, STANDARD_ANIONS, ION_MOLAR_MASSES

# Sample brine: SARB FW1 (mg/L)
SAMPLE_BRINES = {
    "Example FW": {
        "cations": {"Na": 58695, "K": 4087, "Ca": 34469, "Mg": 2880, "Sr": 2377, "Ba": 28},
        "anions":  {"Cl": 166615, "SO4": 136, "HCO3": 250},
        "unit": "mg/L",
    },
}
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
    mix_compositions,
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

def build_manual_composition(unit: str, key_prefix: str = ""):
    if not key_prefix:
        st.header("Manual brine composition")

    custom_entries = st.text_input(
        "Add custom ions (comma-separated). Capitalise cations, lowercase anions.",
        value="",
        key=f"{key_prefix}custom_ions",
    )
    cation_options, anion_options = make_dropdown_options(custom_entries)

    step = 1.0 if unit == "mg/L" else 0.01
    fmt = "%.2f" if unit == "mg/L" else "%.4f"

    st.markdown("**Cations**")
    cations_moll = {}
    for ion in cation_options:
        if ion and ion[0].isupper():
            key = f"{key_prefix}cat_{ion}"
            if key not in st.session_state:
                st.session_state[key] = 0.0
            raw = st.number_input(
                f"{ion} ({unit})", min_value=0.0, step=step, format=fmt, key=key
            )
            if raw > 0:
                cations_moll[ion] = _parse_manual_conc(ion, raw, unit)

    st.markdown("**Anions**")
    anions_moll = {}
    for ion in anion_options:
        if ion:
            key = f"{key_prefix}an_{ion}"
            if key not in st.session_state:
                st.session_state[key] = 0.0
            raw = st.number_input(
                f"{ion} ({unit})", min_value=0.0, step=step, format=fmt, key=key
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
    input_type = st.sidebar.radio("Input type", ["Manual entry", "Upload PDF / image"])

    # ── sample loader ─────────────────────────────────────────────────────────
    st.sidebar.divider()
    st.sidebar.markdown("**Load sample brine**")
    sample_name = st.sidebar.selectbox("Sample", ["— none —"] + list(SAMPLE_BRINES.keys()), label_visibility="collapsed")
    if st.sidebar.button("Load sample"):
        sample = SAMPLE_BRINES[sample_name]
        for ion, val in sample["cations"].items():
            st.session_state[f"cat_{ion}"] = float(val)
        for ion, val in sample["anions"].items():
            st.session_state[f"an_{ion}"] = float(val)
        st.session_state["unit"] = sample["unit"]
        st.rerun()

    # ── composition input ─────────────────────────────────────────────────────
    composition = None

    unit = st.radio("Concentration unit", ["mg/L", "mol/L"], horizontal=True, key="unit")

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
                st.write(f"- **{inst.salt_name}** ({inst.formula}): **{inst.grams * 1000:.2f} mg** — {inst.notes}")
        else:
            st.info("No salts required (empty composition after filtering).")

    else:  # split task
        st.subheader("Split into cationic / anionic brines")

        # ── brine mixing ──────────────────────────────────────────────────────
        n_brines = st.radio(
            "Number of brines to mix", [1, 2, 3], horizontal=True, key="n_brines"
        )

        brines_with_fractions: list[tuple] = []

        if n_brines == 1:
            brines_with_fractions = [(composition, 1.0)]
        else:
            frac1 = st.number_input(
                "Brine 1 fraction", min_value=0.0, max_value=1.0,
                value=0.5 if n_brines == 2 else 0.34,
                step=0.01, format="%.2f", key="frac1",
            )
            brines_with_fractions.append((composition, frac1))

            with st.expander("Brine 2", expanded=True):
                frac2 = st.number_input(
                    "Brine 2 fraction", min_value=0.0, max_value=1.0,
                    value=round(1.0 - frac1, 2) if n_brines == 2 else 0.33,
                    step=0.01, format="%.2f", key="frac2",
                )
                comp2 = build_manual_composition(unit, key_prefix="b2_")
            brines_with_fractions.append((comp2, frac2))

            if n_brines == 3:
                with st.expander("Brine 3", expanded=True):
                    frac3 = st.number_input(
                        "Brine 3 fraction", min_value=0.0, max_value=1.0,
                        value=round(max(0.0, 1.0 - frac1 - frac2), 2),
                        step=0.01, format="%.2f", key="frac3",
                    )
                    comp3 = build_manual_composition(unit, key_prefix="b3_")
                brines_with_fractions.append((comp3, frac3))

            total_frac = sum(f for _, f in brines_with_fractions)
            if abs(total_frac - 1.0) > 1e-4:
                st.error(f"Fractions must sum to 1.0 — currently {total_frac:.4g}. Adjust before proceeding.")
                return

            mixed = mix_compositions(brines_with_fractions)
            st.divider()
            st.subheader("Mixed composition")
            show_composition(mixed, unit)
            m_balanced, m_delta = validate_charge_balance(mixed)
            if m_balanced:
                st.success("Mixed brine charge balance: OK")
            else:
                st.warning(f"Mixed brine charge balance: unbalanced (Δ = {m_delta:+.4g} eq/L).")
            composition = mixed  # split the mixed brine

        st.divider()
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

        sub_vol = volume_l / 2
        st.divider()
        st.subheader(
            f"Preparation instructions — cationic brine "
            f"(prepare {sub_vol:.3g} L at 2× concentration)"
        )
        c_instr, c_warn = prepare_brine_instructions(cationic, volume_l=sub_vol)
        for w in c_warn:
            st.warning(w)
        for inst in c_instr:
            st.write(f"- **{inst.salt_name}** ({inst.formula}): **{inst.grams * 1000:.2f} mg** — {inst.notes}")

        st.subheader(
            f"Preparation instructions — anionic brine "
            f"(prepare {sub_vol:.3g} L at 2× concentration)"
        )
        a_instr, a_warn = prepare_brine_instructions(anionic, volume_l=sub_vol)
        for w in a_warn:
            st.warning(w)
        for inst in a_instr:
            st.write(f"- **{inst.salt_name}** ({inst.formula}): **{inst.grams * 1000:.2f} mg** — {inst.notes}")


if __name__ == "__main__":
    main()
