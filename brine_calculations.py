from typing import Dict, List, Tuple
from brine_models import (
    BrineComposition, SaltInstruction, SALT_DATABASE,
    DEFAULT_CATION_SALT, DEFAULT_ANION_SALT, ION_CHARGES, ION_MOLAR_MASSES,
)


def _ion_equivalents(concentration: float, ion: str) -> float:
    charge = ION_CHARGES.get(ion, 1)
    return abs(charge) * concentration


def mgl_to_moll(ion: str, conc_mgl: float) -> float:
    """Convert mg/L to mol/L for a given ion.
    mg/L ÷ (g/mol × 1000 mg/g) = mol/L
    """
    mw = ION_MOLAR_MASSES.get(ion)
    if mw is None or mw <= 0:
        raise ValueError(f"No molar mass for ion '{ion}'.")
    return conc_mgl / (mw * 1000)


def moll_to_mgl(ion: str, conc_moll: float) -> float:
    """Convert mol/L to mg/L for a given ion."""
    mw = ION_MOLAR_MASSES.get(ion)
    if mw is None or mw <= 0:
        raise ValueError(f"No molar mass for ion '{ion}'.")
    return conc_moll * mw * 1000


def convert_composition_units(
    composition: BrineComposition, to_unit: str
) -> BrineComposition:
    """Return a new BrineComposition with concentrations in *to_unit* ('mol/L' or 'mg/L').

    The source composition is assumed to be in mol/L internally; this is for display only.
    """
    if to_unit not in ("mol/L", "mg/L"):
        raise ValueError(f"Unknown unit '{to_unit}'. Use 'mol/L' or 'mg/L'.")
    if to_unit == "mol/L":
        return composition
    cations = {ion: moll_to_mgl(ion, v) for ion, v in composition.cations.items()}
    anions = {ion: moll_to_mgl(ion, v) for ion, v in composition.anions.items()}
    return BrineComposition(cations=cations, anions=anions,
                            source=composition.source, notes=composition.notes)


def validate_charge_balance(composition: BrineComposition) -> Tuple[bool, float]:
    cation_eq = sum(_ion_equivalents(value, ion) for ion, value in composition.cations.items())
    anion_eq = sum(_ion_equivalents(value, ion) for ion, value in composition.anions.items())
    return abs(cation_eq - anion_eq) < 1e-6, cation_eq - anion_eq


def compute_salt_mass(target_moles_cation: float, salt_key: str) -> float:
    salt = SALT_DATABASE[salt_key]
    if salt["cation_stoich"] <= 0:
        raise ValueError(f"Invalid cation stoichiometry for {salt_key}")
    return target_moles_cation / salt["cation_stoich"] * salt["molar_mass"]


def prepare_brine_instructions(
    composition: BrineComposition, volume_l: float = 1.0
) -> Tuple[List[SaltInstruction], List[str]]:
    """
    Return (instructions, warnings).

    Algorithm:
      1. Non-Cl anions  → paired with Na using DEFAULT_ANION_SALT (NaHCO3, Na2CO3 …)
      2. Non-Na cations → paired with Cl using DEFAULT_CATION_SALT (CaCl2, MgCl2 …)
      3. Remaining Na   → NaCl
      4. Cl balance check: Cl from steps 2+3 must equal target Cl.
    """
    if composition.is_empty():
        raise ValueError("Brine composition is empty.")

    instructions: List[SaltInstruction] = []
    warnings: List[str] = []

    na_target = composition.cations.get("Na", 0.0) * volume_l   # total mol Na required
    na_used = 0.0      # mol Na consumed by Na-anion salts (step 1)
    cl_provided = 0.0  # mol Cl delivered by all salts (steps 2 + 3)

    # ── Step 1: non-Cl anions ────────────────────────────────────────────────
    for anion, conc in composition.anions.items():
        if anion == "Cl":
            continue
        if anion not in DEFAULT_ANION_SALT:
            warnings.append(f"No Na-salt configured for anion '{anion}' — skipped.")
            continue
        salt_key = DEFAULT_ANION_SALT[anion]
        salt = SALT_DATABASE[salt_key]
        moles_anion = conc * volume_l          # 1 anion per formula unit
        moles_salt = moles_anion
        grams = moles_salt * salt["molar_mass"]
        na_consumed = salt["cation_stoich"] * moles_salt
        na_used += na_consumed
        instructions.append(SaltInstruction(
            salt_name=salt_key,
            formula=salt["formula"],
            grams=grams,
            notes=(
                f"Delivers {anion} at {conc:.4g} mol/L in {volume_l:.3g} L "
                f"(uses {na_consumed:.4g} mol Na)."
            ),
        ))

    # ── Step 2: non-Na cations ───────────────────────────────────────────────
    for cation, conc in composition.cations.items():
        if cation == "Na":
            continue
        if cation not in DEFAULT_CATION_SALT:
            warnings.append(f"No default chloride salt for cation '{cation}' — skipped.")
            continue
        salt_key = DEFAULT_CATION_SALT[cation]
        salt = SALT_DATABASE[salt_key]
        moles_cation = conc * volume_l
        moles_salt = moles_cation / salt["cation_stoich"]
        grams = moles_salt * salt["molar_mass"]
        # Cl contributed = cation charge × moles of cation (charge balance within the salt)
        cation_charge = abs(ION_CHARGES.get(cation, 1))
        cl_from_salt = moles_cation * cation_charge
        cl_provided += cl_from_salt
        instructions.append(SaltInstruction(
            salt_name=salt_key,
            formula=salt["formula"],
            grams=grams,
            notes=(
                f"Delivers {cation} at {conc:.4g} mol/L in {volume_l:.3g} L "
                f"(contributes {cl_from_salt:.4g} mol Cl)."
            ),
        ))

    # ── Step 3: remaining Na via NaCl ────────────────────────────────────────
    na_remaining = na_target - na_used
    if na_remaining < -1e-9:
        warnings.append(
            f"Na deficit: need {na_target:.4g} mol Na total but Na-anion salts "
            f"already consume {na_used:.4g} mol. Reduce non-Cl anion concentrations "
            "or increase Na."
        )
        na_remaining = 0.0

    if na_remaining > 1e-9:
        nacl = SALT_DATABASE["NaCl"]
        grams_nacl = na_remaining * nacl["molar_mass"]
        cl_provided += na_remaining          # NaCl: 1 Na → 1 Cl
        instructions.append(SaltInstruction(
            salt_name="NaCl",
            formula="NaCl",
            grams=grams_nacl,
            notes=(
                f"Delivers remaining {na_remaining:.4g} mol Na as NaCl "
                f"(also adds {na_remaining:.4g} mol Cl)."
            ),
        ))

    # ── Step 4: Cl balance check ─────────────────────────────────────────────
    cl_target = composition.anions.get("Cl", 0.0) * volume_l
    cl_delta = cl_provided - cl_target
    if abs(cl_delta) > 1e-6:
        warnings.append(
            f"Cl balance discrepancy: salts deliver {cl_provided:.4g} mol Cl "
            f"but target is {cl_target:.4g} mol (Δ = {cl_delta:+.4g} mol). "
            "This usually means the input brine is not charge-balanced."
        )

    return instructions, warnings


