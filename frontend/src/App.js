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
    return (_jsxs("div", { className: "app", children: [_jsx(TopBar, {}), _jsxs("div", { className: "body", children: [_jsx(ChatPanel, {}), _jsx(Canvas, {}), _jsx(RightPanel, {})] })] }));
}
