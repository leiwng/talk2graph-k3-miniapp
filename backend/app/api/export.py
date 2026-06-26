"""导出路由：SVG / PNG / PDF（基于当前 DSL+solution）。"""
from __future__ import annotations

import io

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from ..render import render_svg
from ..session import repo as repo_mod
from .deps import db_dep, require_session

router = APIRouter(prefix="/api/export", tags=["export"])


def _load_cairosvg():
    try:
        import cairosvg  # noqa: WPS433

        return cairosvg
    except (OSError, ImportError) as e:
        raise HTTPException(
            501,
            detail=(
                "PNG/PDF 导出需要安装 cairo 原生库。macOS: brew install cairo；"
                f"详细：{e}"
            ),
        )


async def _current_svg(db: AsyncSession, sid: str) -> str:
    await require_session(db, sid)
    snap = await repo_mod.current_snapshot(db, sid)
    if snap is None or snap.solution is None:
        raise HTTPException(400, detail="no current dsl/solution")
    # 重新 render，确保 solution 中 list 转回 tuple 适配 renderer
    from ..solver.engine import Solution

    coords = {k: tuple(v) for k, v in snap.solution["coordinates"].items()}
    circles = {
        k: {"center": tuple(v["center"]), "radius": v["radius"]}
        for k, v in snap.solution.get("circles", {}).items()
    }
    sol = Solution(
        coordinates=coords,
        circles=circles,
        residual=snap.solution.get("residual", 0.0),
        method=snap.solution.get("method", "numeric"),
        iterations=0,
    )
    return render_svg(snap.dsl, sol)


@router.get("/{sid}.svg")
async def export_svg(sid: str, db: AsyncSession = Depends(db_dep)) -> Response:
    svg = await _current_svg(db, sid)
    return Response(svg, media_type="image/svg+xml")


@router.get("/{sid}.png")
async def export_png(sid: str, db: AsyncSession = Depends(db_dep)) -> Response:
    cairosvg = _load_cairosvg()
    svg = await _current_svg(db, sid)
    buf = io.BytesIO()
    cairosvg.svg2png(bytestring=svg.encode("utf-8"), write_to=buf, output_width=1024)
    return Response(buf.getvalue(), media_type="image/png")


@router.get("/{sid}.pdf")
async def export_pdf(sid: str, db: AsyncSession = Depends(db_dep)) -> Response:
    cairosvg = _load_cairosvg()
    svg = await _current_svg(db, sid)
    buf = io.BytesIO()
    cairosvg.svg2pdf(bytestring=svg.encode("utf-8"), write_to=buf)
    return Response(buf.getvalue(), media_type="application/pdf")