def split_brine(composition: BrineComposition) -> Tuple[BrineComposition, BrineComposition, List[str]]:
    if composition.is_empty():
        raise ValueError("Brine composition is empty.")

    balanced, difference = validate_charge_balance(composition)
    warnings: List[str] = []
    if not balanced:
        warnings.append(f"Original composition is not charge balanced. Delta = {difference:.6g} equivalents per liter.")

    original_na = composition.cations.get("Na", 0.0)
    cationic_composition = BrineComposition(cations={}, anions={}, source="cationic_split")
    anionic_composition = BrineComposition(cations={}, anions={}, source="anionic_split")

    total_positive_excl_na = 0.0
    for ion, conc in composition.cations.items():
        if ion == "Na":
            continue
        cationic_composition.cations[ion] = 2.0 * conc
        total_positive_excl_na += abs(ION_CHARGES.get(ion, 1) * conc)

    cationic_composition.anions["Cl"] = total_positive_excl_na * 2.0
    anionic_composition.cations["Na"] = original_na * 2.0

    for ion, conc in composition.anions.items():
        if ion == "Cl":
            continue
        anionic_composition.anions[ion] = conc * 2.0

    cl_from_cationic = cationic_composition.anions["Cl"]
    cl_target = composition.anions.get("Cl", 0.0) * 2.0
    anionic_cl = cl_target - cl_from_cationic
    if anionic_cl < 0:
        warnings.append(
            "Cationic split requires more chloride than the original chloride concentration. "
            "Check whether the original composition is valid for this split configuration."
        )
        anionic_cl = 0.0
    anionic_composition.anions["Cl"] = anionic_cl

    is_neutral, delta = validate_charge_balance(cationic_composition)
    if not is_neutral:
        warnings.append(f"Cationic split is not charge balanced after the split. Delta = {delta:.6g}.")

    is_neutral, delta = validate_charge_balance(anionic_composition)
    if not is_neutral:
        warnings.append(f"Anionic split is not charge balanced after the split. Delta = {delta:.6g}.")

    return cationic_composition, anionic_composition, warnings


def check_equal_mix(original: BrineComposition, cationic: BrineComposition, anionic: BrineComposition) -> bool:
    if cationic.is_empty() or anionic.is_empty():
        return False

    def average_maps(map_a: Dict[str, float], map_b: Dict[str, float]) -> Dict[str, float]:
        keys = set(map_a) | set(map_b)
        return {key: (map_a.get(key, 0.0) + map_b.get(key, 0.0)) / 2.0 for key in keys}

    combined_cations = average_maps(cationic.cations, anionic.cations)
    combined_anions = average_maps(cationic.anions, anionic.anions)

    def almost_equal(value_a: float, value_b: float, tol: float = 1e-6) -> bool:
        return abs(value_a - value_b) <= tol

    for ion, target in original.cations.items():
        if not almost_equal(combined_cations.get(ion, 0.0), target):
            return False
    for ion, target in original.anions.items():
        if not almost_equal(combined_anions.get(ion, 0.0), target):
            return False
    return True
