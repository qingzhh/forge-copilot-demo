# 03 - Recommendation & Import Design (v0.1)

## Goal

Define how recommended values are generated, how history samples are used,
and how the Excel import runs.

## Recommendation design

The first release deliberately avoids a black-box model:

```text
recommendation = base theoretical value + history correction
```

### 1. Base theoretical values

Recommended template thickness:

```text
base template thickness
= lower-die actual height
+ lower block plate thickness
+ upper block plate thickness
- die seat actual height
+ total base plate thickness
+ target thickness
- die seat thickness deviation
- base template deviation
+ theoretical 700 template
```

Base X (lateral) shim:

```text
base X shim
= die seat X deviation
+ product-type X compensation
+ (upper die X reference - lower die X reference)
+ (lower block X base thickness - upper block X base thickness)
+ previous blade-direction X compensation
```

Base Y (longitudinal) shim:

```text
base Y shim
= die seat Y deviation
+ (upper die Y reference - lower die Y reference)
+ (lower block Y base thickness - upper block Y base thickness)
- constant correction term
```

The constant correction term is provided by rule configuration, never
hard-coded.

### 2. History correction

Median corrections are computed from Grade-A samples, grouped by a fallback
hierarchy:

1. Product process + die version + block + blade direction
2. Product process + die version + block
3. Product process + die version
4. Product process + product type
5. Global baseline

### 3. Sample eligibility

A history sample only feeds the correction statistics when:

- Sample grade = A
- Key inputs are complete
- Key feedback is complete
- No obvious installation anomaly

### 4. Recommendation confidence

- `high`: >= 20 eligible samples in the group
- `medium`: 5-19 samples
- `low`: < 5 samples

## Excel import design

### Import modes

Master data sheets (English names; the legacy Chinese names are accepted as
aliases): `Base Plates`, `Die Seats`, `Blocks`, `Blade Types`.

History sheet: `Calculation` (the legacy Chinese sheet name is accepted as an alias).

### Import principles

1. Master data first, history second
2. Every failed row is logged
3. History import never overwrites existing jobs
4. Only stable fields are extracted; fragile legacy Excel logic is not copied

### Deduplication

History rows are deduplicated on:
product+process name + die no. + die seat no. + block no. + date.
Duplicates are logged, not overwritten.

### Grading on import

- Inputs and feedback complete -> A
- Inputs complete, feedback incomplete -> B
- Key fields missing or abnormal -> C

### Legacy Excel logic explicitly NOT inherited

1. Cross-row position corrections
2. Whole-sheet average deviation logic
3. Out-of-range auto-clearing
4. Retired data-validation logic

### Import output

Total rows, successful rows, failed rows, duplicate rows, A/B/C sample
counts, and the main failure reasons.
