# ForgeCopilot - User Guide

Version: v1.30 demo edition (sanitized; all bundled data is synthetic)

## 1. What the program does

ForgeCopilot supports die-setup work on a large (18,000-ton class) forging
press in an **offline** engineering-PC environment. Its core goals:

1. Record die-setup inputs
2. Calculate theoretical values and recommended values
3. Record first-piece feedback
4. Track success rates
5. Accumulate history so recommendations keep improving

## 2. Design idea

This is not a spreadsheet replacement; it is an offline data-loop tool with
four layers:

1. **Master data** - product processes, die versions, die seats, blocks,
   base plates, compensation rules
2. **Job inputs** - the real inputs of each die setup
3. **Calculation snapshots** - the theoretical and recommended values the
   program produced at that moment
4. **First-piece feedback** - the shims actually used, the measured offsets,
   pass/fail, and readjustment records

Because all four are stored separately, everything stays traceable: what was
entered, what was recommended, what was finally used, and which combinations
succeed most often.

## 3. How recommendations work

```text
recommendation = base theoretical value + history correction
```

1. The base theoretical value comes from rule-based calculation over die
   seat, block, base plates, reference planes, lower-die actual height and
   target thickness.
2. The history correction comes from previously saved successful samples.
3. The current version learns primarily from **Grade-A samples**.
4. A sample counts as successful when |actual - recommended| <= 1.
5. Successful samples influence the next recommendation for the same
   product process / die version / block combination.

## 4. Why accuracy improves over time

The engine prefers:

1. Recent successful samples (newest first, linearly time-decayed weights)
2. Successful samples with the same product process, die version and block
3. Successful records with small deviations

The more real feedback is entered, the closer recommendations get to what
actually works on the shop floor.

## 5. First use

1. Start the program
2. (Optional) Generate the bundled synthetic demo data:
   `python scripts/generate_demo_data.py`
3. Or import your Excel master data (Home -> Import Excel Workbook)
4. Optionally import a curated history CSV
5. Check the success-rate statistics and monthly curve on the History page
6. Start entering new jobs

## 6. Daily workflow

1. **New Setup Job** - select product process, die version, die seat, block
2. Enter setup inputs - reference planes, lower-die actual height, base
   plate combination
3. Click **Calculate Recommendation** - review the recommended template
   thickness and X/Y shims, the number of similar cases and the confidence
4. Save the job
5. After the first piece, open **First-piece Feedback**
6. Enter actual template/shims, offsets, pass/fail
7. If a readjustment was needed, add the readjustment record
8. Watch the history statistics and success rates evolve

## 7. Offset entry convention

All offsets use one convention:

> "How much shim still has to be added or removed to reach the 0 position"

- Positive = add more shim
- Negative = remove shim
- 0 = already on target

## 8. Success-rate statistics

Three rates are tracked: template, X shim (lateral) and Y shim
(longitudinal). A direction counts as successful when
|actual - recommended| <= 1. Rates are shown for all time and as a monthly
curve, so it is easy to see whether the recommendation logic is improving
and which direction is least stable.

## 9. Exporting data

The analysis CSV export can be used to:

1. Back up data
2. Import on another engineering PC
3. Hand data to whoever maintains the formulas for further optimization

## 10. Notes

1. Do not delete the database file casually.
2. Back up the `db` folder before every program upgrade.
3. If imported history looks wrong, stop and verify the import before
   entering new data.
4. If one month's success rate drops sharply, check: measurement
   consistency, die seat / block / base plate / guide clearance state, and
   whether a new die version or a regrind state changed.

## 11. Training points

Make these four things explicit when training operators:

1. Select the right master data first, then enter inputs
2. An offset is not a direction - it is "how much shim to add/remove"
3. A recommendation is advice; first-piece feedback must be entered honestly
4. The program gets more accurate with use - provided feedback data is real

## 12. Notable features (v1.10+)

1. **Entry order optimized** - core required fields first (product process,
   die, die seat, block, lower-die height, target thickness), then
   reference planes and base plates
2. **Confidence colors** - high confidence green, medium orange, low red
3. **Time-decayed history weighting** - linear time decay, newest samples
   weigh most
4. **Quick state edit** - change a die seat's guide state or theoretical
   close height directly, and enable/disable blocks, without creating new
   master records

## 13. Language

The interface is bilingual. English is the default; switch anytime via the
**Language** menu (English / Chinese). The choice is remembered across
restarts. Database values (statuses, option lists) use English canonical
values in this edition; only the interface text changes.
