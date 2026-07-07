import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useEffect } from 'react';
import { Canvas } from './components/Canvas';
import { ChatPanel } from './components/ChatPanel';
import { RightPanel } from './components/RightPanel';
import { TopBar } from './components/TopBar';
import { useStore } from './store';
export function App() {
    const init = useStore((s) => s.init);
    const loading = useStore((s) => s.loading);
    const activeTab = useStore((s) => s.activeTab);
    const setActiveTab = useStore((s) => s.setActiveTab);
    const debugUI = useStore((s) => s.debugUI);
    useEffect(() => {
        init();
    }, [init]);
    if (loading) {
        return (_jsx("div", { style: {
                height: '100vh',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: 'var(--muted)',
            }, children: "\u8BDD\u56FE T2G \u542F\u52A8\u4E2D\u2026" }));
    }
    const tabClass = (tab) => `panel-wrap panel-${tab} ${activeTab === tab ? 'tab-active' : ''}`;
    return (_jsxs("div", { className: `app ${debugUI ? 'debug-ui' : 'prod-ui'}`, children: [_jsx(TopBar, {}), _jsxs("div", { className: "body", children: [_jsx("div", { className: tabClass('chat'), children: _jsx(ChatPanel, {}) }), _jsx("div", { className: tabClass('canvas'), children: _jsx(Canvas, {}) }), debugUI && (_jsx("div", { className: tabClass('objects'), children: _jsx(RightPanel, {}) }))] }), _jsx(MobileTabBar, { activeTab: activeTab, onChange: setActiveTab, debugUI: debugUI })] }));
}
function MobileTabBar({ activeTab, onChange, debugUI, }) {
    const tabs = [
        { id: 'chat', icon: '💬', label: '对话' },
        { id: 'canvas', icon: '📊', label: '画板' },
        ...(debugUI ? [{ id: 'objects', icon: '📐', label: '对象' }] : []),
    ];
    return (_jsx("div", { className: "mobile-tab-bar", children: tabs.map((t) => (_jsxs("button", { className: activeTab === t.id ? 'active' : '', onClick: () => onChange(t.id), children: [_jsx("span", { className: "tab-icon", children: t.icon }), _jsx("span", { children: t.label })] }, t.id))) }));
}
