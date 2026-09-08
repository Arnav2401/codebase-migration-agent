from pathlib import Path

from pmigrate.security.regression import Finding, compare, gate, run_scan


def _f(test_id="B602", severity="HIGH", path="a.py", code="subprocess.run(x, shell=True)"):  # type: ignore[no-untyped-def]
    return Finding(test_id=test_id, severity=severity, path=path, code=code)


def test_preexisting_findings_are_not_the_migrations_fault() -> None:
    """The same principle as I4, which scores only tests that passed at baseline: a
    migration answers for what it changed, not the state it inherited. Failing on inherited
    findings would make the gate unusable on real code, so it would get switched off."""
    pre = [_f(), _f(test_id="B303", path="b.py", code="hashlib.md5()")]
    report = compare(pre, list(pre))
    assert report.introduced == []
    assert not report.worsened


def test_a_newly_introduced_finding_fails_the_gate() -> None:
    pre = [_f()]
    post = [*pre, _f(test_id="B307", severity="MEDIUM", path="c.py", code="eval(user_input)")]
    report = compare(pre, post)
    assert len(report.introduced) == 1
    assert report.worsened
    assert report.worst_introduced == "MEDIUM"
    assert "FAIL" in report.render()


def test_findings_are_keyed_by_code_not_line_number() -> None:
    """A migration editing a file ABOVE an untouched finding must not report it as new --
    that false positive is what gets a regression gate disabled."""
    pre = [_f(code="  subprocess.run(x, shell=True)")]
    post = [_f(code="subprocess.run(x, shell=True)  ")]  # same code, shifted/whitespace
    assert compare(pre, post).introduced == []


def test_resolving_a_finding_is_reported_and_still_passes() -> None:
    report = compare([_f(), _f(test_id="B303", path="b.py")], [_f()])
    assert len(report.resolved) == 1
    assert not report.worsened
    assert "resolved" in report.render()


def test_a_scanner_that_cannot_run_fails_closed() -> None:
    """An unavailable gate that reports success is worse than no gate: it looks like
    coverage. So a scan error is a failure, not a pass."""
    report = compare([], [], error="bandit did not run")
    assert report.worsened
    assert "could not run" in report.render()


def test_gate_runs_against_a_real_tree_and_detects_an_introduced_issue(tmp_path: Path) -> None:
    """End-to-end against the real scanner, not a stub."""
    src, ovl = tmp_path / "source", tmp_path / "overlay"
    src.mkdir()
    ovl.mkdir()
    (src / "m.py").write_text("import os\n\n\ndef f(x):\n    return os.path.join(x, 'a')\n")
    (ovl / "m.py").write_text(
        "import os\nimport subprocess\n\n\ndef f(x):\n"
        "    subprocess.run(x, shell=True)\n    return os.path.join(x, 'a')\n"
    )

    report = gate(src, ovl)

    assert report.scan_failed is None, report.scan_failed
    assert report.worsened
    assert any("subprocess" in f.code for f in report.introduced)


def test_run_scan_returns_no_error_on_a_clean_tree(tmp_path: Path) -> None:
    (tmp_path / "clean.py").write_text("X = 1\n")
    findings, error = run_scan(tmp_path)
    assert error is None
    assert findings == []


def test_bandit_line_number_prefixes_do_not_make_a_finding_look_new() -> None:
    """The false positive that made this gate useless on its first real run (D99).

    Bandit's `code` field is the offending line plus context, each prefixed with its line
    NUMBER. Keying on it raw made the key line-dependent, so editing a file above an
    untouched finding renumbered it and reported it as introduced. Real case:
    `Aiven-Open__rohmu` reported 9 "introduced" B101 asserts that predated the migration.
    """
    pre = [
        _f(
            test_id="B101",
            severity="LOW",
            path="m.py",
            code="222         assert not self.total\n223     ",
        )
    ]
    post = [
        _f(
            test_id="B101",
            severity="LOW",
            path="m.py",
            code="231         assert not self.total\n232     ",
        )
    ]

    assert compare(pre, post).introduced == []
    assert not compare(pre, post).worsened


def test_a_genuinely_different_line_at_the_same_location_is_still_new() -> None:
    """Normalisation must not go so far that it stops detecting anything."""
    pre = [_f(test_id="B101", path="m.py", code="222         assert not self.total")]
    post = [_f(test_id="B101", path="m.py", code="222         assert self.unsafe_thing()")]
    assert len(compare(pre, post).introduced) == 1
