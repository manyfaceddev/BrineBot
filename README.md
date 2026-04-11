# BrineBot

A tool for preparing and splitting reservoir brines in the laboratory. Given ion concentrations, BrineBot calculates the masses of reagent-grade salts to weigh out, and — for compatibility flooding tests — how to split a mixed brine into separate cationic and anionic stock solutions.

Available as a **Streamlit web app** (`streamlit_app.py`) and a **command-line tool** (`app.py`).

---

## Table of contents

1. [Quick start](#quick-start)
2. [File overview](#file-overview)
3. [Unit conventions](#unit-conventions)
4. [Molar masses](#molar-masses)
5. [Salt database](#salt-database)
6. [Charge balance](#charge-balance)
7. [Task: Prepare brine](#task-prepare-brine)
8. [Task: Split brine](#task-split-brine)
9. [Brine mixing](#brine-mixing)
10. [Command-line interface](#command-line-interface)
11. [Running tests](#running-tests)

---

## Quick start

```bash
pip install -r requirements.txt

# Streamlit app
streamlit run streamlit_app.py

# CLI — prepare 1 L from mg/L values
python app.py --task prepare \
  --cations "Na=58695,K=4087,Ca=34469,Mg=2880,Sr=2377,Ba=28" \
  --anions  "Cl=166615,SO4=136,HCO3=250"

# CLI — split a brine (produces 0.5 L of each sub-brine → 1 L mixed)
python app.py --task split \
  --cations "Na=58695,K=4087,Ca=34469,Mg=2880,Sr=2377,Ba=28" \
  --anions  "Cl=166615,SO4=136,HCO3=250"
```

---

## File overview

| File | Purpose |
|---|---|
| `streamlit_app.py` | Streamlit UI — manual entry, unit toggle, prepare & split tasks |
| `app.py` | CLI entry point |
| `brine_models.py` | Ion charges, molar masses, salt database, default salt mappings |
| `brine_calculations.py` | Core maths — unit conversion, charge balance, prepare, split, mix |
| `input_tools.py` | Manual composition normalisation; PDF/image parsing placeholder |
| `test_example_fw.py` | pytest test suite |
| `requirements.txt` | Python dependencies |

---

## Unit conventions

Concentrations are entered and displayed in **mg/L** by default. All internal calculations use **mol/L**.

### mg/L → mol/L

```
C [mol/L] = C [mg/L] / ( M [g/mol] × 1000 [mg/g] )
```

**Example — sodium at 58 695 mg/L:**

```
C(Na) = 58 695 / (22.99 × 1000) = 2.553 mol/L
```

### mol/L → mg/L

```
C [mg/L] = C [mol/L] × M [g/mol] × 1000 [mg/g]
```

**Example — chloride at 4.700 mol/L:**

```
C(Cl) = 4.700 × 35.45 × 1000 = 166 615 mg/L
```

---

## Molar masses

The molar mass of an ion is the sum of the standard atomic weights of its constituent atoms. Values used in BrineBot are consistent with IUPAC 2021 standard atomic weights.

### Ions

| Ion | Formula | Composition | Molar mass (g/mol) | Charge |
|---|---|---|---|---|
| Sodium | Na⁺ | Na | 22.99 | +1 |
| Potassium | K⁺ | K | 39.10 | +1 |
| Calcium | Ca²⁺ | Ca | 40.08 | +2 |
| Magnesium | Mg²⁺ | Mg | 24.31 | +2 |
| Strontium | Sr²⁺ | Sr | 87.62 | +2 |
| Barium | Ba²⁺ | Ba | 137.33 | +2 |
| Iron(II) | Fe²⁺ | Fe | 55.85 | +2 |
| Manganese | Mn²⁺ | Mn | 54.94 | +2 |
| Zinc | Zn²⁺ | Zn | 65.38 | +2 |
| Lithium | Li⁺ | Li | 6.94 | +1 |
| Chloride | Cl⁻ | Cl | 35.45 | −1 |
| Sulphate | SO₄²⁻ | S + 4O = 32.07 + 4×16.00 | 96.06 | −2 |
| Bicarbonate | HCO₃⁻ | H + C + 3O = 1.008 + 12.01 + 3×16.00 | 61.02 | −1 |
| Carbonate | CO₃²⁻ | C + 3O = 12.01 + 3×16.00 | 60.01 | −2 |
| Hydroxide | OH⁻ | O + H = 16.00 + 1.008 | 17.01 | −1 |
| Bromide | Br⁻ | Br | 79.90 | −1 |

### Salts

The molar mass of a salt is computed from its molecular formula, including water of crystallisation.

**Example — CaCl₂·2H₂O:**

```
M = M(Ca) + 2×M(Cl) + 2×M(H₂O)
  = 40.08 + 2×35.45 + 2×(2×1.008 + 16.00)
  = 40.08 + 70.90 + 2×18.016
  = 40.08 + 70.90 + 36.03
  = 147.01 g/mol  (BrineBot uses 147.02)
```

**Example — Na₂SO₄:**

```
M = 2×M(Na) + M(S) + 4×M(O)
  = 2×22.99 + 32.07 + 4×16.00
  = 45.98 + 32.07 + 64.00
  = 142.05 g/mol  (BrineBot uses 142.04)
```

---

## Salt database

BrineBot maps each ion to a default laboratory salt. Multiple hydration states are available for calcium chloride.

| Salt | Formula | Molar mass (g/mol) | Cation | Anion | Na stoich |
|---|---|---|---|---|---|
| Sodium chloride | NaCl | 58.44 | Na | Cl | 1 |
| Sodium bicarbonate | NaHCO₃ | 84.01 | Na | HCO₃ | 1 |
| Sodium carbonate | Na₂CO₃ | 105.99 | Na | CO₃ | 2 |
| Sodium sulphate | Na₂SO₄ | 142.04 | Na | SO₄ | 2 |
| Sodium hydroxide | NaOH | 40.00 | Na | OH | 1 |
| Sodium bromide | NaBr | 102.89 | Na | Br | 1 |
| Calcium chloride (anhy.) | CaCl₂ | 110.98 | Ca | Cl | — |
| Calcium chloride dihydrate | CaCl₂·2H₂O | 147.02 | Ca | Cl | — |
| Magnesium chloride hexahydrate | MgCl₂·6H₂O | 203.30 | Mg | Cl | — |
| Potassium chloride | KCl | 74.55 | K | Cl | — |
| Strontium chloride hexahydrate | SrCl₂·6H₂O | 266.62 | Sr | Cl | — |
| Barium chloride dihydrate | BaCl₂·2H₂O | 244.26 | Ba | Cl | — |
| Lithium chloride | LiCl | 42.39 | Li | Cl | — |
| Manganese chloride | MnCl₂ | 125.84 | Mn | Cl | — |
| Zinc chloride | ZnCl₂ | 136.34 | Zn | Cl | — |
| Iron(II) chloride | FeCl₂ | 126.75 | Fe | Cl | — |

Default mappings: non-Cl anions use their Na-salt; non-Na cations use their Cl-salt; residual Na uses NaCl.

---

## Charge balance

The charge balance verifies electrical neutrality:

```
Δ [eq/L] = Σ ( z_i × C_i )  [cations]  −  Σ ( |z_j| × C_j )  [anions]
```

where z is the ionic charge and C is the concentration in mol/L.

- **Δ = 0** — perfectly balanced.
- **Δ < 0** — excess anion equivalents; common in field samples due to analytical uncertainty.
- **Δ > 0** — excess cation equivalents.

Charge imbalances of a few percent are normal for measured brine analyses. BrineBot reports Δ and continues; it does not modify the input to force balance.

---

## Task: Prepare brine

Given a brine composition and preparation volume V (litres), BrineBot returns the mass of each salt to dissolve.

### Algorithm

**Step 1 — non-Cl anions via Na-salts**

For each anion A ≠ Cl, select the default Na-salt and calculate:

```
n_A     = C_A × V                       [mol, total moles of anion A]
n_salt  = n_A                            [mol, 1 anion per formula unit]
m_salt  = n_salt × M_salt               [g]
Na_consumed += stoich_Na × n_salt       [mol Na used]
```

`stoich_Na` is the number of Na per formula unit: 1 for NaHCO₃ / NaOH / NaBr, 2 for Na₂CO₃ / Na₂SO₄.

**Step 2 — non-Na cations via Cl-salts**

For each cation X ≠ Na:

```
n_X     = C_X × V                       [mol]
n_salt  = n_X / stoich_X                [mol, stoich_X = 1 for all database entries]
m_salt  = n_salt × M_salt               [g]
Cl_provided += z_X × n_X               [mol Cl from this salt]
```

**Step 3 — remaining Na via NaCl**

```
Na_remaining = C_Na × V − Na_consumed
m_NaCl       = Na_remaining × M(NaCl)   [g]
Cl_provided += Na_remaining             [mol]
```

**Step 4 — Cl balance check**

```
Cl_deficit = Cl_provided − C_Cl × V    [mol]
```

A non-zero deficit means the brine is not charge-balanced; it is reported as a warning.

### Numerical example

Composition (mol/L): Na = 2.553, Ca = 0.860, SO₄ = 0.00173, Cl = 4.700 — V = 1 L.

| Step | Salt | n (mol) | m (mg) |
|---|---|---|---|
| 1 — SO₄ | Na₂SO₄ | 0.001730 | 245.7 |
| 2 — Ca | CaCl₂·2H₂O | 0.8600 | 126 437 |
| 3 — Na | NaCl | 2.553 − 2×0.001730 = 2.550 | 149 013 |

---

## Task: Split brine

For compatibility flooding tests a brine is divided into a **cationic stock** and an **anionic stock**, each prepared at **2× concentration**. Combining 500 mL of each in a 1 L vessel reproduces the target brine at 1×.

### Why 2×?

```
C_final = C_sub × V_sub / V_total = 2C × 0.5 / 1.0 = C   ✓
```

Consequence: **the mass weighed into each 500 mL sub-brine equals the mass required to prepare 1 L of the target brine at 1×**. The `--volume` / preparation volume parameter always refers to the **final mixed brine volume**; each sub-brine is prepared in V/2.

### Split algorithm

**Step 1 — non-Cl anions → anionic stock**

Each non-Cl anion is delivered to the anionic stock via its Na-salt (Na₂SO₄, NaHCO₃ …). The Na consumed is tracked:

```
Na_consumed = Σ  stoich_Na(salt_A) × C_A     [mol/L at 1×]
```

**Step 2 — non-Na cations → cationic stock**

Each non-Na cation is delivered to the cationic stock via its chloride salt.

**Step 3 — remaining Na → NaCl, split equally**

```
Na_remaining = C_Na − Na_consumed
NaCl per stock = Na_remaining / 2             [mol/L at 1×, as NaCl]
```

Both stocks receive the same NaCl addition, so both contain Na and are individually charge-balanced.

**Step 4 — Cl by charge balance**

Cl is not weighed separately; it is delivered by the chloride salts (step 2) and NaCl (step 3). At 2× sub-brine concentration, charge balance gives:

```
Cl_cationic = Na_remaining + 2 × Σ( z_X × C_X )   for non-Na cations
Cl_anionic  = Na_remaining
```

Both sub-brines are electrically neutral by construction.

### Sub-brine compositions at 2×

| Ion | Cationic stock | Anionic stock |
|---|---|---|
| Na⁺ | Na_remaining | C_Na + Na_consumed |
| Non-Na cations | 2 × C_X | — |
| Cl⁻ | Na_remaining + 2 × non-Na cation eq | Na_remaining |
| Non-Cl anions | — | 2 × C_A |

Averaging each sub-brine 50:50 returns the original 1× concentration for every ion (exactly for all ions except Cl when Δ ≠ 0).

### Cl deficit in charge-imbalanced brines

If the input brine has charge imbalance Δ [eq/L], the remixed Cl will differ from the original by:

```
ΔCl_remixed [mg/L] = Δ [eq/L] × M(Cl) [g/mol] × 1000 [mg/g]
```

This is mathematically unavoidable — both sub-brines must be charge-balanced, so any deficit in the input is absorbed by the Cl balance. BrineBot reports this deficit as a single warning. It is **not** corrected, as the deficit reflects genuine analytical uncertainty in the original brine composition.

---

## Brine mixing

Before splitting, BrineBot can blend 2 or 3 brines by volumetric fraction. The fractions must sum to 1.0:

```
Σ f_i = 1.0
```

The mixed concentration for each ion is the weighted sum:

```
C_ion = Σ f_i × C_ion_i
```

Ions absent from a given brine contribute zero to the sum. The mixed brine is then split using the algorithm above.

**Example — 50:50 blend:**

```
C_Na_mixed = 0.5 × C_Na_brine1 + 0.5 × C_Na_brine2
           = 0.5 × 58 695 + 0.5 × 13 300
           = 35 997.5 mg/L
```

---

## Command-line interface

```
python app.py [--task {prepare,split}]
              [--volume LITRES]
              [--unit {mg/L,mol/L}]
              [--cations "Ion=value,..."]
              [--anions  "Ion=value,..."]
              [--fraction F]
              [--brine2-cations "..."] [--brine2-anions "..."] [--brine2-fraction F]
              [--brine3-cations "..."] [--brine3-anions "..."] [--brine3-fraction F]
```

| Flag | Default | Description |
|---|---|---|
| `--task` | `prepare` | `prepare` or `split` |
| `--volume` | `1.0` | Final brine volume in litres |
| `--unit` | `mg/L` | Concentration unit for all ion inputs |
| `--cations` | — | Comma-separated `Ion=value` pairs for brine 1 |
| `--anions` | — | Comma-separated `Ion=value` pairs for brine 1 |
| `--fraction` | auto | Volumetric fraction for brine 1 (derived if omitted) |
| `--brine2-*` | — | Same as above for a second brine |
| `--brine3-*` | — | Same as above for a third brine |

### Examples

```bash
# Prepare 2 L of Example FW
python app.py --task prepare --volume 2.0 \
  --cations "Na=58695,K=4087,Ca=34469,Mg=2880,Sr=2377,Ba=28" \
  --anions  "Cl=166615,SO4=136,HCO3=250"

# Split Example FW — each sub-brine prepared in 0.5 L (1 L final)
python app.py --task split \
  --cations "Na=58695,K=4087,Ca=34469,Mg=2880,Sr=2377,Ba=28" \
  --anions  "Cl=166615,SO4=136,HCO3=250"

# Split a 60:40 blend of two brines
python app.py --task split \
  --cations "Na=58695,Ca=34469" --anions "Cl=166615,SO4=136" --fraction 0.6 \
  --brine2-cations "Na=13300,Ca=540,Mg=1660,K=490,Ba=0.1,Sr=10" \
  --brine2-anions  "Cl=24280,SO4=3190" --brine2-fraction 0.4
```

---

## Running tests

```bash
python -m pytest test_example_fw.py -v
```

The test suite (48 tests) covers:

- **Unit conversion** — mg/L ↔ mol/L for all 9 ions in Example FW
- **Composition structure** — ion presence, positivity, non-empty check
- **Charge balance** — unbalanced flag and delta sign for Example FW
- **Prepare instructions** — correct salt set, anion-driven masses, cation-driven masses, NaCl residual, linear volume scaling, Cl balance warning
- **Split algorithm** — ion placement in each stock, non-Na cations at 2×, non-Cl anions at 2×, equal NaCl split, Na remix identity, charge balance of both sub-brines, equal-mix validation (1% tolerance), NaCl mass equality across stocks
- **Mixing** — identity (fraction = 1), invalid fractions, two- and three-brine blends, ion union, mixed→split→equal-mix round-trip
