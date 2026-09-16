# Task: Right-align MCP count widget

- [x] Align controls and status to navigation's right content edge.
- [x] Verify desktop/mobile layout and existing count interactions.

The full-width status text widens the flex form, but controls default to
left justification within that width, leaving apparent trailing padding.

Added flex-end control alignment and right-aligned status text. Build and
Playwright fixture pass with geometric right-edge assertions (within 1px) at
1280px and 390px, including long status text. Synthetic APIs only; live config
and session unchanged. Refresh browser to load the rebuilt CSS; no restart.
