import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useStore } from '../store';
export function ProviderSwitch() {
    const debugUI = useStore((s) => s.debugUI);
    const providerName = useStore((s) => s.providerName);
    const providers = useStore((s) => s.availableProviders);
    const setProvider = useStore((s) => s.setProvider);
    if (!debugUI)
        return null;
    const usable = providers.filter((p) => p.enabled);
    return (_jsx("div", { className: "provider-switch", children: _jsxs("select", { value: providerName, onChange: (e) => setProvider(e.target.value), title: "\u5207\u6362 LLM \u6A21\u578B", children: [usable.map((p) => (_jsx("option", { value: p.name, children: p.model || p.name }, p.name))), usable.length === 0 && (_jsx("option", { value: providerName, children: providerName }))] }) }));
}
