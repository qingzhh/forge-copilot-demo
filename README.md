# ForgeCopilot — Die Setup Assistant for 18,000-t Forging Presses

**Meta Global AI Developer Hackathon · Track: Push the Frontier (Manufacturing)**

Setting up dies on an 18,000-ton forging press is experience-driven
trial-and-error. For every new die setup, an operator must choose a template
thickness and lateral/longitudinal shims; if the first forged piece is off,
the crew readjusts and tries again. Every failed first piece costs billet
material, furnace energy, press time — and the knowledge of *what worked*
usually stays in the heads of a few senior operators.

ForgeCopilot turns that tacit knowledge into a data loop that runs **on the
shop floor, fully offline**:

```text
master data → setup job → recommendation (theory + history correction)
           → first-piece feedback → sample grading → success-rate tracking
           → better recommendations
```

## What is in this repository

A working, production-proven desktop application (this is the sanitized
public edition — see *Data & privacy* below):

- **Master data management** — product processes, die versions, die seats,
  blocks, base plates, compensation rules
- **Explainable recommendations** — `recommendation = base theoretical value
  + history correction`, where the correction is learned from graded
  historical cases (no black box; every number can be traced)
- **First-piece feedback & readjustment records** — actual shims, measured
  offsets, pass/fail, defect types, append-only readjustment trail
- **Sample grading (A/B/C)** — only trustworthy samples teach the engine
- **Success-rate analytics** — template / X-shim / Y-shim first-piece success
  rates, all-time and monthly, with trend chart
- **Excel / CSV import & export** — imports the legacy factory workbook
  (English or Chinese sheet names) and curated history CSVs
- **Bilingual UI** — English by default, switchable to Chinese at runtime
  (Language menu); the choice persists across restarts
- **Offline-first** — Python + tkinter + SQLite, **zero third-party
  dependencies**, packaged as a portable exe for the engineering PC

## Field results (production deployment)

The production system this demo is derived from has accumulated **261
curated setup records**. First-piece success rates of the current
formula + history-correction engine (success = |actual − recommended| ≤ 1):

| Direction | Success rate |
|---|---|
| Template thickness | **20.7%** |
| X shim (lateral) | **47.9%** |
| Y shim (longitudinal) | **78.2%** |

The template direction is wrong four times out of five. That is exactly the
gap an AI copilot should close — and it is measurable, which makes it a
perfect hackathon target: **raise first-piece success, prove it on data.**

## The hackathon build: from calculator to copilot

During the hackathon we extend this working core with Meta AI tooling,
keeping the offline-first architecture (factory PCs have no internet;
data syncs when a connection is available):

1. **Muse Spark agent for case-based setup reasoning** — instead of a
   median correction, the agent retrieves the most similar historical
   setups, reasons over die state, regrind history, guide clearance and
   feedback, and returns a recommendation *with an explanation an operator
   can challenge*.
2. **SAM 3.1 for photo-based measurement** — segment photos of the die and
   the first piece to assist guide-clearance checks and template contact
   inspection.
3. **Muse Image for annotated setup guidance** — generate visual setup
   sheets that mark exactly which shims to change and by how much.
4. **Offline core stays authoritative** — the AI layer advises; the proven
   offline workflow, grading rules and audit trail remain the system of
   record.

## Quickstart

```bash
# 1. (optional) generate the bundled synthetic demo dataset
python scripts/generate_demo_data.py

# 2. run the app
python app/main.py

# 3. headless self-check
python app/main.py --self-check
```

Requires Python 3.10+. No packages to install.

To build the portable Windows bundle: `scripts\build_portable_exe.bat`
(PyInstaller, onedir).

## Repository layout

```text
app/                 application code (UI, services, importer, i18n)
db/schema.sql        SQLite schema
docs/                design docs + user guide
scripts/             init / validation / smoke test / demo data / packaging
sample_data/         generated demo history CSV (after running the generator)
```

## Data & privacy

This public edition is **sanitized**:

- No real production database, part numbers, or company data is included.
- All bundled/generated data is **synthetic** (see
  `scripts/generate_demo_data.py`) and merely mimics the shape of real
  setup work.
- The field results quoted above are aggregate statistics only.
- The author's personal name, local paths and the original Chinese workbook
  identifiers were removed or generalized. (Legacy Chinese Excel sheet names
  are still accepted by the importer for backward compatibility.)

## Design docs

- [01 - System Architecture](docs/01-architecture.md)
- [02 - Desktop UI Flow](docs/02-ui-flow.md)
- [03 - Recommendation & Import Design](docs/03-recommendation-and-import.md)
- [04 - Testing & Acceptance Strategy](docs/04-testing.md)
- [05 - Packaging & Deployment](docs/05-packaging.md)
- [User Guide](docs/USER_GUIDE.md)

## Known limitations of this demo edition

- Database values (statuses, option lists, stored grade reasons) use English
  canonical text; switching the UI language does not retranslate stored
  data values.
- The v5 forging-process workbench (dimension pre-calculation, strike-energy
  checks, geometry helpers) is a companion module of the full private suite
  and is not part of this demo.

## License

MIT — see [LICENSE](LICENSE).
