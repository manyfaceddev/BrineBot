import sys

# Guard: detect Streamlit's runtime and bail before argparse fires.
import os as _os, sys as _sys
try:
    _stderr, _sys.stderr = _sys.stderr, open(_os.devnull, "w")
    from streamlit.runtime.scriptrunner import get_script_run_ctx as _get_ctx
    _sys.stderr = _stderr
    if _get_ctx() is not None:
        import streamlit as st
        st.error("**app.py is the CLI entry point.** Run the Streamlit app instead:\n```\nstreamlit run streamlit_app.py\n```")
        st.stop()
except ImportError:
    _sys.stderr = _stderr  # type: ignore[possibly-undefined]

import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from brine_models import BrineComposition
from input_tools import normalize_manually_entered_composition, parse_uploaded_file
from brine_calculations import (
    prepare_brine_instructions,
    split_brine,
    check_equal_mix,
    validate_charge_balance,
    mgl_to_moll,
    mix_compositions,
    convert_composition_units,
)


# ── formatting helpers ────────────────────────────────────────────────────────

def _fmt_instructions(instructions, warnings, volume_l: float):
    if warnings:
        print("  Warnings:")
        for w in warnings:
            print(f"    ! {w}")
    if instructions:
        for inst in instructions:
            print(f"  - {inst.salt_name} ({inst.formula}): {inst.grams * 1000:.2f} mg")
    else:
        print("  (no salts required)")


def _print_composition(composition: BrineComposition, unit: str):
    if unit == "mg/L":
        display = convert_composition_units(composition, "mg/L")
        print(display.format("mg/L"))
    else:
        print(str(composition))


def _print_charge_balance(composition: BrineComposition):
    balanced, delta = validate_charge_balance(composition)
    if balanced:
        print("  Charge balance: OK")
    else:
        print(f"  Charge balance: UNBALANCED (Δ = {delta:+.4g} eq/L)")


# ── argument parsing ──────────────────────────────────────────────────────────

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Brine Bot CLI — prepare or split reservoir brines.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Prepare 1L from mg/L values (default unit):
  python app.py --task prepare \\
    --cations "Na=58695,K=4087,Ca=34469,Mg=2880,Sr=2377,Ba=28" \\
    --anions  "Cl=166615,SO4=136,HCO3=250"

  # Split a single brine:
  python app.py --task split \\
    --cations "Na=58695,K=4087,Ca=34469,Mg=2880,Sr=2377,Ba=28" \\
    --anions  "Cl=166615,SO4=136,HCO3=250"

  # Split a 60/40 mix of two brines (mg/L):
  python app.py --task split \\
    --cations "Na=58695,Ca=34469" --anions "Cl=166615" --fraction 0.6 \\
    --brine2-cations "Na=10000,Ca=5000" --brine2-anions "Cl=30000" --brine2-fraction 0.4
