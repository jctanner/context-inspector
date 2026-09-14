# Task: Random skill generator

## Goal

Provide the requested `scripts/skill-maker.py` to generate 1,000 synthetic skills
under `container/workspace/.context/skill-dump/.claude/skills`.

## Acceptance criteria

- [x] Default output is repository-relative, independent of current directory.
- [x] Generate 1,000 valid skills with substantial random descriptions and bodies.
- [x] Support reproducible seeds and refuse to overwrite existing skills.
- [x] Test in temporary directories without modifying the live skill registry.
- [x] Document invocation and description-budget limitations.

## Discoveries

Skill descriptions, not just bodies, must contain random words to exercise
registration context cost. Claude may cap the description listing; generated
word counts are not measurements of model-visible tokens. `/container/` is
already ignored. The user's explicit script path overrides the usual src-only
layout for this standalone utility; tests remain under src/tests.

## Usage

Run `python3 scripts/skill-maker.py` from the repository. As updated by task 063,
defaults are 1,000 skills, each with 96 random description words and a random
500–5,000 total file lines (including frontmatter), with 20 words per body line.
Use `--seed 42` for reproducible content; `--count`, `--description-words`,
`--min-lines`, `--max-lines`, `--words-per-line`, and `--output` customize the
experiment. The old `--body-words` option was replaced. Descriptions are bounded
to 1,024 characters. Existing numbered skill directories cause an error before
generation; this utility neither deletes nor replaces data. A failed write may
leave a partial batch, which is not automatically removed.

## Verification

`python3 -m unittest src.tests.test_skill_maker -v`: five tests pass, including
a real CLI run producing all 1,000 skills in a temporary directory from another
working directory. Tests check frontmatter, unique descriptions, word counts,
description size, seeded reproducibility, collision/symlink preservation, and
invalid arguments. `git diff --check` passes.

The live workspace was not populated and the stack was not restarted.
