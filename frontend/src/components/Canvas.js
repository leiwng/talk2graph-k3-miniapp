import { jsx as _jsx, jsxs as _jsxs, Fragment as _Fragment } from "react/jsx-runtime";
import { useEffect, useRef, useState } from 'react';
import { useStore } from '../store';
export function Canvas() {
    const svg = useStore((s) => s.svg);
    const dsl = useStore((s) => s.dsl);
    const solution = useStore((s) => s.solution);
    const seq = useStore((s) => s.seq);
    const busy = useStore((s) => s.busy);
    const selectedId = useStore((s) => s.selectedObjectId);
    const selectObject = useStore((s) => s.selectObject);
    const applyPatch = useStore((s) => s.applyPatch);
    const containerRef = useRef(null);
    const [hover, setHover] = useState(null);
    // 注入交互：hover / 点击选中 / 拖动点
    useEffect(() => {
        const root = containerRef.current;
        if (!root || !dsl)
            return;
        const svgEl = root.querySelector('svg');
        if (!svgEl)
            return;
        const objs = svgEl.querySelectorAll('[data-id]');
        const handlers = [];
        // 拖动状态：单次注册到 document，避免离开元素丢失 mouseup
        let dragging = null;
        const onWindowMove = (e) => {
            if (!dragging)
                return;
            // 实时更新 hover 信息为 "正在拖动 X"
            const rect = root.getBoundingClientRect();
            setHover({
                id: dragging.id,
                text: `拖动 ${dragging.id} 到此处（松手提交）`,
                x: e.clientX - rect.left,
                y: e.clientY - rect.top,
            });
        };
        const onWindowUp = async (e) => {
            if (!dragging)
                return;
            const moved = performance.now() - dragging.startedAt;
            const id = dragging.id;
            const draggingState = dragging;
            dragging = null;
            window.removeEventListener('mousemove', onWindowMove);
            window.removeEventListener('mouseup', onWindowUp);
            setHover(null);
            // 拖动太短认为是点击；不发 patch
            if (moved < 120)
                return;
            const math = clientToMath(svgEl, e.clientX, e.clientY);
            if (!math || !dsl)
                return;
            const idx = dsl.objects.findIndex((o) => o.id === id);
            if (idx < 0)
                return;
            const ops = [
                {
                    op: dsl.objects[idx].hint == null ? 'add' : 'replace',
                    path: `/objects/${idx}/hint`,
                    value: [math.x, math.y],
                },
            ];
            await applyPatch(ops);
        };
        objs.forEach((el) => {
            const id = el.getAttribute('data-id');
            if (id === selectedId)
                el.classList.add('t2g-selected');
            const onEnter = (e) => {
                if (dragging)
                    return;
                const rect = root.getBoundingClientRect();
                const text = describe(id, dsl, solution);
                setHover({ id, text, x: e.clientX - rect.left, y: e.clientY - rect.top });
            };
            const onLeave = () => {
                if (!dragging)
                    setHover(null);
            };
            const onDown = (e) => {
                e.stopPropagation();
                // 仅 point 支持拖动
                const obj = dsl.objects.find((o) => o.id === id);
                if (obj && obj.kind === 'point') {
                    dragging = { id, startedAt: performance.now() };
                    window.addEventListener('mousemove', onWindowMove);
                    window.addEventListener('mouseup', onWindowUp);
                }
                // 点击：选中（即使拖动也保留选中态）
                selectObject(selectedId === id ? null : id);
            };
            el.addEventListener('mouseenter', onEnter);
            el.addEventListener('mouseleave', onLeave);
            el.addEventListener('mousedown', onDown);
            handlers.push({ el, enter: onEnter, leave: onLeave, down: onDown });
        });
        return () => {
            handlers.forEach(({ el, enter, leave, down }) => {
                el.removeEventListener('mouseenter', enter);
                el.removeEventListener('mouseleave', leave);
                el.removeEventListener('mousedown', down);
                el.classList.remove('t2g-selected');
            });
            window.removeEventListener('mousemove', onWindowMove);
            window.removeEventListener('mouseup', onWindowUp);
        };
    }, [svg, selectedId, dsl, solution, selectObject, applyPatch]);
    return (_jsxs("section", { children: [_jsx("div", { className: "section-header", children: "\u753B\u677F" }), _jsxs("div", { className: "canvas-wrap", ref: containerRef, children: [svg ? (_jsx("div", { dangerouslySetInnerHTML: { __html: svg }, style: {
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                        } })) : dsl ? (_jsx("div", { className: "placeholder", children: busy ? '渲染中…' : '点击撤销/重做后会自动刷新画板' })) : (_jsxs("div", { className: "placeholder", children: ["\u8FD8\u6CA1\u6709\u56FE\u5F62\u3002", _jsx("br", {}), "\u5728\u5DE6\u4FA7\u8F93\u5165\"\u753B\u4E00\u4E2A\u7B49\u8FB9\u4E09\u89D2\u5F62\"\u8BD5\u8BD5\u3002"] })), hover && (_jsx("div", { className: "canvas-tooltip", style: { left: hover.x + 12, top: hover.y + 12 }, children: hover.text })), svg && _jsx(FeedbackOverlay, {})] }), _jsxs("div", { className: "canvas-footer", children: [_jsxs("span", { children: ["seq #", seq] }), solution && _jsxs("span", { children: ["\u6B8B\u5DEE\uFF1A", solution.residual.toExponential(2)] }), dsl && (_jsxs("span", { children: ["\u5BF9\u8C61 ", dsl.objects.length, " \u00B7 \u7EA6\u675F ", dsl.constraints.length] })), dsl && dsl.objects.some((o) => o.kind === 'point') && (_jsx("span", { style: { color: 'var(--muted)' }, children: "\u63D0\u793A\uFF1A\u53EF\u62D6\u52A8\u70B9\u91CD\u65B0\u6446\u4F4D" }))] })] }));
}
function clientToMath(svgEl, clientX, clientY) {
    // 通过 SVGPoint matrixTransform 得到 SVG 内坐标
    const pt = svgEl.createSVGPoint();
    pt.x = clientX;
    pt.y = clientY;
    const ctm = svgEl.getScreenCTM();
    if (!ctm)
        return null;
    const inv = ctm.inverse();
    const local = pt.matrixTransform(inv);
    const scale = Number(svgEl.dataset.t2gScale || '1');
    const offsetX = Number(svgEl.dataset.t2gOffsetX || '0');
    const offsetY = Number(svgEl.dataset.t2gOffsetY || '0');
    const minX = Number(svgEl.dataset.t2gBboxMinx || '0');
    const minY = Number(svgEl.dataset.t2gBboxMiny || '0');
    const cs = Number(svgEl.dataset.t2gCanvasSize || '480');
    const mx = minX + (local.x - offsetX) / scale;
    const my = minY + (cs - offsetY - local.y) / scale;
    return { x: mx, y: my };
}
function describe(id, dsl, sol) {
    if (!dsl)
        return id;
    const obj = dsl.objects.find((o) => o.id === id);
    if (!obj)
        return id;
    const label = dsl.labels?.[id] ?? id;
    switch (obj.kind) {
        case 'point': {
            const c = sol?.coordinates?.[id];
            if (c)
                return `${label}(${c[0].toFixed(2)}, ${c[1].toFixed(2)})`;
            return `点 ${label}`;
        }
        case 'segment': {
            const a = sol?.coordinates?.[obj.a];
            const b = sol?.coordinates?.[obj.b];
            if (a && b) {
                const d = Math.hypot(a[0] - b[0], a[1] - b[1]);
                return `|${obj.a}${obj.b}| = ${d.toFixed(2)}`;
            }
            return `线段 ${obj.a}${obj.b}`;
        }
        case 'circle': {
            const info = sol?.circles?.[id];
            if (info)
                return `圆 ${id}：r = ${info.radius.toFixed(2)}`;
            return `圆 ${id}`;
        }
        case 'polygon':
            return `多边形 [${(obj.vertices || []).join('')}]`;
        default:
            return `${obj.kind} ${id}`;
    }
}
function FeedbackOverlay() {
    const sendFeedback = useStore((s) => s.sendFeedback);
    const seq = useStore((s) => s.seq);
    const [sent, setSent] = useState(null);
    const [showBadInput, setShowBadInput] = useState(false);
    const [comment, setComment] = useState('');
    // 切换图形（seq 变）时重置
    useEffect(() => {
        setSent(null);
        setShowBadInput(false);
        setComment('');
    }, [seq]);
    const onGood = async () => {
        setSent('good');
        await sendFeedback('good');
    };
    const onBad = () => {
        setShowBadInput(true);
    };
    const submitBad = async () => {
        setSent('bad');
        await sendFeedback('bad', comment.trim() || undefined);
        setShowBadInput(false);
    };
    if (sent) {
        return (_jsx("div", { className: "feedback-overlay sent", children: _jsx("span", { style: { fontSize: 11 }, children: "\u5DF2\u6536\u5230\u53CD\u9988\uFF0C\u8C22\u8C22 \uD83D\uDE4F" }) }));
    }
    return (_jsx("div", { className: "feedback-overlay", children: !showBadInput ? (_jsxs(_Fragment, { children: [_jsx("button", { className: "feedback-btn", onClick: onGood, title: "\u8FD9\u9053\u9898\u753B\u5BF9\u4E86", children: "\uD83D\uDC4D \u4E0D\u9519" }), _jsx("button", { className: "feedback-btn", onClick: onBad, title: "\u8FD9\u9053\u9898\u753B\u9519\u4E86", children: "\uD83D\uDC4E \u4E0D\u5BF9" })] })) : (_jsxs("div", { className: "feedback-comment-box", children: [_jsx("input", { type: "text", placeholder: "\u54EA\u91CC\u4E0D\u5BF9\uFF1F\uFF08\u53EF\u9009\uFF09", value: comment, onChange: (e) => setComment(e.target.value), onKeyDown: (e) => {
                        if (e.key === 'Enter')
                            submitBad();
                        if (e.key === 'Escape')
                            setShowBadInput(false);
                    }, autoFocus: true, style: { width: 180 } }), _jsx("button", { onClick: submitBad, className: "primary", style: { fontSize: 11 }, children: "\u63D0\u4EA4" }), _jsx("button", { onClick: () => setShowBadInput(false), style: { fontSize: 11 }, children: "\u53D6\u6D88" })] })) }));
}
