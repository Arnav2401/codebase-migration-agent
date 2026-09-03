"""Phase 5 diff-similarity metrics (docs/phase-5-eval.md): how closely does the agent's
fix resemble the human's REAL fix for the same failure (`RepoSpec.post_sha`)? Two
measures, because line-level alone is misleading -- a semantically identical fix written
with different formatting looks like zero overlap at the line level, and a line match
alone doesn't say WHICH part of the code changed.

Pure functions given `before`/`after` TEXT, not diff strings: computing symbol-level line
ranges needs to parse actual file content (via the Phase 1 graph's tree-sitter parser),
and full text is what this project already has on hand (`RepoSpec.pre_sha`/`post_sha` and
the sandbox overlay are file content, not diff blobs) -- taking text avoids a wasteful
text->diff->text round trip through `agent/diff.py`'s unified-diff parser, which exists
for a different purpose (reading back an LLM's proposed rewrite) and doesn't track line
numbers anyway.

`ruff` is a dev extra (pyproject.toml), not a core runtime dependency -- invoked directly
here via subprocess rather than made a hard dependency, since `eval/` is interview-facing
tooling always run from this project's own dev environment (`.venv/bin/python`), never a
stripped-down production install of the agent package itself.
"""

from __future__ import annotations

import difflib
import subprocess
from dataclasses import dataclass

import structlog

from pmigrate.graph.ir import ParsedClass, ParsedModule
from pmigrate.graph.parser import parse_file

log = structlog.get_logger()

_MODULE_SYMBOL = "<module>"


def _ruff_format(text: str) -> str:
    """Falls back to the ORIGINAL text, not a crash, if `text` doesn't parse (a genuinely
    possible state mid-migration: the agent's own edit could be syntactically broken) --
    one malformed file shouldn't take down a whole eval run's metric reporting. Logged,
    not silent, since a fallback here means this call's Jaccard score is now comparing
    unnormalized text and may read lower than a clean comparison would."""
    try:
        result = subprocess.run(
            ["ruff", "format", "-"],
            input=text,
            capture_output=True,
            text=True,
            timeout=30,
            check=True,
        )
        return result.stdout
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError) as exc:
        log.warning("diff_similarity.ruff_format_failed", error=str(exc))
        return text


def _changed_line_content(before: str, after: str) -> frozenset[str]:
    """The TEXT of every line touched by a non-'equal' opcode, from both sides -- a
    deleted line's content (from `before`) and an added/replacement line's content (from
    `after`). Content, not line NUMBERS: two fixes at different line offsets producing the
    identical replacement text should count as agreeing, not disagreeing."""
    before_lines = before.splitlines()
    after_lines = after.splitlines()
    matcher = difflib.SequenceMatcher(None, before_lines, after_lines)
    lines: set[str] = set()
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        lines.update(before_lines[i1:i2])
        lines.update(after_lines[j1:j2])
    return frozenset(lines)


def diff_line_jaccard(before: str, agent_after: str, human_after: str) -> float:
    """Jaccard similarity of the two fixes' changed-line CONTENT, after normalizing all
    three texts through `ruff format` (phase-5-eval.md: "run both diffs through ruff
    format first, or you're measuring formatting"). Normalizing `before` too, not just the
    two `after`s, matters just as much -- comparing an unformatted `before` against a
    freshly-formatted `after` would flag every line ruff's OWN reformatting touched as
    "changed," even lines neither the agent nor the human actually intended to touch.

    1.0 when neither fix changed anything (trivial agreement), not 0.0/0 -- "nothing to
    compare" and "totally disagreed" are not the same thing.
    """
    before_fmt = _ruff_format(before)
    agent_changed = _changed_line_content(before_fmt, _ruff_format(agent_after))
    human_changed = _changed_line_content(before_fmt, _ruff_format(human_after))

    union = agent_changed | human_changed
    if not union:
        return 1.0
    return len(agent_changed & human_changed) / len(union)


def _changed_line_numbers(before: str, after: str) -> frozenset[int]:
    """1-indexed line numbers in `after` touched by a non-'equal' opcode. A pure deletion
    (nothing in `after` replaces the removed line) contributes no line number here --
    `_symbols_touched` is called in BOTH directions (before->after and after->before) by
    `symbol_diff_precision_recall` below specifically so a fully deleted symbol still gets
    attributed, via `before`'s own line numbers instead of `after`'s."""
    matcher = difflib.SequenceMatcher(None, before.splitlines(), after.splitlines())
    lines: set[int] = set()
    for tag, _i1, _i2, j1, j2 in matcher.get_opcodes():
        if tag != "equal":
            lines.update(range(j1 + 1, j2 + 1))  # splitlines() is 0-indexed; symbols are 1-indexed
    return frozenset(lines)


