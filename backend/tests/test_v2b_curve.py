"""V2-B — 函数曲线（FunctionCurveObj + 安全表达式沙箱）测试。

覆盖：
1. safe_expr：白名单函数可用（sin/cos/sqrt/exp/log/abs）
2. safe_expr：拒绝 __import__ / eval / open / getattr 等注入
3. safe_expr：拒绝属性访问 / 下标访问 / lambda
4. schema：FunctionCurveObj 解析
5. validator：无 axis 时拒绝 curve
6. validator：不安全表达式在 DSL 层被拦下
7. render：y=x 输出至少一段 polyline，起止点符合期望
8. render：y=1/x 断点切段（≥ 2 段 polyline）
9. render：域外产生 nan 时被过滤
"""
from __future__ import annotations

import math

import pytest

from app.dsl.safe_expr import UnsafeExpressionError, compile_expr
from app.dsl.schema import DSL
from app.dsl.validator import DSLValidationError, validate
from app.render.svg import render_svg
from app.solver.engine import solve


# ---------------------------------------------------------------------------
# 1) safe_expr 白名单
# ---------------------------------------------------------------------------

def test_safe_expr_whitelist_math_funcs():
    f = compile_expr("sin(x) + cos(x)")
    assert abs(f(0.0) - 1.0) < 1e-9
    g = compile_expr("sqrt(x)")
    assert abs(g(4.0) - 2.0) < 1e-9
    h = compile_expr("abs(x) + exp(0)")
    assert abs(h(-3.0) - 4.0) < 1e-9


def test_safe_expr_supports_pi_e_and_pow():
    f = compile_expr("pi * x**2")
    assert abs(f(2.0) - math.pi * 4) < 1e-9
    g = compile_expr("e ** 0")
    assert abs(g(0.0) - 1.0) < 1e-9


def test_safe_expr_runtime_errors_return_nan():
    f = compile_expr("1/x")
    assert math.isnan(f(0.0))
    g = compile_expr("sqrt(x)")
    assert math.isnan(g(-1.0))
    h = compile_expr("log(x)")
    assert math.isnan(h(0.0))


# ---------------------------------------------------------------------------
# 2) safe_expr 拒绝危险语法
# ---------------------------------------------------------------------------

def test_safe_expr_rejects_import():
    with pytest.raises(UnsafeExpressionError):
        compile_expr("__import__('os').system('ls')")


def test_safe_expr_rejects_builtins():
    # open / eval / exec 都不在白名单
    with pytest.raises(UnsafeExpressionError):
        compile_expr("open('/etc/passwd')")
    with pytest.raises(UnsafeExpressionError):
        compile_expr("eval('1+1')")


def test_safe_expr_rejects_attribute_access():
    with pytest.raises(UnsafeExpressionError):
        compile_expr("(1).__class__")
    with pytest.raises(UnsafeExpressionError):
        compile_expr("x.__init__")


def test_safe_expr_rejects_subscript():
    with pytest.raises(UnsafeExpressionError):
        compile_expr("x[0]")


def test_safe_expr_rejects_lambda():
    with pytest.raises(UnsafeExpressionError):
        compile_expr("(lambda: 1)()")


def test_safe_expr_rejects_unknown_name():
    with pytest.raises(UnsafeExpressionError):
        compile_expr("foo(x)")   # 未知函数
    with pytest.raises(UnsafeExpressionError):
        compile_expr("y")        # 默认 var=x，y 未声明


def test_safe_expr_var_y():
    f = compile_expr("y**2", var="y")
    assert abs(f(3.0) - 9.0) < 1e-9


# ---------------------------------------------------------------------------
# 3) Schema
# ---------------------------------------------------------------------------

def test_curve_schema_parses():
    dsl = DSL.model_validate({
        "version": "0.1",
        "objects": [
            {"id": "O", "kind": "point"},
            {"id": "ax", "kind": "axis", "origin": "O"},
            {"id": "c1", "kind": "curve", "expr": "x**2", "var": "x",
             "domain": [-3, 3]},
        ],
    })
    validate(dsl)
    curves = dsl.curves()
    assert len(curves) == 1
    assert curves[0].expr == "x**2"
    assert curves[0].samples == 300  # 默认


# ---------------------------------------------------------------------------
# 4) Validator
# ---------------------------------------------------------------------------

def test_validator_rejects_curve_without_axis():
    bad = DSL.model_validate({
        "version": "0.1",
        "objects": [
            {"id": "c1", "kind": "curve", "expr": "x**2"},
        ],
    })
    with pytest.raises(DSLValidationError, match="requires an axis"):
        validate(bad)


