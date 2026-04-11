"""Tests covering the Example FW brine calculations and output."""
import pytest
from brine_models import BrineComposition, ION_MOLAR_MASSES, SALT_DATABASE
from brine_calculations import (
    mgl_to_moll,
    prepare_brine_instructions,
    split_brine,
    check_equal_mix,
    validate_charge_balance,
    mix_compositions,
)

# Mirrors SAMPLE_BRINES["Example FW"] in streamlit_app.py
EXAMPLE_FW_MGL = {
    "cations": {"Na": 58695, "K": 4087, "Ca": 34469, "Mg": 2880, "Sr": 2377, "Ba": 28},
    "anions":  {"Cl": 166615, "SO4": 136, "HCO3": 250},
}


@pytest.fixture
def example_fw() -> BrineComposition:
    """Example FW composition converted from mg/L to mol/L (internal units)."""
    cations = {ion: mgl_to_moll(ion, v) for ion, v in EXAMPLE_FW_MGL["cations"].items()}
    anions  = {ion: mgl_to_moll(ion, v) for ion, v in EXAMPLE_FW_MGL["anions"].items()}
    return BrineComposition(cations=cations, anions=anions, source="example_fw")


# ── unit conversion ───────────────────────────────────────────────────────────

class TestMglToMoll:
    @pytest.mark.parametrize("ion,mgl", [
        ("Na",   58695),
        ("K",    4087),
        ("Ca",   34469),
        ("Mg",   2880),
        ("Sr",   2377),
        ("Ba",   28),
        ("Cl",   166615),
        ("SO4",  136),
        ("HCO3", 250),
    ])
    def test_conversion_formula(self, ion, mgl):
        expected = mgl / (ION_MOLAR_MASSES[ion] * 1000)
        assert mgl_to_moll(ion, mgl) == pytest.approx(expected, rel=1e-9)


# ── composition structure ─────────────────────────────────────────────────────

class TestExampleFwComposition:
    def test_has_all_cations(self, example_fw):
        assert set(example_fw.cations) == {"Na", "K", "Ca", "Mg", "Sr", "Ba"}

    def test_has_all_anions(self, example_fw):
        assert set(example_fw.anions) == {"Cl", "SO4", "HCO3"}

    def test_not_empty(self, example_fw):
        assert not example_fw.is_empty()

    def test_all_concentrations_positive(self, example_fw):
        for v in {**example_fw.cations, **example_fw.anions}.values():
            assert v > 0


# ── charge balance ─────────────────────────────────────────────────────────────

class TestChargeBalance:
    def test_example_fw_is_not_charge_balanced(self, example_fw):
        balanced, _ = validate_charge_balance(example_fw)
        assert not balanced

    def test_charge_balance_delta_is_negative(self, example_fw):
        # Anion equivalents exceed cation equivalents for this composition
        _, delta = validate_charge_balance(example_fw)
        assert delta < 0


# ── prepare instructions (1 L) ───────────────────────────────────────────────

class TestPrepareInstructions1L:
    @pytest.fixture
    def by_salt(self, example_fw):
        instr, _ = prepare_brine_instructions(example_fw, volume_l=1.0)
        return {i.salt_name: i for i in instr}

    def test_expected_salts_present(self, by_salt):
        assert set(by_salt) == {
            "Na2SO4 (anhydrous)",
            "NaHCO3 (anhydrous)",
            "KCl",
            "CaCl2.2H2O",
            "MgCl2.6H2O",
            "SrCl2.6H2O",
            "BaCl2.2H2O",
            "NaCl",
        }

    def test_salt_count(self, by_salt):
        assert len(by_salt) == 8

    # Anion-driven salts: moles_salt = moles_anion (1:1 with anion)
    @pytest.mark.parametrize("salt_name,anion,mgl", [
        ("NaHCO3 (anhydrous)", "HCO3", 250),
        ("Na2SO4 (anhydrous)", "SO4",  136),
    ])
    def test_anion_salt_mass_grams(self, by_salt, salt_name, anion, mgl):
        moles_anion = mgl_to_moll(anion, mgl)
        expected_g = moles_anion * SALT_DATABASE[salt_name]["molar_mass"]
        assert by_salt[salt_name].grams == pytest.approx(expected_g, rel=1e-6)

    # Cation-driven salts: moles_salt = moles_cation / cation_stoich
    @pytest.mark.parametrize("salt_name,cation,mgl", [
        ("KCl",        "K",  4087),
        ("CaCl2.2H2O", "Ca", 34469),
        ("MgCl2.6H2O", "Mg", 2880),
        ("SrCl2.6H2O", "Sr", 2377),
        ("BaCl2.2H2O", "Ba", 28),
    ])
    def test_cation_salt_mass_grams(self, by_salt, salt_name, cation, mgl):
        moles_cation = mgl_to_moll(cation, mgl)
        salt = SALT_DATABASE[salt_name]
        expected_g = (moles_cation / salt["cation_stoich"]) * salt["molar_mass"]
        assert by_salt[salt_name].grams == pytest.approx(expected_g, rel=1e-6)

    def test_nacl_mass_grams(self, example_fw, by_salt):
        na_total = example_fw.cations["Na"]
        na_used = (
            SALT_DATABASE["NaHCO3 (anhydrous)"]["cation_stoich"] * example_fw.anions["HCO3"]
            + SALT_DATABASE["Na2SO4 (anhydrous)"]["cation_stoich"] * example_fw.anions["SO4"]
        )
        expected_g = (na_total - na_used) * SALT_DATABASE["NaCl"]["molar_mass"]
        assert by_salt["NaCl"].grams == pytest.approx(expected_g, rel=1e-6)

    def test_all_mg_values_positive(self, by_salt):
        for inst in by_salt.values():
            assert inst.grams * 1000 > 0

    def test_cl_balance_warning_raised(self, example_fw):
        _, warnings = prepare_brine_instructions(example_fw, volume_l=1.0)
        assert any("Cl balance" in w for w in warnings)