""",
    )
    p.add_argument("--task", choices=["prepare", "split"], default="prepare")
    p.add_argument("--volume", type=float, default=1.0,
                   help="Preparation volume in litres (default 1.0).")
    p.add_argument("--unit", choices=["mg/L", "mol/L"], default="mg/L",
                   help="Concentration unit for all ion inputs (default mg/L).")

    # Brine 1
    p.add_argument("--pdf", help="Path to PDF/image with brine chemistry (brine 1).")
    p.add_argument("--cations", help='Brine 1 cations, e.g. "Na=58695,Ca=34469"')
    p.add_argument("--anions",  help='Brine 1 anions,  e.g. "Cl=166615,HCO3=250"')
    p.add_argument("--fraction", type=float, default=None,
                   help="Volumetric fraction for brine 1 (only needed when mixing).")

    # Brine 2
    p.add_argument("--brine2-cations", dest="brine2_cations",
                   help='Brine 2 cations, e.g. "Na=10000,Ca=5000"')
    p.add_argument("--brine2-anions",  dest="brine2_anions",
                   help='Brine 2 anions,  e.g. "Cl=30000"')
    p.add_argument("--brine2-fraction", dest="brine2_fraction", type=float, default=None)

    # Brine 3
    p.add_argument("--brine3-cations", dest="brine3_cations")
    p.add_argument("--brine3-anions",  dest="brine3_anions")
    p.add_argument("--brine3-fraction", dest="brine3_fraction", type=float, default=None)

    return p


# ── composition builder ───────────────────────────────────────────────────────

def _composition_from_args(cations_str, anions_str, unit: str) -> BrineComposition:
    raw_cations = _parse_ion_values(cations_str)
    raw_anions  = _parse_ion_values(anions_str)
    if unit == "mg/L":
        raw_cations = {ion: mgl_to_moll(ion, v) for ion, v in raw_cations.items()}
        raw_anions  = {ion: mgl_to_moll(ion, v) for ion, v in raw_anions.items()}
    return normalize_manually_entered_composition(raw_cations, raw_anions)


def _parse_ion_values(value: str | None) -> dict[str, float]:
    if not value:
        return {}
    result = {}
    for token in value.split(","):
        token = token.strip()
        if not token:
            continue
        if "=" not in token:
            raise ValueError(f"Invalid ion token: '{token}'. Expected format Ion=value.")
        key, raw = token.split("=", 1)
        result[key.strip()] = float(raw.strip())
    return result


# ── main ──────────────────────────────────────────────────────────────────────

def run_cli():
    parser = _build_parser()
    args = parser.parse_args()

    # ── build brine 1 ─────────────────────────────────────────────────────────
    if args.pdf:
        comp1 = parse_uploaded_file(args.pdf)
    else:
        if not args.cations and not args.anions:
            parser.error("Provide --pdf or --cations / --anions.")
        comp1 = _composition_from_args(args.cations, args.anions, args.unit)

    # ── optional additional brines for mixing ─────────────────────────────────
    extra_brines: list[tuple[BrineComposition, float]] = []
    if args.brine2_cations or args.brine2_anions:
        if args.brine2_fraction is None:
            parser.error("--brine2-fraction is required when --brine2-cations/anions is given.")
        extra_brines.append((
            _composition_from_args(args.brine2_cations, args.brine2_anions, args.unit),
            args.brine2_fraction,
        ))
    if args.brine3_cations or args.brine3_anions:
        if args.brine3_fraction is None:
            parser.error("--brine3-fraction is required when --brine3-cations/anions is given.")
        extra_brines.append((
            _composition_from_args(args.brine3_cations, args.brine3_anions, args.unit),
            args.brine3_fraction,
        ))

    if extra_brines:
        given_extra = sum(f for _, f in extra_brines)
        frac1 = args.fraction if args.fraction is not None else round(1.0 - given_extra, 10)
        all_brines = [(comp1, frac1)] + extra_brines
        total = sum(f for _, f in all_brines)
        if abs(total - 1.0) > 1e-6:
            parser.error(f"Mixing fractions must sum to 1.0 (got {total:.6g}).")
        composition = mix_compositions(all_brines)
        print(f"\nMixed composition ({len(all_brines)} brines):\n")
        _print_composition(composition, args.unit)
        _print_charge_balance(composition)
    else:
        composition = comp1
        print("\nBrine composition:\n")
        _print_composition(composition, args.unit)
        _print_charge_balance(composition)

    print()

    # ── task ──────────────────────────────────────────────────────────────────
    if args.task == "prepare":
        print(f"Preparation instructions — {args.volume:.3g} L:\n")
        instructions, warnings = prepare_brine_instructions(composition, volume_l=args.volume)
        _fmt_instructions(instructions, warnings, args.volume)

    else:  # split
        cationic, anionic, split_warnings = split_brine(composition)

        print("Cationic brine:\n")
        _print_composition(cationic, args.unit)
        _print_charge_balance(cationic)

        print("\nAnionic brine:\n")
        _print_composition(anionic, args.unit)
        _print_charge_balance(anionic)

        mix_ok = check_equal_mix(composition, cationic, anionic)
        print(f"\nEqual-mix validation: {'PASS' if mix_ok else 'FAIL'}")

        if split_warnings:
            print("\nWarnings:")
            for w in split_warnings:
                print(f"  ! {w}")

        sub_vol = args.volume / 2
        print(f"\nPreparation instructions — cationic brine (prepare {sub_vol:.3g} L at 2×):\n")
        c_instr, c_warn = prepare_brine_instructions(cationic, volume_l=sub_vol)
        _fmt_instructions(c_instr, c_warn, sub_vol)

        print(f"\nPreparation instructions — anionic brine (prepare {sub_vol:.3g} L at 2×):\n")
        a_instr, a_warn = prepare_brine_instructions(anionic, volume_l=sub_vol)
        _fmt_instructions(a_instr, a_warn, sub_vol)


def main():
    run_cli()


if __name__ == "__main__":
    main()
