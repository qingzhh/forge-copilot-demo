# 02 - Desktop UI Flow (v0.1)

## Goal

Define the page structure, navigation and key inputs/outputs of the desktop
program.

## Main navigation

1. Home
2. Master Data
3. New Setup Job
4. History (queries, success-rate statistics, CSV export)

First-piece feedback is entered either on the same page as the new job or
from the list of jobs awaiting feedback.

## Page definitions

### 1. Home

- Current data counts (product processes, die versions, die seats, blocks,
  history jobs)
- Quick actions: initialize database, import Excel workbook, import curated
  history CSV, refresh all data
- Entry tips for shop-floor use

### 2. Master Data

Sub-pages: product processes, die versions, die seats, blocks, base plates,
compensation rules, basic options, plus a "quick state edit" page for die
seat guide state / close height and block enable/disable.

Actions: add, edit (load selected), deactivate (with reason), reactivate,
query.

### 3. New Setup Job

Step 1 - basic selection: product process, die, die version, die seat, block.

Step 2 - setup inputs: base plates 1-5, upper/lower die X/Y reference
planes, lower-die actual height, target thickness, optional process fields
(temperatures, lubrication, hit count, ...).

Step 3 - calculation: base theoretical template thickness, X shim and Y shim;
recommended template thickness, X shim and Y shim; number of similar history
cases; recommendation confidence.

Step 4 - optionally enter first-piece feedback on the same page and save
job + feedback together.

### 4. First-piece Feedback

Inputs: actual template thickness, template aluminum block thickness, actual
thickness, actual root/tip X shims, actual Y shim, root/tip X offsets, Y
offset, first-piece thickness delta, pass/fail, defect type, quality grades
(measurement reliability, die installation quality, block installation
quality, die seat guide state).

Output: the sample is graded A/B/C automatically; the job status becomes
*Completed* (passed) or returns to *Feedback Pending*.

### 5. Readjustment

Each readjustment is a new record (never overwritten): round, template
adjustment, X/Y shim adjustments, reason, result after adjustment.

### 6. History & Statistics

- Filter by product process
- Theory vs. recommendation vs. actual, deviations, sample grade, status
- Success-rate statistics (success = |actual - recommended| <= 1), all-time
  and monthly, with a trend chart
- Export of the analysis CSV (used to keep improving the formulas)

## Key interaction rules

1. Required fields must be complete before submitting.
2. Every calculation is stored as an immutable snapshot.
3. Sample grading runs when first-piece feedback is saved.
4. Readjustments are append-only.