# ── volume scaling ────────────────────────────────────────────────────────────

class TestVolumeScaling:
    def test_masses_scale_linearly_with_volume(self, example_fw):
        instr_1, _ = prepare_brine_instructions(example_fw, volume_l=1.0)
        instr_5, _ = prepare_brine_instructions(example_fw, volume_l=5.0)
        by_1 = {i.salt_name: i.grams for i in instr_1}
        by_5 = {i.salt_name: i.grams for i in instr_5}
        for name in by_1:
            assert by_5[name] == pytest.approx(by_1[name] * 5, rel=1e-9)


# ── split brine ───────────────────────────────────────────────────────────────

class TestSplitBrine:
    @pytest.fixture
    def split(self, example_fw):
        cationic, anionic, warnings = split_brine(example_fw)
        return cationic, anionic, warnings

    # ── ion placement ─────────────────────────────────────────────────────────

    def test_cationic_has_na(self, split):
        # NaCl is split equally — cationic gets half
        cationic, _, _ = split
        assert "Na" in cationic.cations
        assert cationic.cations["Na"] > 0

    def test_anionic_has_only_na_as_cation(self, split):
        _, anionic, _ = split
        assert set(anionic.cations) == {"Na"}

    def test_non_na_cations_only_in_cationic(self, example_fw, split):
        cationic, anionic, _ = split
        for ion in example_fw.cations:
            if ion == "Na":
                continue
            assert ion in cationic.cations
            assert ion not in anionic.cations

    def test_non_cl_anions_only_in_anionic(self, example_fw, split):
        cationic, anionic, _ = split
        for ion in example_fw.anions:
            if ion == "Cl":
                continue
            assert ion in anionic.anions
            assert ion not in cationic.anions

    # ── concentrations at 2× ─────────────────────────────────────────────────

    def test_non_na_cation_concentrations_doubled(self, example_fw, split):
        cationic, _, _ = split
        for ion, conc in example_fw.cations.items():
            if ion == "Na":
                continue
            assert cationic.cations[ion] == pytest.approx(conc * 2, rel=1e-9)

    def test_non_cl_anion_concentrations_doubled(self, example_fw, split):
        _, anionic, _ = split
        for ion, conc in example_fw.anions.items():
            if ion == "Cl":
                continue
            assert anionic.anions[ion] == pytest.approx(conc * 2, rel=1e-9)

    # ── NaCl split ────────────────────────────────────────────────────────────

    def test_nacl_split_equally(self, example_fw, split):
        cationic, anionic, _ = split
        from brine_models import SALT_DATABASE, DEFAULT_ANION_SALT
        # Na consumed by anion salts
        na_consumed = sum(
            SALT_DATABASE[DEFAULT_ANION_SALT[ion]]["cation_stoich"] * conc
            for ion, conc in example_fw.anions.items()
            if ion != "Cl" and ion in DEFAULT_ANION_SALT
        )
        na_remaining = example_fw.cations["Na"] - na_consumed
        # Each sub-brine gets na_remaining as NaCl at 2× concentration
        assert cationic.cations["Na"] == pytest.approx(na_remaining, rel=1e-9)

    def test_na_remixes_to_original(self, example_fw, split):
        cationic, anionic, _ = split
        assert (cationic.cations["Na"] + anionic.cations["Na"]) / 2 == pytest.approx(
            example_fw.cations["Na"], rel=1e-9
        )

    # ── charge balance ────────────────────────────────────────────────────────

    def test_cationic_is_charge_balanced(self, split):
        cationic, _, _ = split
        balanced, delta = validate_charge_balance(cationic)
        assert balanced, f"Cationic charge balance delta = {delta:.2e}"

    def test_anionic_is_charge_balanced(self, split):
        _, anionic, _ = split
        balanced, delta = validate_charge_balance(anionic)
        assert balanced, f"Anionic charge balance delta = {delta:.2e}"

    # ── equal-mix validation ──────────────────────────────────────────────────

    def test_equal_mix_recovers_original(self, example_fw, split):
        cationic, anionic, _ = split
        assert check_equal_mix(example_fw, cationic, anionic)

    def test_prep_instructions_nacl_equal(self, example_fw, split):
        # NaCl mass for cationic sub-brine == NaCl mass for anionic sub-brine
        from brine_calculations import prepare_brine_instructions
        cationic, anionic, _ = split
        sub_vol = 0.5
        c_instr, _ = prepare_brine_instructions(cationic, volume_l=sub_vol)
        a_instr, _ = prepare_brine_instructions(anionic,  volume_l=sub_vol)
        nacl_cat = next(i.grams for i in c_instr if i.salt_name == "NaCl")
        nacl_an  = next(i.grams for i in a_instr if i.salt_name == "NaCl")
        assert nacl_cat == pytest.approx(nacl_an, rel=1e-9)