def test_validator_rejects_unsafe_expr_in_dsl():
    bad = DSL.model_validate({
        "version": "0.1",
        "objects": [
            {"id": "O", "kind": "point"},
            {"id": "ax", "kind": "axis", "origin": "O"},
            {"id": "c1", "kind": "curve", "expr": "__import__('os').system('x')"},
        ],
    })
    with pytest.raises(DSLValidationError, match="unsafe or invalid"):
        validate(bad)


def test_validator_rejects_bad_domain():
    bad = DSL.model_validate({
        "version": "0.1",
        "objects": [
            {"id": "O", "kind": "point"},
            {"id": "ax", "kind": "axis", "origin": "O"},
            {"id": "c1", "kind": "curve", "expr": "x", "domain": [5, 3]},
        ],
    })
    with pytest.raises(DSLValidationError, match="domain min must"):
        validate(bad)


# ---------------------------------------------------------------------------
# 5) Render
# ---------------------------------------------------------------------------

def test_render_curve_linear():
    dsl = DSL.model_validate({
        "version": "0.1",
        "objects": [
            {"id": "O", "kind": "point"},
            {"id": "ax", "kind": "axis", "origin": "O", "x_range": [-3, 3], "y_range": [-3, 3]},
            {"id": "c1", "kind": "curve", "expr": "x", "domain": [-2, 2], "samples": 100},
        ],
    })
    validate(dsl)
    sol = solve(dsl)
    svg = render_svg(dsl, sol)
    assert 'data-id="c1"' in svg
    assert 't2g-curve' in svg
    assert '<polyline' in svg


def test_render_curve_reciprocal_splits_segments():
    """y=1/x 在 x=0 附近 y 值发散，应至少切成两段。"""
    dsl = DSL.model_validate({
        "version": "0.1",
        "objects": [
            {"id": "O", "kind": "point"},
            {"id": "ax", "kind": "axis", "origin": "O", "x_range": [-5, 5], "y_range": [-5, 5]},
            {"id": "c1", "kind": "curve", "expr": "1/x", "domain": [-3, 3], "samples": 401},
        ],
    })
    validate(dsl)
    sol = solve(dsl)
    svg = render_svg(dsl, sol)
    # 至少 2 段 polyline（负 x 一段 + 正 x 一段）
    assert svg.count('data-id="c1"') >= 2


def test_render_curve_filters_nan_out_of_domain():
    """y = sqrt(x)，域 [-2, 4]：负半段应被 nan 过滤后切段。"""
    dsl = DSL.model_validate({
        "version": "0.1",
        "objects": [
            {"id": "O", "kind": "point"},
            {"id": "ax", "kind": "axis", "origin": "O", "x_range": [-3, 5], "y_range": [-1, 3]},
            {"id": "c1", "kind": "curve", "expr": "sqrt(x)", "domain": [-2, 4], "samples": 300},
        ],
    })
    validate(dsl)
    sol = solve(dsl)
    svg = render_svg(dsl, sol)
    # 至少画出正 x 半段
    assert 'data-id="c1"' in svg


def test_render_curve_uses_axis_range_when_no_domain():
    """curve 未指定 domain 时使用 axis.x_range。"""
    dsl = DSL.model_validate({
        "version": "0.1",
        "objects": [
            {"id": "O", "kind": "point"},
            {"id": "ax", "kind": "axis", "origin": "O", "x_range": [-4, 4], "y_range": [-1, 16]},
            {"id": "c1", "kind": "curve", "expr": "x**2"},
        ],
    })
    validate(dsl)
    sol = solve(dsl)
    svg = render_svg(dsl, sol)
    assert 'data-id="c1"' in svg


def test_render_curve_var_y():
    """var='y' 时 x = g(y)：例如 x = y²（右开抛物线的下半支或全部）。"""
    dsl = DSL.model_validate({
        "version": "0.1",
        "objects": [
            {"id": "O", "kind": "point"},
            {"id": "ax", "kind": "axis", "origin": "O", "x_range": [-1, 5], "y_range": [-3, 3]},
            {"id": "c1", "kind": "curve", "expr": "y**2", "var": "y", "domain": [-2, 2]},
        ],
    })
    validate(dsl)
    sol = solve(dsl)
    svg = render_svg(dsl, sol)
    assert 'data-id="c1"' in svg
    assert 't2g-curve' in svg
