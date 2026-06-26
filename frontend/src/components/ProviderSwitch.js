import { jsxs as _jsxs, jsx as _jsx } from "react/jsx-runtime";
import { useStore } from '../store';
export function ProviderSwitch() {
    const providerName = useStore((s) => s.providerName);
    const providers = useStore((s) => s.availableProviders);
    const setProvider = useStore((s) => s.setProvider);
    return (_jsxs("select", { value: providerName, onChange: (e) => setProvider(e.target.value), title: "\u5207\u6362 LLM", children: [providers.map((p) => (_jsxs("option", { value: p.name, disabled: !p.enabled, children: [labelOf(p.name, p.model), !p.enabled ? '（未配置）' : ''] }, p.name))), providers.length === 0 && (_jsx("option", { value: providerName, children: labelOf(providerName, '') }))] }));
}
function labelOf(name, model) {
    switch (name) {
        case 'zhipu':
            return model ? `智谱 ${model}` : '智谱';
        case 'volcengine':
            return model ? `火山方舟 ${shorten(model)}` : '火山方舟';
        case 'deepseek':
            return model ? `DeepSeek ${model}` : 'DeepSeek';
        case 'minimax':
            return model ? `MiniMax ${model}` : 'MiniMax';
        default:
            return model ? `${name} (${model})` : name;
    }
}
function shorten(s) {
    if (s.length <= 18)
        return s;
    return s.slice(0, 8) + '…' + s.slice(-6);
}