# ── mix_compositions ──────────────────────────────────────────────────────────

# A simple dilute brine for mixing tests
DILUTE_MGL = {
    "cations": {"Na": 1000, "Ca": 500},
    "anions":  {"Cl": 2000},
}


@pytest.fixture
def dilute_brine() -> BrineComposition:
    cations = {ion: mgl_to_moll(ion, v) for ion, v in DILUTE_MGL["cations"].items()}
    anions  = {ion: mgl_to_moll(ion, v) for ion, v in DILUTE_MGL["anions"].items()}
    return BrineComposition(cations=cations, anions=anions, source="dilute")


class TestMixCompositions:
    def test_single_brine_fraction_one_is_identity(self, example_fw):
        mixed = mix_compositions([(example_fw, 1.0)])
        for ion, conc in example_fw.cations.items():
            assert mixed.cations[ion] == pytest.approx(conc, rel=1e-9)
        for ion, conc in example_fw.anions.items():
            assert mixed.anions[ion] == pytest.approx(conc, rel=1e-9)

    def test_fractions_not_summing_to_one_raises(self, example_fw):
        with pytest.raises(ValueError, match="sum to 1.0"):
            mix_compositions([(example_fw, 0.6)])

    def test_two_brine_mix_concentrations(self, example_fw, dilute_brine):
        mixed = mix_compositions([(example_fw, 0.6), (dilute_brine, 0.4)])
        # Na should be 0.6 * fw_Na + 0.4 * dilute_Na
        expected_na = example_fw.cations["Na"] * 0.6 + dilute_brine.cations["Na"] * 0.4
        assert mixed.cations["Na"] == pytest.approx(expected_na, rel=1e-9)

    def test_two_brine_mix_ion_union(self, example_fw, dilute_brine):
        # dilute has no SO4/HCO3/K/Mg/Sr/Ba; mixed should still have them from fw
        mixed = mix_compositions([(example_fw, 0.6), (dilute_brine, 0.4)])
        assert "SO4" in mixed.anions
        assert "HCO3" in mixed.anions
        assert "K" in mixed.cations

    def test_50_50_mix_is_average(self, example_fw, dilute_brine):
        mixed = mix_compositions([(example_fw, 0.5), (dilute_brine, 0.5)])
        expected_na = (example_fw.cations["Na"] + dilute_brine.cations["Na"]) / 2
        assert mixed.cations["Na"] == pytest.approx(expected_na, rel=1e-9)

    def test_three_brine_mix(self, example_fw, dilute_brine):
        brine3 = BrineComposition(
            cations={"Na": 0.05},
            anions={"Cl": 0.05},
            source="b3",
        )
        mixed = mix_compositions([(example_fw, 0.5), (dilute_brine, 0.3), (brine3, 0.2)])
        expected_na = (
            example_fw.cations["Na"] * 0.5
            + dilute_brine.cations["Na"] * 0.3
            + brine3.cations["Na"] * 0.2
        )
        assert mixed.cations["Na"] == pytest.approx(expected_na, rel=1e-9)

    def test_mixed_source_label(self, example_fw, dilute_brine):
        mixed = mix_compositions([(example_fw, 0.5), (dilute_brine, 0.5)])
        assert mixed.source == "mixed"

    def test_mixed_then_split_equal_mix_passes(self, example_fw, dilute_brine):
        mixed = mix_compositions([(example_fw, 0.6), (dilute_brine, 0.4)])
        cationic, anionic, _ = split_brine(mixed)
        # Both sub-brines charge-balanced; equal-mix passes within 1% tolerance
        assert check_equal_mix(mixed, cationic, anionic)
