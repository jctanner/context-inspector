# Task: Add Sonnet 4.6 selection

User explicitly requested this model and its deployment window.

- [x] Offer claude-sonnet-4-6 in the modal and accept it in new-session argv.
- [x] Use the user-specified 200K deployment window; preserve Haiku default.
- [x] Verify model selection and context accounting; build frontend.

No model availability probe or live Claude session launch is required.

Verification: 26 focused Python tests pass (selection routes/argv and context
accounting); production TypeScript/Vite build and `git diff --check` pass.
Mocked Playwright fixture passes all four choices, exact submitted models,
Haiku default, focus, cancel/Escape, pending guard, retry and mobile fit.
Browser closed. Backend restart and browser refresh are user-managed.
