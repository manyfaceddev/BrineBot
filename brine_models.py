from dataclasses import dataclass, field
from typing import Dict, List

STANDARD_CATIONS: List[str] = ["Na", "Ca", "Mg", "K", "Mn", "Zn", "Fe", "Sr", "Ba"]
STANDARD_ANIONS: List[str] = ["Cl", "SO4", "HCO3", "CO3", "OH", "Br"]

ION_CHARGES = {
    "Na": 1,
    "Ca": 2,
    "Mg": 2,
    "K": 1,
    "Mn": 2,
    "Zn": 2,
    "Fe": 2,
    "Sr": 2,
    "Ba": 2,
    "Li": 1,
    "Cl": -1,
    "OH": -1,
    "HCO3": -1,
    "CO3": -2,
    "Br": -1,
    "SO4": -2,
}

# Molar masses (g/mol) for unit conversion between mg/L and mol/L
ION_MOLAR_MASSES: Dict[str, float] = {
    "Na": 22.99,
    "Ca": 40.08,
    "Mg": 24.31,
    "K": 39.10,
    "Mn": 54.94,
    "Zn": 65.38,
    "Fe": 55.85,
    "Sr": 87.62,
    "Ba": 137.33,
    "Li": 6.94,
    "Cl": 35.45,
    "OH": 17.01,
    "HCO3": 61.02,
    "CO3": 60.01,
    "Br": 79.90,
    "SO4": 96.06,
}

SALT_DATABASE = {
    "NaHCO3 (anhydrous)": {
        "formula": "NaHCO3",
        "cation": "Na",
        "anion": "HCO3",
        "cation_stoich": 1,
        "molar_mass": 84.01,
    },
    "Na2CO3 (anhydrous)": {
        "formula": "Na2CO3",
        "cation": "Na",
        "anion": "CO3",
        "cation_stoich": 2,
        "molar_mass": 105.99,
    },
    "Na2SO4 (anhydrous)": {
        "formula": "Na2SO4",
        "cation": "Na",
        "anion": "SO4",
        "cation_stoich": 2,
        "molar_mass": 142.04,
    },
    "NaCl": {
        "formula": "NaCl",
        "cation": "Na",
        "anion": "Cl",
        "cation_stoich": 1,
        "molar_mass": 58.44,
    },
    "CaCl2 (anhydrous)": {
        "formula": "CaCl2",
        "cation": "Ca",
        "anion": "Cl",
        "cation_stoich": 1,
        "molar_mass": 110.98,
    },
    "CaCl2.2H2O": {
        "formula": "CaCl2.2H2O",
        "cation": "Ca",
        "anion": "Cl",
        "cation_stoich": 1,
        "molar_mass": 147.02,
    },
    "MgCl2.6H2O": {
        "formula": "MgCl2.6H2O",
        "cation": "Mg",
        "anion": "Cl",
        "cation_stoich": 1,
        "molar_mass": 203.30,
    },
    "KCl": {
        "formula": "KCl",
        "cation": "K",
        "anion": "Cl",
        "cation_stoich": 1,
        "molar_mass": 74.55,
    },
    "MnCl2": {
        "formula": "MnCl2",
        "cation": "Mn",
        "anion": "Cl",
        "cation_stoich": 1,
        "molar_mass": 125.84,
    },
    "ZnCl2": {
        "formula": "ZnCl2",
        "cation": "Zn",
        "anion": "Cl",
        "cation_stoich": 1,
        "molar_mass": 136.34,
    },
    "FeCl2": {
        "formula": "FeCl2",
        "cation": "Fe",
        "anion": "Cl",
        "cation_stoich": 1,
        "molar_mass": 126.75,
    },
    "SrCl2.6H2O": {
        "formula": "SrCl2.6H2O",
        "cation": "Sr",
        "anion": "Cl",
        "cation_stoich": 1,
        "molar_mass": 266.62,
    },
    "LiCl": {
        "formula": "LiCl",
        "cation": "Li",
        "anion": "Cl",
        "cation_stoich": 1,
        "molar_mass": 42.39,
    },
    "BaCl2.2H2O": {
        "formula": "BaCl2.2H2O",
        "cation": "Ba",
        "anion": "Cl",
        "cation_stoich": 1,
        "molar_mass": 244.26,
    },
    "NaOH": {
        "formula": "NaOH",
        "cation": "Na",
        "anion": "OH",
        "cation_stoich": 1,
        "molar_mass": 40.00,
    },
    "NaBr": {
        "formula": "NaBr",
        "cation": "Na",
        "anion": "Br",
        "cation_stoich": 1,
        "molar_mass": 102.89,
    },
}

DEFAULT_CATION_SALT = {
    "Na": "NaCl",
    "Ca": "CaCl2.2H2O",
    "Mg": "MgCl2.6H2O",
    "K": "KCl",
    "Sr": "SrCl2.6H2O",
    "Ba": "BaCl2.2H2O",
    "Mn": "MnCl2",
    "Zn": "ZnCl2",
    "Fe": "FeCl2",
    "Li": "LiCl",
}

# Na-based salts used to deliver non-Cl anions
DEFAULT_ANION_SALT: Dict[str, str] = {
    "HCO3": "NaHCO3 (anhydrous)",
    "CO3": "Na2CO3 (anhydrous)",
    "SO4": "Na2SO4 (anhydrous)",
    "OH": "NaOH",
    "Br": "NaBr",
}

AVAILABLE_SALTS = list(SALT_DATABASE.keys())

@dataclass
class BrineComposition:
    cations: Dict[str, float] = field(default_factory=dict)
    anions: Dict[str, float] = field(default_factory=dict)
    source: str = "manual"
    notes: str = ""

    def is_empty(self) -> bool:
        return not self.cations and not self.anions

    def format(self, unit: str = "mol/L") -> str:
        lines = [f"Source: {self.source}"]
        if self.cations:
            lines.append("Cations:")
            for key, value in self.cations.items():
                lines.append(f"  {key}: {value:.4g} {unit}")
        if self.anions:
            lines.append("Anions:")
            for key, value in self.anions.items():
                lines.append(f"  {key}: {value:.4g} {unit}")
        if self.notes:
            lines.append(f"Notes: {self.notes}")
        return "\n".join(lines)

    def __str__(self) -> str:
        return self.format("mol/L")


@dataclass
class SaltInstruction:
    salt_name: str
    formula: str
    grams: float
    notes: str

    def __str__(self) -> str:
        return f"{self.salt_name} ({self.formula}): {self.grams:.2f} g - {self.notes}"
