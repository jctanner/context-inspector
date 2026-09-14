# Bug: Context UI Obscures Content and Mislabels Missing Responses

Repeated unchanged requests fill full-height cards; evidence JSON precedes content.
Cards label wire event sequence as request number. Missing response reconstruction
is presented indefinitely as awaiting capture, even when its lifecycle is unknown.
New request rendering unconditionally scrolls the reader to the bottom.

Addressed by task 033; no change to captured evidence or classifier certainty.

Fixed: grouped repeats, separate visible request numbers and wire event IDs,
neutral missing-response labels, content-first rendering, and reader-aware
scrolling. Synthetic browser regression and live-session inspection passed.
