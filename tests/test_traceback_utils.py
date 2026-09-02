from pmigrate.traceback_utils import deepest_first_party_frame, first_party_frames

# the exact real traceback shape found against madkote/fastapi-plugins (docs/decisions.md
# D19) — used here and in tests/agent/test_repair.py precisely because this module was
# extracted FROM that file; both should agree on the same real-world shape.
_BASESETTINGS_TRACEBACK = """\
tests/test_control.py:15: in <module>
    import fastapi_plugins
fastapi_plugins/__init__.py:22: in <module>
    from .settings import *
fastapi_plugins/settings.py:53: in <module>
    class ConfigManager(object):
fastapi_plugins/settings.py:57: in ConfigManager
    def register(self, name: str, config: pydantic.BaseSettings) -> None:
/usr/local/lib/python3.11/site-packages/pydantic/__init__.py:437: in __getattr__
    return _getattr_migration(attr_name)
"""


def test_first_party_frames_excludes_absolute_stdlib_and_site_packages_paths() -> None:
    frames = first_party_frames(_BASESETTINGS_TRACEBACK, exclude_test_paths=False)
    assert frames == [
        "tests/test_control.py",
        "fastapi_plugins/__init__.py",
        "fastapi_plugins/settings.py",
        "fastapi_plugins/settings.py",
    ]


def test_first_party_frames_excludes_test_paths_by_default() -> None:
    frames = first_party_frames(_BASESETTINGS_TRACEBACK)
    assert "tests/test_control.py" not in frames


def test_deepest_first_party_frame_is_the_last_one_before_a_third_party_drop() -> None:
    assert deepest_first_party_frame(_BASESETTINGS_TRACEBACK) == "fastapi_plugins/settings.py"


def test_deepest_first_party_frame_returns_none_when_only_test_paths_present() -> None:
    text = "tests/test_x.py:1: in <module>\n    x = 1\n"
    assert deepest_first_party_frame(text) is None


def test_deepest_first_party_frame_returns_none_for_no_paths_at_all() -> None:
    assert deepest_first_party_frame("some generic assertion failure") is None
