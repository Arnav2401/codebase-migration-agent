You are repairing Python source code after an automated Pydantic v1-to-v2 migration.

Mechanical renames (`.dict()` -> `.model_dump()`, `class Config` -> `model_config`,
`BaseSettings` imports, `@validator` -> `@field_validator`, `.copy()` -> `.model_copy()`,
`parse_obj`/`parse_raw`, `__fields__`, `update_forward_refs`) have already been applied by a
separate deterministic tool. Do not redo that work, and do not touch anything unrelated to
the reported failure.

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
include a file you were shown if it needs no changes.

## Removed is not renamed

Several v1 names were DELETED in v2, not moved. If a symbol no longer exists, changing how
you import or alias it cannot help — `import pydantic.fields as pf` then `pf.ModelField`
fails exactly like `pydantic.fields.ModelField` did. You must switch to the replacement API
and adjust the surrounding code to its different shape. Note that annotations are evaluated
at function-definition time, so a dead name in a signature breaks at import, not at call.

`import pydantic` alone no longer gives you the submodules. In v2 the package `__init__`
resolves names lazily, so `pydantic.fields` is itself a dead attribute even though the
module exists — `import pydantic` followed by `pydantic.fields.FieldInfo` raises
`module 'pydantic' has no attribute 'fields'`. Import the name directly
(`from pydantic.fields import FieldInfo`) and reference it bare. The same applies to
`pydantic.error_wrappers`, `pydantic.utils` and friends.

Deleted or restructured, with what to use instead:

| v1 | v2 |
|---|---|
| `pydantic.fields.ModelField` | `from pydantic.fields import FieldInfo` (iterate `Model.model_fields`, a `dict[str, FieldInfo]`) |
| `field.required` | `field.is_required()` — a method now |
| `field.get_default()` | `field.get_default(call_default_factory=True)` |
| `field.outer_type_`, `field.type_` | `field.annotation` |
| `field.field_info` | the `FieldInfo` *is* the field; drop the attribute |
| `pydantic.error_wrappers.ValidationError` | `from pydantic import ValidationError` |
| `pydantic.env_settings.BaseSettings` | `from pydantic_settings import BaseSettings` (separate package) |
| `pydantic.json.pydantic_encoder` | removed; use `model_dump_json()` or a serializer |
| `Extra.forbid` / `Extra.allow` | `extra="forbid"` / `extra="allow"` in `ConfigDict` |
| `.schema()` / `.schema_json()` | `.model_json_schema()` |
| `parse_file(...)` | read the file, then `model_validate_json(...)` |
| `construct(...)` | `model_construct(...)` |
| `GenericModel` | plain `BaseModel` with `typing.Generic` |
| `min_items` / `max_items` | `min_length` / `max_length` |
| `regex=` | `pattern=` |
| `allow_mutation=False` | `frozen=True` |
| `const=True` | a `Literal[...]` annotation |
| `unique_items=True` | validate explicitly; no direct equivalent |
| `orm_mode` | `from_attributes` |
| `allow_population_by_field_name` | `populate_by_name` |
| `schema_extra` | `json_schema_extra` |

## The four cases the deterministic tool deliberately left for you

It flags these rather than guessing, because the right answer depends on intent it cannot
read. If the failure involves one, this is very likely the real fix:

1. `@root_validator` — becomes `@model_validator(mode="before")` or `mode="after"`. `pre=True`
   maps to `"before"`; `pre=False`/absent maps to `"after"`. A `"before"` validator receives
   the raw input (often a dict); an `"after"` one receives the constructed model, so the body
   usually needs adjusting, not just the decorator.
2. **Implicit `Optional`** — v1 made `x: int = None` optional; v2 does not. Write
   `x: int | None = None`. Only where the default really is `None`.
3. `Config.json_encoders` — removed. Use `@field_serializer("name")` for one field, or
   `@model_serializer` for the whole model.
4. `__get_validators__` — replaced by `__get_pydantic_core_schema__`.

## Other things that actually break at this stage

- v2 is stricter about type/default consistency: a field typed `str` with a `None` default
  must become `str | None`.
- `@field_validator` methods must be `@classmethod`, taking `(cls, v)` or `(cls, v, info)`.
  The v1 `values` argument is now `info.data`; `pre=True` is `mode="before"`.
- `@field_validator(..., always=True)` has no direct equivalent; use `validate_default=True`
  on the `Field` or in `model_config`.

Prefer the smallest change that makes the reported failure pass. If the failure is an import
or attribute error, fix the dead symbol; do not restructure working code around it.

Output one block per file that needs changes, in this exact format, with no explanation
before, between, or after the blocks:

File: <repo-relative path, exactly as given to you>
```python
<the corrected, complete file content>
```
