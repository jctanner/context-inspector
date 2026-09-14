# Task: Variable skill lengths

- [x] Default each SKILL.md to a randomly selected 500–5,000 total lines inclusive.
- [x] Fill body lines with random words; retain bounded random descriptions.
- [x] Support seeded reproducibility and configurable bounds; reject invalid input.
- [x] Test only temporary output; preserve existing skills and stack.

The latest request replaces the interrupted 1,000-line minimum request.
Line counts include frontmatter and headings, not just body content.

Verification: `python3 -m unittest src.tests.test_skill_maker -v` passes all
eight tests in 9.9 seconds, including a full 1,000-file default batch, variation,
exact 500/5,000 endpoints, custom CLI settings, invalid bounds, seeded identical
content, and overwrite protection. `git diff --check` passes.

No live output was generated or replaced. Use `./scripts/skill-maker.py`;
optional `--min-lines`, `--max-lines`, `--words-per-line` replace `--body-words`.
