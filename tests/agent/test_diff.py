from pathlib import Path

from pmigrate.agent.diff import make_unified_diff, parse_unified_diff
from pmigrate.agent.patch import apply_patch

SIMPLE_DIFF = """diff --git a/foo.py b/foo.py
index c2119dc..3765dd8 100644
--- a/foo.py
+++ b/foo.py
@@ -1,2 +1,2 @@
 def foo():
-    return 1
+    return 2
"""

NEW_AND_DELETED_DIFF = """diff --git a/new.py b/new.py
new file mode 100644
index 0000000..e69de29
--- /dev/null
+++ b/new.py
@@ -0,0 +1,2 @@
+def bar():
+    pass
diff --git a/gone.py b/gone.py
deleted file mode 100644
index e69de29..0000000
--- a/gone.py
+++ /dev/null
@@ -1,2 +0,0 @@
-def baz():
-    pass
"""


def test_simple_modification() -> None:
    files = parse_unified_diff(SIMPLE_DIFF)
    assert len(files) == 1
    f = files[0]
    assert f.path == "foo.py"
    assert not f.is_new_file and not f.is_deleted_file
    assert f.added_lines == ("    return 2",)
    assert f.removed_lines == ("    return 1",)


def test_new_file_detected() -> None:
    files = parse_unified_diff(NEW_AND_DELETED_DIFF)
    new_file = next(f for f in files if f.path == "new.py")
    assert new_file.is_new_file is True
    assert new_file.is_deleted_file is False
    assert new_file.added_lines == ("def bar():", "    pass")


def test_deleted_file_detected() -> None:
    files = parse_unified_diff(NEW_AND_DELETED_DIFF)
    deleted_file = next(f for f in files if f.path == "gone.py")
    assert deleted_file.is_deleted_file is True
    assert deleted_file.removed_lines == ("def baz():", "    pass")


def test_multi_file_diff_parses_both_files() -> None:
    files = parse_unified_diff(NEW_AND_DELETED_DIFF)
    assert {f.path for f in files} == {"new.py", "gone.py"}


def test_empty_diff_returns_empty_list() -> None:
    assert parse_unified_diff("") == []


def test_context_lines_are_ignored() -> None:
    files = parse_unified_diff(SIMPLE_DIFF)
    all_added_and_removed = files[0].added_lines + files[0].removed_lines
    assert "def foo():" not in all_added_and_removed


# --- make_unified_diff --------------------------------------------------------------


def test_make_unified_diff_round_trips_through_apply_patch(tmp_path: Path) -> None:
    before = "x = m.dict()\ny = 2\n"
    after = "x = m.model_dump()\ny = 2\n"
    (tmp_path / "foo.py").write_text(before)

    diff = make_unified_diff("foo.py", before, after)
    result = apply_patch(tmp_path, diff)

    assert result.applied is True
    assert (tmp_path / "foo.py").read_text() == after


def test_make_unified_diff_empty_when_no_change() -> None:
    assert make_unified_diff("foo.py", "same\n", "same\n") == ""


def test_make_unified_diff_parses_back_to_expected_lines() -> None:
    diff = make_unified_diff("foo.py", "a\nb\nc\n", "a\nX\nc\n")
    files = parse_unified_diff(diff)
    assert len(files) == 1
    assert files[0].path == "foo.py"
    assert files[0].removed_lines == ("b",)
    assert files[0].added_lines == ("X",)
