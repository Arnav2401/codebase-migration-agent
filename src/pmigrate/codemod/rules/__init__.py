"""ALL_RULES is the public surface of this package — engine.apply_rules(source, path,
ALL_RULES) is the whole T1 tier. Order runs mechanical/structural rules before the
needs-review-only detectors, though in practice none of these rules' matches overlap."""

from pmigrate.codemod.protocol import CodemodRule
from pmigrate.codemod.rules.basesettings_import import rule as basesettings_import_rule
from pmigrate.codemod.rules.config_class_to_configdict import rule as config_class_rule
from pmigrate.codemod.rules.copy_to_model_copy import rule as copy_rule
from pmigrate.codemod.rules.custom_get_validators_flag import rule as get_validators_flag_rule
from pmigrate.codemod.rules.dict_to_model_dump import rule as dict_rule
from pmigrate.codemod.rules.field_kwargs import rule as field_kwargs_rule
from pmigrate.codemod.rules.fields_attr import rule as fields_attr_rule
from pmigrate.codemod.rules.implicit_optional_flag import rule as implicit_optional_flag_rule
from pmigrate.codemod.rules.json_encoders_flag import rule as json_encoders_flag_rule
from pmigrate.codemod.rules.json_to_model_dump_json import rule as json_rule
from pmigrate.codemod.rules.parse_obj_to_model_validate import rule as parse_obj_rule
from pmigrate.codemod.rules.parse_raw_to_validate_json import rule as parse_raw_rule
from pmigrate.codemod.rules.root_validator_flag import rule as root_validator_flag_rule
from pmigrate.codemod.rules.update_forward_refs import rule as update_forward_refs_rule
from pmigrate.codemod.rules.validator_to_field_validator import rule as validator_rule

ALL_RULES: list[CodemodRule] = [
    basesettings_import_rule,
    config_class_rule,
    dict_rule,
    json_rule,
    parse_obj_rule,
    parse_raw_rule,
    copy_rule,
    update_forward_refs_rule,
    fields_attr_rule,
    field_kwargs_rule,
    validator_rule,
    root_validator_flag_rule,
    implicit_optional_flag_rule,
    get_validators_flag_rule,
    json_encoders_flag_rule,
]