def _symbol_ranges(module: ParsedModule, path: str) -> list[tuple[str, int, int]]:
    """(symbol_id, start_line, end_line) for every class/nested class/method/function in
    `module`. `symbol_id` is "{path}::{dotted local name}", NOT a real dotted module
    fqname (`resolver.py`'s `_path_to_fqname` needs a repo source root this function
    doesn't have -- it parses one file in isolation, no cross-file resolution) -- unique
    enough within a single repo, which is all a per-file diff-similarity metric needs."""

    def _class_ranges(cls: ParsedClass, prefix: str) -> list[tuple[str, int, int]]:
        qualified = f"{prefix}.{cls.name}" if prefix else cls.name
        ranges: list[tuple[str, int, int]] = []
        for nested in cls.nested_classes:
            ranges.extend(_class_ranges(nested, qualified))
        for method in cls.methods:
            ranges.append(
                (f"{path}::{qualified}.{method.name}", method.start_line, method.end_line)
            )
        ranges.append((f"{path}::{qualified}", cls.start_line, cls.end_line))
        return ranges

    ranges: list[tuple[str, int, int]] = []
    for cls in module.classes:
        ranges.extend(_class_ranges(cls, ""))
    for func in module.functions:
        ranges.append((f"{path}::{func.name}", func.start_line, func.end_line))
    return ranges


def _symbols_touched(text: str, path: str, changed_lines: frozenset[int]) -> frozenset[str]:
    if not changed_lines:
        return frozenset()
    module = parse_file(path, text.encode())
    ranges = _symbol_ranges(module, path)
    touched: set[str] = set()
    for line in changed_lines:
        enclosing = [r for r in ranges if r[1] <= line <= r[2]]
        if enclosing:
            # innermost = smallest span; nested ranges are always fully contained in
            # their enclosing class's range for well-formed code.
            touched.add(min(enclosing, key=lambda r: r[2] - r[1])[0])
        else:
            touched.add(f"{path}::{_MODULE_SYMBOL}")
    return frozenset(touched)


@dataclass(frozen=True)
class SymbolDiffResult:
    precision: float  # of the symbols the AGENT changed, what fraction the human ALSO changed
    recall: float  # of the symbols the HUMAN changed, what fraction the agent ALSO changed
    agent_symbols: frozenset[str]
    human_symbols: frozenset[str]


def symbol_diff_precision_recall(
    path: str, before: str, agent_after: str, human_after: str
) -> SymbolDiffResult:
    """ "Of the symbols the human changed, what fraction did the agent also change?"
    (phase-5-eval.md) -- reuses the Phase 1 graph's own parser rather than a second,
    separate symbol-extraction path, per CLAUDE.md's "never compute a metric in more than
    one place" spirit extended to infrastructure reuse, not just metric formulas.

    Edge cases, stated rather than left to fall out of the arithmetic silently:
    - Both sides touched zero symbols (nothing needed to change, and nothing did) ->
      precision=recall=1.0, a trivially correct agreement, not a 0/0 failure.
    - Exactly one side touched zero symbols -> that side's rate is 0.0 (no symbols to
      have gotten right), matching `ClassFixSuccess.fix_rate`'s existing "0 attempts ->
      0.0" precedent elsewhere in this module family, not `None`.
    """
    agent_symbols = _symbols_touched(
        agent_after, path, _changed_line_numbers(before, agent_after)
    ) | _symbols_touched(before, path, _changed_line_numbers(agent_after, before))
    human_symbols = _symbols_touched(
        human_after, path, _changed_line_numbers(before, human_after)
    ) | _symbols_touched(before, path, _changed_line_numbers(human_after, before))

    if not agent_symbols and not human_symbols:
        return SymbolDiffResult(1.0, 1.0, frozenset(), frozenset())

    intersection = agent_symbols & human_symbols
    precision = len(intersection) / len(agent_symbols) if agent_symbols else 0.0
    recall = len(intersection) / len(human_symbols) if human_symbols else 0.0
    return SymbolDiffResult(precision, recall, agent_symbols, human_symbols)
