# Bug: Existing Sessions Are Invisible to Fresh Browsers

Start Claude in one browser, then open another profile or hostname. The new
browser reports zero requests because reconnection requires localStorage.
It should discover the server's active session and replay its captured traffic.

Related task: 032-share-active-session.

Fixed in source by server-side discovery and shared Start behavior; regression
tests and two-profile Playwright validation pass. The running server requires a
restart to load the fix.
