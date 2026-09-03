from pmigrate.eval.diff_similarity import diff_line_jaccard, symbol_diff_precision_recall

_BEFORE = """class User:
    def greet(self):
        return "hi"

    def other(self):
        return 1
"""


def test_jaccard_is_one_when_neither_side_changed_anything() -> None:
    assert diff_line_jaccard(_BEFORE, _BEFORE, _BEFORE) == 1.0


def test_jaccard_ignores_pure_formatting_differences() -> None:
    # same semantic change (return "hi" -> return "hello"), different whitespace --
    # phase-5-eval.md: "run both diffs through ruff format first, or you're measuring
    # formatting."
    agent_after = _BEFORE.replace('return "hi"', 'return "hello"')
    human_after = _BEFORE.replace('return "hi"', 'return   "hello"')
    assert diff_line_jaccard(_BEFORE, agent_after, human_after) == 1.0


def test_jaccard_is_zero_when_the_two_fixes_touch_disjoint_content() -> None:
    agent_after = _BEFORE.replace('return "hi"', 'return "hello"')
    human_after = _BEFORE.replace("return 1", "return 2")
    assert diff_line_jaccard(_BEFORE, agent_after, human_after) == 0.0


def test_jaccard_reflects_partial_overlap() -> None:
    # both fixes change greet(), but to different values -- the removed line ("hi") is
    # shared, the two added lines aren't, so this is a partial (not zero, not one) match.
    agent_after = _BEFORE.replace('return "hi"', 'return "hello"')
    human_after = _BEFORE.replace('return "hi"', 'return "hey"')
    score = diff_line_jaccard(_BEFORE, agent_after, human_after)
    assert 0.0 < score < 1.0


def test_symbol_diff_is_trivially_perfect_when_nothing_changed() -> None:
    result = symbol_diff_precision_recall("app/models.py", _BEFORE, _BEFORE, _BEFORE)
    assert (result.precision, result.recall) == (1.0, 1.0)
    assert result.agent_symbols == frozenset()


def test_symbol_diff_full_agreement_on_the_same_method() -> None:
    agent_after = _BEFORE.replace('return "hi"', 'return "hello"')
    human_after = _BEFORE.replace('return "hi"', 'return   "hello"')  # different formatting
    result = symbol_diff_precision_recall("app/models.py", _BEFORE, agent_after, human_after)
    assert result.precision == 1.0
    assert result.recall == 1.0
    assert result.agent_symbols == frozenset({"app/models.py::User.greet"})
    assert result.human_symbols == frozenset({"app/models.py::User.greet"})


def test_symbol_diff_zero_overlap_when_fixes_touch_different_methods() -> None:
    agent_after = _BEFORE.replace('return "hi"', 'return "hello"')  # touches greet()
    human_after = _BEFORE.replace("return 1", "return 2")  # touches other()
    result = symbol_diff_precision_recall("app/models.py", _BEFORE, agent_after, human_after)
    assert result.precision == 0.0
    assert result.recall == 0.0
    assert result.agent_symbols == frozenset({"app/models.py::User.greet"})
    assert result.human_symbols == frozenset({"app/models.py::User.other"})


def test_symbol_diff_zero_denominator_when_only_the_agent_changed_anything() -> None:
    agent_after = _BEFORE.replace('return "hi"', 'return "hello"')
    result = symbol_diff_precision_recall("app/models.py", _BEFORE, agent_after, _BEFORE)
    assert result.precision == 0.0  # agent touched a symbol the human's "fix" didn't need
    assert result.recall == 0.0  # meaningless here (human touched nothing) but not undefined


def test_symbol_diff_attributes_a_fully_deleted_method_via_before_line_numbers() -> None:
    # other() no longer exists in `after` at all -- can't be found via after's own parse
    # tree, must be attributed via before's.
    after = 'class User:\n    def greet(self):\n        return "hi"\n'
    result = symbol_diff_precision_recall("app/models.py", _BEFORE, after, after)
    assert "app/models.py::User.other" in result.agent_symbols
    assert result.precision == 1.0
    assert result.recall == 1.0


def test_symbol_diff_attributes_a_module_level_change_to_the_module_sentinel() -> None:
    before = "X = 1\n\n\ndef f():\n    return 1\n"
    after = "X = 2\n\n\ndef f():\n    return 1\n"
    result = symbol_diff_precision_recall("app/const.py", before, after, after)
    assert result.agent_symbols == frozenset({"app/const.py::<module>"})


def test_symbol_diff_resolves_nested_classes_and_methods_correctly() -> None:
    before = "class Outer:\n    class Inner:\n        def method(self):\n            return 1\n"
    after = before.replace("return 1", "return 2")
    result = symbol_diff_precision_recall("app/nested.py", before, after, after)
    assert result.agent_symbols == frozenset({"app/nested.py::Outer.Inner.method"})
