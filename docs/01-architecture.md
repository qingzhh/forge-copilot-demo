# 01 - System Architecture (v0.1)

## Goal

Define the structure, module boundaries and responsibilities of the offline,
single-PC desktop edition, so implementation stays decoupled and rework is
minimized.

## Overall architecture

```text
Desktop UI layer
  -> Application service layer
    -> Domain rules layer
      -> Data access layer
        -> SQLite
  -> Import/export layer
    -> Excel read/write
  -> Validation & logging layer
```

## Layers

### 1. Desktop UI layer

Responsibilities:

- Job entry, master-data maintenance, history queries, first-piece feedback
  and readjustment entry screens
- Input validation and controlled drop-down choices
- Display of theoretical values, recommendations, similar cases and warnings

Rules:

- Every key field is bound to the field dictionary
- No calculation formulas in the UI layer

### 2. Application service layer

Responsibilities:

- Orchestrate the complete flow of one business operation
- Manage transaction boundaries
- Call the importer, calculator, sample grader and repositories

Suggested services: `MasterDataService`, `InstallJobService`, `CalcService`,
`FeedbackService`, `ImportService`, `ReportService`.

### 3. Domain rules layer

Responsibilities:

- Hold the explainable theoretical formulas
- Execute the recommendation-correction logic
- Execute the sample-grading rules
- Execute outlier-detection rules

Suggested modules: `theory_calculator`, `recommendation_engine`,
`sample_grader`, `validators`.

### 4. Data access layer

Responsibilities:

- Read/write SQLite
- Provide a stable data-model interface
- Keep SQL out of the UI and service layers

### 5. Import/export layer

Responsibilities:

- Import the historical Excel workbook sheet by sheet
- Produce import logs
- Export query results and job sheets

## Scope of the first release

Must have: master-data maintenance, setup-job entry, theoretical-value
calculation, recommendation calculation, first-piece feedback, readjustment
records, history queries, Excel import.

Explicitly out of scope for v1: user permissions, automatic device data
collection, image recognition, network sync, multi-PC collaboration.
(Image recognition and AI assistance are the roadmap of this demo edition -
see the README.)

## Core business objects

Product process, die version, die seat, block, base plate, setup job,
calculation snapshot, first-piece feedback, sample grade, readjustment record.

## Risk controls

1. Formula logic separated from UI logic
2. Recommendation corrections separated from raw theoretical values
3. Raw inputs, calculation snapshots and feedback stored in separate tables
4. History import separated from online entry
5. No cross-row dependency logic inherited from the legacy Excel workbook
