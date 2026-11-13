"""
TwinOps Digital Twin Rule & Derived KPI Evaluator.
Evaluates template formulas, derived metrics, and ISO 10816 status bands safely.
Ref: docs/05_design_document.md §4, 9
"""

import ast
import operator
from typing import Any

from services.common.twin_templates import AssetTypeTemplate

# Supported safe AST operators
SAFE_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
    ast.Gt: operator.gt,
    ast.GtE: operator.ge,
    ast.Lt: operator.lt,
    ast.LtE: operator.le,
    ast.Eq: operator.eq,
    ast.NotEq: operator.ne,
}


def safe_eval(expr: str, context: dict[str, Any]) -> Any:
    """
    Safely evaluate an algebraic or boolean expression using Python's AST.
    Guarantees no arbitrary code execution or __builtins__ access.
    """

    def _eval(node):
        if isinstance(node, ast.Constant):
            return node.value
        elif isinstance(node, ast.Name):
            if node.id in context:
                return context[node.id]
            # Boolean literals
            if node.id == "True":
                return True
            if node.id == "False":
                return False
            raise NameError(f"Variable '{node.id}' not provided in context")
        elif isinstance(node, ast.BinOp):
            left = _eval(node.left)
            right = _eval(node.right)
            op_type = type(node.op)
            if op_type in SAFE_OPERATORS:
                return SAFE_OPERATORS[op_type](left, right)
            raise NotImplementedError(f"Unsupported binary operator: {op_type}")
        elif isinstance(node, ast.UnaryOp):
            operand = _eval(node.operand)
            op_type = type(node.op)
            if op_type in SAFE_OPERATORS:
                return SAFE_OPERATORS[op_type](operand)
            raise NotImplementedError(f"Unsupported unary operator: {op_type}")
        elif isinstance(node, ast.Compare):
            left = _eval(node.left)
            for op, comparator in zip(node.ops, node.comparators):
                right = _eval(comparator)
                op_type = type(op)
                if op_type in SAFE_OPERATORS:
                    if not SAFE_OPERATORS[op_type](left, right):
                        return False
                    left = right
                else:
                    raise NotImplementedError(f"Unsupported comparison: {op_type}")
            return True
        elif isinstance(node, ast.BoolOp):
            if isinstance(node.op, ast.And):
                return all(_eval(v) for v in node.values)
            elif isinstance(node.op, ast.Or):
                return any(_eval(v) for v in node.values)
            raise NotImplementedError(f"Unsupported boolean operator: {type(node.op)}")
        else:
            raise TypeError(f"Unsupported AST node type: {type(node)}")

    parsed = ast.parse(expr.strip(), mode="eval")
    return _eval(parsed.body)


class TwinEvaluator:
    """
    Evaluates template derived metrics and status rules for an asset.
    """

    @staticmethod
    def evaluate_derived_metrics(
        template: AssetTypeTemplate, raw_metrics: dict[str, float]
    ) -> dict[str, float]:
        """
        Evaluate all derived metrics specified in the asset twin template.
        e.g. Pump hydraulic efficiency: (flow * discharge * 2.78) / power
        e.g. Chiller delta T: inlet_temp - outlet_temp
        """
        derived: dict[str, float] = {}
        eval_context = dict(raw_metrics)

        for d in template.derived:
            try:
                res = safe_eval(d.expr, eval_context)
                val = round(float(res), 3)
                derived[d.name] = val
                eval_context[d.name] = val  # Can be used by subsequent expressions
            except Exception:
                # If a required input signal is missing, leave derived metric unset
                pass

        return derived

    @staticmethod
    def evaluate_status_color(
        template: AssetTypeTemplate,
        raw_metrics: dict[str, float],
        operational_status: str = "RUNNING",
        is_stale: bool = False,
    ) -> tuple[str, list[str]]:
        """
        Computes 3D digital twin visualization status color according to Section 6 of PRD:
        - 'green': RUNNING, all metrics within normal bands.
        - 'amber': IDLE or WARNING (hi / lo threshold reached, or ISO 10816 Zone C).
        - 'red': FAULT or ALARM (hi_hi / lo_lo exceeded, or ISO 10816 Zone D).
        - 'grey': OFFLINE or stale telemetry (> 15 seconds without data).
        Returns: (color, list_of_breached_conditions)
        """
        if is_stale or operational_status == "OFFLINE":
            return "grey", ["Offline / Stale Telemetry"]

        if operational_status == "FAULT":
            return "red", ["Asset Fault State"]

        breaches: list[str] = []
        is_alarm_red = False
        is_warning_amber = False

        if operational_status in ("IDLE", "STOPPED"):
            is_warning_amber = True

        # Check metric limits defined in template
        for m_def in template.metrics:
            if m_def.name not in raw_metrics:
                continue
            val = raw_metrics[m_def.name]

            # High-High Alarm
            if m_def.hi_hi is not None and val >= m_def.hi_hi:
                is_alarm_red = True
                breaches.append(f"{m_def.name} ({val} {m_def.unit}) >= Critical High {m_def.hi_hi}")
            # Low-Low Alarm
            elif m_def.lo_lo is not None and val <= m_def.lo_lo:
                is_alarm_red = True
                breaches.append(f"{m_def.name} ({val} {m_def.unit}) <= Critical Low {m_def.lo_lo}")
            # High Warning
            elif m_def.hi is not None and val >= m_def.hi:
                is_warning_amber = True
                breaches.append(f"{m_def.name} ({val} {m_def.unit}) >= Warning High {m_def.hi}")
            # Low Warning
            elif m_def.lo is not None and val <= m_def.lo:
                is_warning_amber = True
                breaches.append(f"{m_def.name} ({val} {m_def.unit}) <= Warning Low {m_def.lo}")

        if is_alarm_red:
            return "red", breaches
        if is_warning_amber:
            return "amber", breaches

        return "green", []
