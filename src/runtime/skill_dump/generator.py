#!/usr/bin/env python3
"""Generate synthetic skills for discovery/context-load experiments.

Run: python3 scripts/skill-maker.py
Defaults: 1,000 skills, each 500–5,000 total lines (including frontmatter),
with 96 description words and 20 random words per body line.
Claude may limit the advertised skill listing; words are not token counts.
Existing skill directories are never replaced. No stack restart is performed.
"""

import argparse
import random
from pathlib import Path


DEFAULT_OUTPUT = (
    Path(__file__).resolve().parents[3]
    / "container/workspace/.context/skill-dump/.claude/skills"
)
WORDS = """
acorn amber anchor apple apron arrow atlas autumn badge bamboo barrel basket
beacon berry birch blanket blossom bottle branch breeze brick brook bubble
cactus candle canyon carrot cedar cherry circle cloud clover cobalt coffee
comet coral cotton crane crystal daisy dawn delta desert dew diamond drift
eagle earth echo elm ember falcon feather fern field finch flame flint flower
forest fossil frost garden garnet ginger glacier globe grain granite grape
grass gravel grove harbor harvest hazel heron honey horizon island ivory jade
jasmine jewel juniper kettle lagoon lake lantern laurel lavender leaf lemon
linen lotus maple marble meadow melon mercury mist moss mountain nectar
nettle ocean olive opal orange orchid otter oyster pebble pepper petal pine
planet plum pollen pond poplar prairie prism quartz quill rain raven reed
reef ribbon ripple river robin rose ruby saffron sage sand sapphire satin
shell silver sky slate snow solar sparrow spring spruce star stone storm
stream summit sunset teal thistle thunder timber topaz tulip valley velvet
violet walnut water wave wheat willow wind winter wood wren yellow zephyr
""".split()


def positive(value: str) -> int:
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError("must be positive")
    return number


def write_skill(handle, name, rng, description_words=96, words_per_line=20,
                min_lines=500, max_lines=5000):
    """Write one complete generated skill using the CLI's content defaults."""
    description = " ".join(rng.choices(WORDS, k=description_words))
    line_count = rng.randint(min_lines, max_lines)
    header = (
        f'---\nname: {name}\ndescription: "{description}"\n---\n\n'
        f"# {name}\n\n"
        "Synthetic random-word skill for context-load testing.\n\n"
    )
    handle.write(header)
    for _ in range(line_count - header.count("\n")):
        handle.write(" ".join(rng.choices(WORDS, k=words_per_line)) + "\n")


def generate(output: Path, count: int, description_words: int,
             words_per_line: int = 20, seed: int | None = None,
             min_lines: int = 500, max_lines: int = 5000) -> int:
    """Create exclusive skill directories; return number created."""
    if min(count, description_words, words_per_line) < 1:
        raise ValueError("counts must be positive")
    if min_lines < 10 or max_lines < min_lines:
        raise ValueError("require 10 <= min-lines <= max-lines (includes 9 header lines)")
    # Keep every description within the documented 1,024-character limit.
    if description_words * (max(map(len, WORDS)) + 1) - 1 > 1024:
        raise ValueError("description words could exceed 1,024 characters")
    rng = random.Random(seed)
    targets = [output / f"skill-dump-{index:04d}"
               for index in range(1, count + 1)]
    for target in targets:
        if target.exists() or target.is_symlink():
            raise FileExistsError(f"refusing to overwrite {target}")
    output.mkdir(parents=True, exist_ok=True)
    for target in targets:
        target.mkdir()  # Exclusive even if another generator races us.
        with (target / "SKILL.md").open("x", encoding="utf-8") as handle:
            write_skill(handle, target.name, rng, description_words, words_per_line,
                        min_lines, max_lines)
    return len(targets)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--count", type=positive, default=1000)
    parser.add_argument("--description-words", type=positive, default=96)
    parser.add_argument("--min-lines", type=positive, default=500,
                        help="minimum total file lines, including frontmatter (default: 500)")
    parser.add_argument("--max-lines", type=positive, default=5000,
                        help="maximum total file lines, inclusive (default: 5000)")
    parser.add_argument("--words-per-line", type=positive, default=20)
    parser.add_argument("--seed", type=int, help="reproduce the same random content")
    args = parser.parse_args()
    try:
        count = generate(args.output, args.count, args.description_words,
                         args.words_per_line, args.seed, args.min_lines, args.max_lines)
    except (OSError, ValueError) as exc:
        parser.exit(1, f"Error: {exc}\n")
    print(f"Created {count:,} skills in {args.output.resolve()}")
    print(f"Per skill: {args.description_words} random description words; "
          f"{args.min_lines}–{args.max_lines} total lines; "
          f"{args.words_per_line} random words per body line.")
    print("Claude may cap skill descriptions; generated words are not observed tokens.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
