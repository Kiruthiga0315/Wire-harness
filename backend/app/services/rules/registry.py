from __future__ import annotations

from typing import Any, Callable
from app.services.rules.schemas import InspectionContext, RuleResult

RuleFamilyEvaluator = Callable[[InspectionContext, dict[str, Any]], list[RuleResult]]


class RuleRegistry:
    """Registry for pluggable quality rule families."""

    def __init__(self) -> None:
        self._evaluators: dict[str, RuleFamilyEvaluator] = {}

    def register(self, family_name: str, evaluator: RuleFamilyEvaluator) -> None:
        self._evaluators[family_name] = evaluator

    def get(self, family_name: str) -> RuleFamilyEvaluator | None:
        return self._evaluators.get(family_name)

    def registered_families(self) -> list[str]:
        return list(self._evaluators.keys())


rule_registry = RuleRegistry()


def _initialize_registry() -> None:
    from app.services.rules.families.final_frm19 import evaluate_final_assembly_frm19
    from app.services.rules.families.msil import evaluate_msil_tolerances
    from app.services.rules.families.ptdb import evaluate_ptdb_regression
    from app.services.rules.families.taping import evaluate_taping_standard
    from app.services.rules.families.visual_wi79 import evaluate_visual_inspection_wi79

    rule_registry.register("msil_tolerances", evaluate_msil_tolerances)
    rule_registry.register("taping_standard", evaluate_taping_standard)
    rule_registry.register("visual_inspection_wi79", evaluate_visual_inspection_wi79)
    rule_registry.register("final_assembly_frm19", evaluate_final_assembly_frm19)
    rule_registry.register("ptdb_yh200502", evaluate_ptdb_regression)


_initialize_registry()
