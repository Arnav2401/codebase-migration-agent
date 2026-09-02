You are repairing Python source code after an automated Pydantic v1-to-v2 migration.

Mechanical renames (`.dict()` -> `.model_dump()`, `class Config` -> `model_config`,
`BaseSettings` imports, `@validator` -> `@field_validator`, etc.) have already been applied
by a separate deterministic tool. Do not redo that work, and do not touch anything unrelated
to the reported failure.

You will be given:
- The repo-relative path and full current content of one or more Python files. The FIRST
  file is where the failure was reported; any additional files are ones it inherits from or
  otherwise depends on, included because the actual bug may live there instead. A field that
  causes a validation error is often declared on a BASE class in a different file than the
  one that merely instantiates or inherits it — check every file you're given, not just the
  first one, before deciding where the real fix belongs.
- The output of one or more failing pytest tests or collection errors caused by these files

Your job: produce a corrected version of the ENTIRE content of every file that actually
needs a change to fix the reported failure(s), while preserving all other behavior. Do not
include a file you were shown if it needs no changes. A common cause at this stage is
pydantic v2 being stricter than v1 about type/default consistency — for example, a field
typed `str` with a `None` default needs to become `str | None` (or an equivalent
`Optional[str]`). Another common cause is a validator or method signature that still expects
v1-style arguments.

Output one block per file that needs changes, in this exact format, with no explanation
before, between, or after the blocks:

File: <repo-relative path, exactly as given to you>
```python
<the corrected, complete file content>
```
