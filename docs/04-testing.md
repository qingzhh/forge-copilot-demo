# 04 - Testing & Acceptance Strategy (v0.1)

## Goal

Set the minimum test boundary for the offline single-PC system so the design
can move into implementation without large-scale rework.

## Test layers

### 1. Design validation

Checks: design docs present, SQLite schema executes, key tables exist, key
field naming is consistent.

```bash
python scripts/validate_design.py
```

### 2. Database initialization test

Checks: an empty database can be created, the schema is correct, and the
script is idempotent.

```bash
python scripts/init_db.py
```

### 3. Importer tests

Must cover: master-data import, history import, duplicate detection,
missing-field handling, sample-grade output.

### 4. Formula consistency tests

For a set of historical Excel samples, the program's calculated values must
stay within the allowed deviation of the original theoretical values.

### 5. Manual acceptance path

1. Create a job
2. Enter setup inputs
3. Calculate theoretical and recommended values
4. Save the snapshot
5. Enter first-piece feedback
6. Automatic grading
7. Enter one readjustment round
8. Query the history

## Acceptance checklist (implementation phase)

- SQLite initialization works
- Master data is maintainable
- New jobs can be saved
- Calculation snapshots can be saved
- First-piece feedback can be saved
- Sample grading runs
- Readjustments leave an audit trail
- History queries work
- Excel import works

## Manual final-review focus

1. Field names the shop floor might not understand
2. Whether first-piece feedback entry is smooth
3. Whether readjustment records are clear enough
4. Whether every recommendation can be traced to its source
5. Whether data imported from the legacy Excel workbook is trustworthy
