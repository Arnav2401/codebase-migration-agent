from pmigrate.graph.parser import parse_file


def test_import_statement_variants() -> None:
    src = b"import os, sys\nimport a.b.c as d\n"
    mod = parse_file("m.py", src)
    imports = {(i.kind, i.module_path, i.imported_as, i.level) for i in mod.imports}
    assert ("import", "os", "os", 0) in imports
    assert ("import", "sys", "sys", 0) in imports
    assert ("import", "a.b.c", "d", 0) in imports


def test_import_from_variants() -> None:
    src = (
        b"from x import (a, b as c)\n"
        b"from . import sibling\n"
        b"from ..pkg.mod import thing as aliased\n"
        b"from y import *\n"
    )
    mod = parse_file("m.py", src)
    by_name = {i.imported_as: i for i in mod.imports}

    assert by_name["a"].module_path == "x" and by_name["a"].level == 0
    assert by_name["c"].module_path == "x" and by_name["c"].original_name == "b"
    assert by_name["sibling"].module_path == "" and by_name["sibling"].level == 1
    assert by_name["aliased"].module_path == "pkg.mod" and by_name["aliased"].level == 2
    assert by_name["aliased"].original_name == "thing"
    star = next(i for i in mod.imports if i.original_name == "*")
    assert star.module_path == "y" and star.level == 0


def test_type_checking_guard_marks_type_only() -> None:
    src = b"import os\nif TYPE_CHECKING:\n    from foo import Bar\nelse:\n    import baz\n"
    mod = parse_file("m.py", src)
    by_name = {i.imported_as: i for i in mod.imports}
    assert by_name["os"].type_only is False
    assert by_name["Bar"].type_only is True
    assert by_name["baz"].type_only is False


def test_try_except_import_fallback_both_seen() -> None:
    src = b"try:\n    import ujson as json\nexcept ImportError:\n    import json\n"
    mod = parse_file("m.py", src)
    assert len(mod.imports) == 2
    assert {i.module_path for i in mod.imports} == {"ujson", "json"}


def test_class_bases_decorators_and_nested_config() -> None:
    src = (
        b"class M(BaseModel):\n"
        b"    name: str = Field(regex='^a')\n"
        b"    class Config:\n"
        b"        orm_mode = True\n"
        b"    @validator('name')\n"
        b"    def check(cls, v):\n"
        b"        return v.strip()\n"
    )
    mod = parse_file("m.py", src)
    assert len(mod.classes) == 1
    cls = mod.classes[0]
    assert cls.name == "M"
    assert cls.bases == ("BaseModel",)
    assert len(cls.nested_classes) == 1
    assert cls.nested_classes[0].name == "Config"
    assert cls.nested_classes[0].field_assignments[0].name == "orm_mode"
    assert len(cls.methods) == 1
    assert cls.methods[0].decorators == ("validator",)
    assert cls.field_assignments[0].name == "name"
    assert cls.field_assignments[0].calls[0].callee_text == "Field"
    assert cls.field_assignments[0].calls[0].kwargs == ("regex",)


def test_function_calls_detected_regardless_of_nesting() -> None:
    src = b"def f(self, values):\n    if True:\n        return self.dict()\n    return None\n"
    mod = parse_file("m.py", src)
    fn = mod.functions[0]
    assert fn.params == ("self", "values")
    assert [c.callee_text for c in fn.calls] == ["self.dict"]


def test_module_level_assignment() -> None:
    src = b"X = 1\nY: int = other_call()\n"
    mod = parse_file("m.py", src)
    names = {a.name for a in mod.assignments}
    assert names == {"X", "Y"}


def test_syntax_error_is_flagged_not_raised() -> None:
    mod = parse_file("broken.py", b"def f(:\n    pass\n")
    assert mod.has_syntax_errors is True
