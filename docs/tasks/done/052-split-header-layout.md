# Task: Fix split diff header overlap

- [x] Group columns under Before and After with compact accessible gutter labels.
- [x] Size columns explicitly without leaking inline header width rules.
- [x] Browser checks confirm text stays inside header cells at desktop/mobile widths.
- [x] Existing split content/navigation tests and frontend build pass.

No architecture change: this corrects table markup and presentation only.

## Verification

Build and whitespace checks pass. Outline/split browser fixture verifies every
header text range stays inside its cell at 1280, 901, 768, 390 and 320px, balanced
Before/After halves and accessible gutter labels. Existing split reconstruction,
navigation and caching checks pass, as does fast-replay. Playwright closed;
no backend restart or live session input.
