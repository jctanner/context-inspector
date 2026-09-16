# MCP widget controls appear inset from the right edge

Long status text determines the form width. Its controls are left-justified
inside that width despite the form itself being right-aligned. Expected:
Refresh button and status align to the navigation's right content edge.

Tracked by task 066.

Fixed by right-justifying form contents and status; desktop/mobile browser
geometry assertions pass.
