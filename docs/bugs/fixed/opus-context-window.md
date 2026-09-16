# Opus denominator does not match the deployment

User reports a 200K Opus 4.6 window; task 070 assigned 1M based on general model
documentation. This understates utilization by a factor of five. Correct the
deployment default, preserving explicit overrides and Sonnet's 1M denominator.

Fixed in task 071; 23 focused tests pass, including Opus percentage and provider IDs.
