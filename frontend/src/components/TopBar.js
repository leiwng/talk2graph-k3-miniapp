import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useState } from 'react';
import { useStore } from '../store';
import { api } from '../api/client';
import { ProviderSwitch } from './ProviderSwitch';
export const EXAMPLES = [
    {
        icon: '△',
        title: '等边三角形',
        desc: '边长为 4 的正三角形',
        nl: '画一个等边三角形 ABC，边长为 4',
    },
    {
        icon: '∟',
        title: '直角三角形',
        desc: '直角边 3 和 4，含直角标记',
        nl: '画一个直角三角形 ABC，C 为直角顶点，BC=3，CA=4',
    },
    {
        icon: '□',
        title: '正方形',
        desc: '边长 5，标注所有顶点',
        nl: '画一个边长为 5 的正方形 ABCD',
    },
    {
        icon: '○',
        title: '圆与圆心角',
        desc: '半径 5，圆心角 90°',
        nl: '画圆 O，半径为 5，A、B 两点在圆上，∠AOB=90°',
    },
    {
        icon: '△',
        title: '等腰 + 内切圆',
        desc: '内切圆半径为 3',
        nl: '画一个内切圆半径为 3 的等腰三角形',
    },
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
    return (_jsxs("div", { className: "topbar", children: [_jsxs("div", { className: "brand", children: [_jsx("span", { className: "logo", children: "\u8BDD" }), _jsx("span", { className: "name", children: "\u8BDD\u56FE T2G" }), _jsx("span", { className: "sub", children: "\u7528\u4E00\u53E5\u8BDD\u753B\u51E0\u4F55" })] }), _jsx("button", { onClick: () => newSession(), disabled: busy, title: "\u65B0\u5EFA\u4F1A\u8BDD", children: "+ \u65B0\u4F1A\u8BDD" }), _jsx("button", { onClick: () => undo(), disabled: !canUndo || busy, title: "\u64A4\u9500", children: "\u2190 \u64A4\u9500" }), _jsx("button", { onClick: () => redo(), disabled: !sessionId || busy, title: "\u91CD\u505A", children: "\u91CD\u505A \u2192" }), _jsx("div", { className: "spacer" }), _jsxs("span", { className: "seq-info", style: { fontSize: 11, color: 'var(--muted)' }, children: ["seq #", seq] }), _jsx(ProviderSwitch, {}), _jsxs("div", { className: "dropdown-wrap", children: [_jsx("button", { onClick: () => setExportOpen((v) => !v), disabled: !canExport, children: "\u5BFC\u51FA \u25BE" }), exportOpen && (_jsx("div", { className: "dropdown-menu", onMouseLeave: () => setExportOpen(false), children: ['svg', 'png', 'pdf'].map((fmt) => (_jsxs("button", { onClick: () => {
                                if (!sessionId)
                                    return;
                                window.open(api.exportUrl(sessionId, fmt), '_blank');
                                setExportOpen(false);
                            }, children: ["\u5BFC\u51FA ", fmt.toUpperCase()] }, fmt))) }))] })] }));
}
