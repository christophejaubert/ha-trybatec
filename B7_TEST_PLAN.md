# Trybatec b7 development and validation plan

**Status:** Development only, branch `feature/0.2.0b7`. Do **not** merge
to `main`, tag or publish before b6 field-test feedback is addressed.

## Included features

1. Read-only historical EUR cost estimates grouped by French-local civil year,
   fluid (EF/ECS/CET) and evidence class (measured near-daily versus separately
   approved accounting attribution); no silent annual tariff fallback.
2. Read-only diagnostic action exposing gaps, index declines, missing units,
   conflicting observations and ambiguous physical meter succession.
3. Bounded Trybatec HTTP responses and limited retries for temporary statuses;
   permanent failures do not trigger repeated calls.
4. Synthetic automated tests for per-meter scaling, sparse gaps, DST/year-end,
   cross-lot identity isolation, admin-only actions and network conditions.

## Validation gates

- GitHub Actions: Python compile, pytest, import with latest published HA,
  manifest check, brand dimensions, and scanned repository files.
- On a backed-up test instance: compare unit labels with the physical meter,
  try water-only, heating-only, multiple lots, sparse history and retired
  meters. Check admin-only access, rate years, and read-only action outputs.
- Perform b6 regression tests on real data before b7 promotion. Ensure Recorder
  pending verification, entity migration and Energy dashboard selections are
  unaffected.
- Document and fix any b6 defects on their own branch and incorporate the
  patches into this b7 branch before final release review.

**Known limitations:** Undocumented portal field names, unaudited tariff
inputs, unavailable independent vendor invoice data, no automatic Recorder
or Energy dashboard migration, no claim of complete interval coverage.
The EUR results are estimates, not an approved statement of charges.
