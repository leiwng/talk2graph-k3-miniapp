"""安全表达式求值沙箱 (V2-B)

**核心用途**：把 LLM 输出的字符串 `"x**2"` / `"sin(x) + 1"` 编译为可调用的一元函数
`f(x) -> float`，用于函数图像采样。

**绝不使用** `eval(str)` —— LLM 只要输出 `__import__('os').system('rm')`
就是灾难。此处走 `ast.parse(mode="eval")` + **AST 节点白名单** 严格校验。

允许：
- 数字字面量 Constant/Num
- 变量 Name（仅白名单变量 x / y / 数学常量 pi / e）
- 算术 BinOp（+ - * / // % **）
- 一元 UnaryOp（+ / -）
- 函数调用 Call —— 但只能是白名单函数 sin/cos/tan/sqrt/exp/log/abs/pow ...
- 比较 Compare / 逻辑 BoolOp —— 用于 piecewise（暂不实现）

禁止：
- Attribute（`x.__class__` / `().__init__`）
- Subscript（`__builtins__['eval']`）
- Lambda / FunctionDef / Import / With / For / While / ...
- 未在白名单的 Name（如 `open` / `__import__`）
"""
from __future__ import annotations

import ast
import math
from typing import Callable

# ---------------------------------------------------------------------------
# 白名单
# ---------------------------------------------------------------------------

_ALLOWED_FUNCS: dict[str, Callable] = {
    "sqrt": math.sqrt,
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "asin": math.asin,
    "acos": math.acos,
    "atan": math.atan,
    "atan2": math.atan2,
    "exp": math.exp,
    "log": math.log,
    "log10": math.log10,
    "log2": math.log2,
    "abs": abs,
    "pow": pow,
    "floor": math.floor,
    "ceil": math.ceil,
}

_ALLOWED_CONSTS: dict[str, float] = {
    "pi": math.pi,
    "e": math.e,
}

# 允许出现的 AST 节点类型（用 tuple 便于 isinstance 检查）
_ALLOWED_NODES: tuple = (
    ast.Expression,
    ast.BinOp, ast.UnaryOp,
    ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod, ast.Pow,
    ast.USub, ast.UAdd,
    ast.Constant, ast.Num,          # Python 3.7-  Num；3.8+ 全部走 Constant
    ast.Name, ast.Load,
    ast.Call,
    ast.Compare, ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE,
    ast.BoolOp, ast.And, ast.Or,
    ast.IfExp,                       # 三元 A if cond else B
)


class UnsafeExpressionError(ValueError):
    """表达式含不允许的语法结构。"""


# ---------------------------------------------------------------------------
# 校验
# ---------------------------------------------------------------------------

def _validate_ast(node: ast.AST, allowed_names: set[str]) -> None:
    """递归遍历 AST，任何不合规节点都抛 UnsafeExpressionError。"""
    if not isinstance(node, _ALLOWED_NODES):
        raise UnsafeExpressionError(
            f"disallowed AST node type: {type(node).__name__}"
        )

    if isinstance(node, ast.Name):
        if node.id not in allowed_names:
            raise UnsafeExpressionError(f"unknown name: {node.id!r}")

    if isinstance(node, ast.Call):
        # 函数必须是 Name 且在白名单里
        if not isinstance(node.func, ast.Name):
            raise UnsafeExpressionError(
                "function call must be a plain name (no attribute / subscript)"
            )
        if node.func.id not in _ALLOWED_FUNCS:
            raise UnsafeExpressionError(f"function {node.func.id!r} not in whitelist")

    if isinstance(node, ast.Constant):
        # 只允许数字常量
        if not isinstance(node.value, (int, float)):
            raise UnsafeExpressionError(
                f"only numeric constants allowed, got {type(node.value).__name__}"
            )

    # 递归所有子节点
    for child in ast.iter_child_nodes(node):
        _validate_ast(child, allowed_names)


# ---------------------------------------------------------------------------
# 编译
# ---------------------------------------------------------------------------

def compile_expr(expr: str, var: str = "x") -> Callable[[float], float]:
    """把 expr 字符串编译成一元函数 `f(var_value) -> float`。

    Args:
        expr: 表达式字符串，如 `"x**2 + 1"` / `"sin(x)"` / `"1/x"`。
        var:  自变量名，默认 "x"。也可以是 "y"（用于 x = g(y) 形式）。

    Raises:
        UnsafeExpressionError: 表达式含不允许的语法。
        SyntaxError: 表达式语法错误（如括号不匹配）。

    Returns:
        callable `f(v: float) -> float`。运行时的 ZeroDivisionError /
        ValueError（如 sqrt 负数、log 非正数）由调用方处理为 nan。
    """
    if not isinstance(expr, str) or not expr.strip():
        raise UnsafeExpressionError("empty expression")

    # 允许的 Name 集合 = 白名单函数 ∪ 常量 ∪ 自变量
    allowed_names = set(_ALLOWED_FUNCS.keys()) | set(_ALLOWED_CONSTS.keys()) | {var}

    tree = ast.parse(expr, mode="eval")
    _validate_ast(tree, allowed_names)

    code = compile(tree, filename="<t2g-expr>", mode="eval")
    # 构造受限的 globals；显式清空 __builtins__ 阻止内建函数注入
    safe_globals = {"__builtins__": {}, **_ALLOWED_FUNCS, **_ALLOWED_CONSTS}

    def _f(v: float) -> float:
        local = {var: v}
        try:
            result = eval(code, safe_globals, local)  # noqa: S307 — 已 AST 校验
        except (ZeroDivisionError, ValueError, OverflowError):
            return float("nan")
        # 结果必须是数字
        if isinstance(result, bool):
            return float(result)
        if not isinstance(result, (int, float)):
            return float("nan")
        return float(result)

    return _f
