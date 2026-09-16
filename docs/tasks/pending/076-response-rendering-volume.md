# Task: Improve long response payload readability

- [ ] Reduce rendering/navigation overhead for thousands of SSE deltas.
- [ ] Handle opaque signature fields and raw-field duplication without data loss.
- [ ] Keep usage easy to find and decoded/reconstructed/wire provenance explicit.
- [ ] Regress with synthetic long streams and large signatures.

See docs/bugs/open/response-event-rendering-volume.md. Diagnosis only so far;
implementation awaits user direction.
