# Bug: Change navigation leaves the payload outline stale

Next/Previous change scrolls a diff row without notifying the outline. Its
aria-current selection and row highlight still reflect the last outline click.
The initial Previous calculation also skips the last hunk when several exist.
Task 050 synchronizes navigation and covers initial/wrapping behavior.

Fixed and verified by task 050: shared row selection, side-specific node ranges,
lazy ancestor reveal, sidebar-only scrolling and initial Previous correction.
