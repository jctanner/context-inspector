# Task: Rename script directory to scripts

- [x] Move the generator to `scripts/skill-maker.py`.
- [x] Update references and verify the generator tests.

User requested the plural directory name; behavior and output remain unchanged.

Verification: all five tests pass with the renamed executable; whitespace check
passes. Removed the old empty directory and its generated Python bytecode cache.
