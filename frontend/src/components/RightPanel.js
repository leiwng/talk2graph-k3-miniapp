import { jsx as _jsx, jsxs as _jsxs, Fragment as _Fragment } from "react/jsx-runtime";
import { useStore } from '../store';
export function RightPanel() {
    const dsl = useStore((s) => s.dsl);
    const selected = useStore((s) => s.selectedObjectId);
    const select = useStore((s) => s.selectObject);
    const applyPatch = useStore((s) => s.applyPatch);
    const busy = useStore((s) => s.busy);
    if (!dsl) {
        return (_jsxs("section", { className: "right-panel", children: [_jsx("div", { className: "section-header", children: "\u5BF9\u8C61" }), _jsx("div", { style: { padding: 12, color: 'var(--muted)', fontSize: 12 }, children: "\uFF08\u7A7A\uFF09" })] }));
    }
    return (_jsxs("section", { className: "right-panel", children: [_jsxs("div", { className: "section-header", children: ["\u5BF9\u8C61 (", dsl.objects.length, ")"] }), _jsx("div", { className: "tree", children: dsl.objects.map((o) => (_jsx(ObjectItem, { obj: o, selected: selected === o.id, onClick: () => select(selected === o.id ? null : o.id) }, o.id))) }), _jsxs("div", { className: "section-header", children: ["\u7EA6\u675F (", dsl.constraints.length, ")"] }), _jsx("div", { className: "tree", style: { flex: 'none', maxHeight: '30%' }, children: dsl.constraints.map((c, i) => (_jsx(ConstraintItem, { c: c, disabled: busy, onChangeValue: async (newVal) => {
                        const ops = [
                            { op: 'replace', path: `/constraints/${i}/value`, value: newVal },
                        ];
                        await applyPatch(ops);
                    }, onRemove: async () => {
                        const ops = [{ op: 'remove', path: `/constraints/${i}` }];
                        await applyPatch(ops);
                    } }, i))) }), _jsx(PropertyPanel, {})] }));
}
function ObjectItem({ obj, selected, onClick, }) {
    const meta = describeObject(obj);
    return (_jsxs("div", { className: `tree-item ${selected ? 'selected' : ''}`, onClick: onClick, children: [_jsx("span", { children: _jsx("strong", { children: obj.id }) }), _jsx("span", { className: "meta", children: meta })] }));
}
function describeObject(o) {
    switch (o.kind) {
        case 'point':
            return '点';
        case 'segment':
            return `线段 ${o.a}${o.b}`;
        case 'line':
            return `直线 ${o.a}${o.b}`;
        case 'polygon':
            return `多边形 [${(o.vertices || []).join('')}]`;
        case 'circle': {
            const d = o.definition;
            if (!d)
                return '圆';
            switch (d.type) {
                case 'center_radius':
                    return `圆 (${d.center}, r=${d.radius})`;
                case 'center_through':
                    return `圆 (${d.center}, 过 ${d.through})`;
                case 'incircle':
                    return `内切圆 / ${d.of}`;
                case 'circumcircle':
                    return `外接圆 / ${d.of}`;
                default:
                    return '圆';
            }
        }
        default:
            return o.kind;
    }
}
function ConstraintItem({ c, disabled, onChangeValue, onRemove, }) {
    return (_jsxs("div", { className: "tree-item", title: JSON.stringify(c), children: [_jsx("span", { children: describeConstraint(c) }), _jsxs("span", { style: { display: 'flex', gap: 4, alignItems: 'center' }, children: [typeof c.value === 'number' && (_jsx("input", { type: "number", value: c.value, step: "0.5", style: { width: 60, fontSize: 11, padding: '2px 4px' }, disabled: disabled, onChange: (e) => {
                            const v = Number(e.target.value);
                            if (!Number.isNaN(v))
                                onChangeValue(v);
                        }, onClick: (e) => e.stopPropagation() })), _jsx("button", { onClick: (e) => {
                            e.stopPropagation();
                            onRemove();
                        }, disabled: disabled, style: { fontSize: 11, padding: '2px 6px' }, title: "\u5220\u9664\u7EA6\u675F", children: "\u00D7" })] })] }));
}
function describeConstraint(c) {
    switch (c.type) {
        case 'length':
            return `|${c.segment}| =`;
        case 'equal_length':
            return `等长 [${(c.segments || []).join(',')}]`;
        case 'angle':
            return `∠${c.a}${c.b}${c.c} =`;
        case 'parallel':
            return `${c.a} ∥ ${c.b}`;
        case 'perpendicular':
            return `${c.a} ⊥ ${c.b}`;
        case 'collinear':
            return `共线 [${(c.points || []).join('')}]`;
        case 'tangent':
            return `${c.line} 切 ${c.circle}`;
        case 'on_circle':
            return `${c.point} ∈ ${c.circle}`;
        case 'isoceles':
            return `${c.polygon} 等腰 @${c.apex}`;
        case 'equilateral':
            return `${c.polygon} 等边`;
        case 'right_triangle':
            return `${c.polygon} 直角@${c.right_at}`;
        case 'radius':
            return `r(${c.circle}) =`;
        default:
            return c.type;
    }
}
function PropertyPanel() {
    const dsl = useStore((s) => s.dsl);
    const solution = useStore((s) => s.solution);
    const selectedId = useStore((s) => s.selectedObjectId);
    const applyPatch = useStore((s) => s.applyPatch);
    const busy = useStore((s) => s.busy);
    if (!dsl || !selectedId) {
        return (_jsxs("div", { className: "properties", children: [_jsx("h4", { children: "\u5C5E\u6027" }), _jsx("div", { style: { color: 'var(--muted)' }, children: "\u70B9\u51FB\u5DE6\u4FA7\u5BF9\u8C61\u67E5\u770B\u5C5E\u6027" })] }));
    }
    const obj = dsl.objects.find((o) => o.id === selectedId);
    if (!obj)
        return null;
    const coord = solution?.coordinates?.[obj.id];
    const circle = solution?.circles?.[obj.id];
    const label = dsl.labels?.[obj.id] ?? obj.id;
    return (_jsxs("div", { className: "properties", children: [_jsxs("h4", { children: [obj.kind, " \u2014 ", obj.id] }), _jsxs("div", { className: "prop-row", children: [_jsx("label", { children: "\u6807\u7B7E" }), _jsx("input", { defaultValue: label, disabled: busy, onBlur: async (e) => {
                            const v = e.target.value;
                            if (v === label)
                                return;
                            await applyPatch([
                                { op: 'replace', path: `/labels/${obj.id}`, value: v },
                            ]);
                        } })] }), coord && (_jsxs(_Fragment, { children: [_jsxs("div", { className: "prop-row", children: [_jsx("label", { children: "X" }), _jsx("span", { className: "key", children: coord[0].toFixed(3) })] }), _jsxs("div", { className: "prop-row", children: [_jsx("label", { children: "Y" }), _jsx("span", { className: "key", children: coord[1].toFixed(3) })] })] })), circle && (_jsxs(_Fragment, { children: [_jsxs("div", { className: "prop-row", children: [_jsx("label", { children: "\u5706\u5FC3" }), _jsxs("span", { className: "key", children: ["(", circle.center[0].toFixed(3), ", ", circle.center[1].toFixed(3), ")"] })] }), _jsxs("div", { className: "prop-row", children: [_jsx("label", { children: "\u534A\u5F84" }), _jsx("span", { className: "key", children: circle.radius.toFixed(3) })] })] }))] }));
}
