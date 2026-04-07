import sys

# Guard: detect Streamlit's runtime and bail before argparse fires.
try:
    from streamlit.runtime.scriptrunner import get_script_run_ctx as _get_ctx
    if _get_ctx() is not None:
        import streamlit as st
        st.error("**app.py is the CLI entry point.** Run the Streamlit app instead:\n```\nstreamlit run streamlit_app.py\n```")
        st.stop()
except ImportError:
    pass

import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from input_tools import normalize_manually_entered_composition, parse_uploaded_file
from brine_calculations import prepare_brine_instructions, split_brine, check_equal_mix


def run_cli():
    parser = argparse.ArgumentParser(description="Brine Bot CLI - prepare or split reservoir brines.")
    parser.add_argument("--task", choices=["prepare", "split"], default="prepare", help="Task to run.")
    parser.add_argument("--volume", type=float, default=1.0, help="Volume in liters for preparation instructions.")
    parser.add_argument("--pdf", type=str, help="Path to a PDF or image that contains brine chemistry.")
    parser.add_argument("--cations", type=str, help="Comma-separated cation values, e.g. Na=0.1,Ca=0.02")
    parser.add_argument("--anions", type=str, help="Comma-separated anion values, e.g. Cl=0.2,HCO3=0.01")
    args = parser.parse_args()

    if args.pdf:
        composition = parse_uploaded_file(args.pdf)
    else:
        if not args.cations and not args.anions:
            parser.error("Either --pdf or --cations/--anions must be provided.")
        cations = parse_ion_values(args.cations)
        anions = parse_ion_values(args.anions)
        composition = normalize_manually_entered_composition(cations, anions)

    print("\nBrine composition:\n")
    print(composition)

    if args.task == "prepare":
        instructions, warnings = prepare_brine_instructions(composition, volume_l=args.volume)
        print("\nPreparation Instructions:\n")
        for item in instructions:
            print(item)
        if warnings:
            print("\nWarnings:")
            for w in warnings:
                print("-", w)
    elif args.task == "split":
        cationic, anionic, warnings = split_brine(composition)
        print("\nCationic split brine:\n")
        print(cationic)
        print("\nAnionic split brine:\n")
        print(anionic)
        combined_ok = check_equal_mix(composition, cationic, anionic)
        print(f"\nEqual-mix validation: {'PASS' if combined_ok else 'FAIL'}")
        if warnings:
            print("\nWarnings:")
            for warning in warnings:
                print("-", warning)


def parse_ion_values(value: str | None) -> dict[str, float]:
    if not value:
        return {}
    result = {}
    for token in value.split(","):
        if not token.strip():
            continue
        if "=" not in token:
            raise ValueError(f"Invalid ion input: {token}")
        key, raw = token.split("=", 1)
        result[key.strip()] = float(raw.strip())
    return result


def main():
    run_cli()


if __name__ == "__main__":
    main()
