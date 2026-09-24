# MLflow trace presentation

## Goal
Improve integrated trace detail hierarchy and styling, informed by the local MLflow trace explorer.

## Acceptance
- Compact trace header and metrics, navigable span hierarchy with timing bars, clear selected span and readable input/output panels.
- Preserve exact recorded IDs and timing provenance, raw JSON, filtering and keyboard-accessible controls.
- Production build, browser regression and visual inspection at desktop/mobile; no stack restart.

## Discovery
Existing view uses generic buttons and long stacked disclosures. MLflow separates span navigation from selected-span content and uses a compact header and tabs. Apply that pattern in the existing Inspector visual theme without embedding the full MLflow application.

## Implementation and validation
Compact trace summary and metric strip, semantic status/type badges, searchable
parent-ID span hierarchy with proportional recorded timing bars, and side-by-side
selected-span content. Inputs/outputs are immediately readable; Attributes and
JSON use keyboard-accessible tabs. Narrow screens stack panels without horizontal
overflow. Native identifiers, raw JSON precision and provenance remain available.

- `npm --prefix src/web run build`: TypeScript and production build passed.
- `src/tests/mlflow.browser.js`: Playwright passed (17 requests), including
  span selection/search, timing bars, keyboard tabs, existing filtering/paging,
  polling, text safety, raw precision, error/empty states and mobile overflow.
- Inspected desktop (1280px) and mobile (390px) screenshots using synthetic data.
- `git diff --check`: passed.

Frontend bundle rebuilt; refresh the browser to load this presentation update.
No backend changes or main-stack restart for this task. ADR-0045 architecture
retained; full MLflow administration remains outside this integrated view.
