import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useState } from 'react';
import { useStore } from '../store';
import { api } from '../api/client';
import { ProviderSwitch } from './ProviderSwitch';
const EXAMPLES = [
    '画一个内切圆半径为 3 的等腰三角形',
    '画一个等边三角形 ABC，边长为 4',
    '画一个直角三角形 ABC，C 为直角顶点，BC=3，CA=4',
    '画一个边长为 5 的正方形 ABCD',
    '画圆 O，半径为 5，A、B 两点在圆上，AOB 角为 90 度',
];
export function TopBar() {
    const sessionId = useStore((s) => s.sessionId);
    const seq = useStore((s) => s.seq);
    const busy = useStore((s) => s.busy);
    const newSession = useStore((s) => s.newSession);
    const undo = useStore((s) => s.undo);
    const redo = useStore((s) => s.redo);
    const [exportOpen, setExportOpen] = useState(false);
    const canExport = !!sessionId && seq > 0;
    const canUndo = !!sessionId && seq > 0;
    return (_jsxs("div", { className: "topbar", children: [_jsxs("div", { className: "brand", children: ["\u8BDD\u56FE T2G", _jsx("span", { className: "sub", children: "\u7528\u4E00\u53E5\u8BDD\u753B\u51E0\u4F55" })] }), _jsx("button", { onClick: () => newSession(), disabled: busy, title: "\u65B0\u5EFA\u4F1A\u8BDD", children: "+ \u65B0\u4F1A\u8BDD" }), _jsx("button", { onClick: () => undo(), disabled: !canUndo || busy, title: "\u64A4\u9500", children: "\u2190 \u64A4\u9500" }), _jsx("button", { onClick: () => redo(), disabled: !sessionId || busy, title: "\u91CD\u505A", children: "\u91CD\u505A \u2192" }), _jsx("div", { className: "spacer" }), _jsxs("span", { style: { fontSize: 11, color: 'var(--muted)' }, children: ["seq #", seq] }), _jsx(ProviderSwitch, {}), _jsxs("div", { className: "dropdown-wrap", children: [_jsx("button", { onClick: () => setExportOpen((v) => !v), disabled: !canExport, children: "\u5BFC\u51FA \u25BE" }), exportOpen && (_jsx("div", { className: "dropdown-menu", onMouseLeave: () => setExportOpen(false), children: ['svg', 'png', 'pdf'].map((fmt) => (_jsxs("button", { onClick: () => {
                                if (!sessionId)
                                    return;
                                window.open(api.exportUrl(sessionId, fmt), '_blank');
                                setExportOpen(false);
                            }, children: ["\u5BFC\u51FA ", fmt.toUpperCase()] }, fmt))) }))] })] }));
}
function ProviderSwitchWrap() {
    return _jsx(ProviderSwitch, {});
}
export function ExampleHints({ onClick }) {
    return (_jsxs("div", { style: { display: 'flex', flexDirection: 'column', gap: 4 }, children: [_jsx("div", { style: { fontSize: 11, color: 'var(--muted)' }, children: "\u8BD5\u8BD5\uFF1A" }), EXAMPLES.map((ex) => (_jsx("button", { onClick: () => onClick(ex), style: { textAlign: 'left', fontSize: 12, padding: '4px 8px' }, children: ex }, ex)))] }));
}
