# Bug: Remote MLflow charts blocked by Origin validation

Task 058 configured Host allowance but omitted browser Origin allowance.
MLflow 3.16 returns 403 for read-only experiment search with
Origin: http://192.168.1.145:5000; the identical request without Origin returns
200. Live logs explicitly report blocked cross-origin requests for that origin,
including POST /ajax-api/3.0/mlflow/traces/metrics (chart queries).

Required fix: expose --cors-allowed-origins in stack configuration and enumerate
the approved browser URLs (scheme + hostname/IP + port), preserving security
middleware and loopback defaults. Add real-container POST tests with Origin
headers; reject unrelated origins. User performs any stack restart.

No implementation or running-container change performed during diagnosis.

Fixed by task 059: explicit CORS origin setting passed to MLflow, approved local
browser URLs configured, README/.env.example corrected. Real-container regression
verifies approved POSTs succeed and unapproved origins/hosts remain blocked.
Requires user restart to take effect; the running server was not modified.
