# Bug: Metadata-Only Changes Render as Identical Before/After Text

A text block loses cache_control but keeps identical text. The card says Changed
and displays the same text twice, hiding the only actual field difference in raw
evidence. Task 034 adds explicit unchanged-text and field-difference presentation.

Fixed and verified against synthetic fixtures and the live session. Changed
non-text fields are displayed directly and identical text is disclosed once.
