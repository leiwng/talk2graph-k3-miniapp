import { jsx as _jsx, jsxs as _jsxs, Fragment as _Fragment } from "react/jsx-runtime";
import { useEffect, useRef, useState } from 'react';
import { useStore } from '../store';
import { EXAMPLES } from './TopBar';
export function ChatPanel() {
    const messages = useStore((s) => s.messages);
    const sendChat = useStore((s) => s.sendChat);
    const busy = useStore((s) => s.busy);
    const seq = useStore((s) => s.seq);
    const errorBanner = useStore((s) => s.errorBanner);
    const dismissError = useStore((s) => s.dismissError);
    const [text, setText] = useState('');
    const listRef = useRef(null);
    useEffect(() => {
        if (listRef.current) {
            listRef.current.scrollTop = listRef.current.scrollHeight;
        }
    }, [messages.length, errorBanner]);
    const submit = async () => {
        const v = text.trim();
        if (!v || busy)
            return;
        setText('');
        await sendChat(v);
    };
    const sendExample = async (nl) => {
        if (busy)
            return;
        setText('');
        await sendChat(nl);
    };
    const showWelcome = messages.length === 0 && seq === 0;
    return (_jsxs("section", { className: "chat-panel", children: [_jsx("div", { className: "section-header", children: "\u5BF9\u8BDD" }), _jsxs("div", { className: "chat-list", ref: listRef, children: [showWelcome && _jsx(WelcomeCard, { onPick: sendExample }), messages.map((m) => (_jsx(ChatMsgItem, { msg: m }, m.id))), errorBanner && (_jsxs("div", { className: "chat-msg error", children: ["\u26A0 ", errorBanner, _jsx("button", { onClick: dismissError, style: { marginLeft: 8, padding: '2px 6px', fontSize: 11 }, children: "\u5173\u95ED" })] }))] }), _jsxs("div", { className: "chat-input", children: [_jsx("textarea", { value: text, onChange: (e) => setText(e.target.value), placeholder: "\u8BD5\u8BD5\uFF1A\u753B\u4E00\u4E2A\u7B49\u8FB9\u4E09\u89D2\u5F62 ABC\uFF0C\u8FB9\u957F\u4E3A 4", onKeyDown: (e) => {
                            if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
                                e.preventDefault();
                                submit();
                            }
                        }, disabled: busy }), _jsxs("div", { className: "actions", children: [_jsx("span", { className: "hint", children: "\u2318/Ctrl + Enter \u53D1\u9001" }), _jsx("button", { className: "primary", onClick: submit, disabled: busy || !text.trim(), children: busy ? '生成中…' : '发送' })] })] })] }));
}
function WelcomeCard({ onPick }) {
    return (_jsxs(_Fragment, { children: [_jsxs("div", { className: "welcome-card", children: [_jsx("h2", { className: "welcome-title", children: "\u4F60\u597D\uFF0C\u8001\u5E08 \uD83D\uDC4B" }), _jsx("p", { className: "welcome-desc", children: "\u8BF4\u4E00\u53E5\u8BDD\uFF0C\u6211\u5C31\u7ED9\u4F60\u753B\u51E0\u4F55\u56FE\u5F62\u3002\u652F\u6301\u521D\u4E2D\u5E73\u9762\u51E0\u4F55\u3001\u5750\u6807\u7CFB\u3001\u51FD\u6570\u56FE\u50CF\u3001\u51E0\u4F55\u53D8\u6362\u3002" }), _jsxs("div", { className: "welcome-features", children: [_jsxs("div", { className: "feature-row", children: [_jsx("span", { className: "check", children: "\u2713" }), _jsx("span", { children: "\u81EA\u7136\u8BED\u8A00\u4F5C\u56FE\uFF0C\u65E0\u9700\u624B\u52A8\u62D6\u62FD" })] }), _jsxs("div", { className: "feature-row", children: [_jsx("span", { className: "check", children: "\u2713" }), _jsx("span", { children: "\u652F\u6301\u7B49\u957F\u3001\u89D2\u5EA6\u3001\u76F8\u5207\u3001\u5171\u7EBF\u3001\u7B49\u8170\u7B49\u7EA6\u675F" })] }), _jsxs("div", { className: "feature-row", children: [_jsx("span", { className: "check", children: "\u2713" }), _jsx("span", { children: "\u53EF\u5BFC\u51FA SVG / PNG / PDF \u7528\u4E8E\u8BFE\u4EF6" })] })] })] }), _jsx("div", { className: "example-grid", children: EXAMPLES.map((ex) => (_jsxs("button", { className: "example-card", onClick: () => onPick(ex.nl), children: [_jsx("span", { className: "icon", children: ex.icon }), _jsxs("span", { className: "text", children: [_jsx("span", { className: "title", children: ex.title }), _jsx("span", { className: "desc", children: ex.desc })] })] }, ex.nl))) })] }));
}
function ChatMsgItem({ msg }) {
    if (msg.role === 'user') {
        return (_jsx("div", { className: `chat-msg user ${msg.pending ? 'pending' : ''}`, children: msg.content }));
    }
    // 思考占位（V2-D SSE 流式）
    // 新格式：__stream__:<json>，含 stage + objects 列表
    // 旧格式：__thinking__ 或 __stage__:xxx（向后兼容）
    const stageText = {
        llm: '正在理解题意',
        fallback: '正在切换备选模型',
        patch: '正在修改图形',
        solve: '正在求解几何约束',
        repair: '图形不收敛，正在尝试修正',
        render: '正在渲染图形',
    };
    if (msg.content.startsWith('__stream__:')) {
        try {
            const state = JSON.parse(msg.content.slice('__stream__:'.length));
            const text = stageText[state.stage] || '话图正在思考中';
            return (_jsxs("div", { className: "chat-msg assistant thinking", children: [_jsxs("div", { className: "thinking-stage", children: [text, _jsxs("span", { className: "dots", children: [_jsx("span", { children: "." }), _jsx("span", { children: "." }), _jsx("span", { children: "." })] })] }), state.waiting && (_jsx("div", { className: "thinking-waiting", children: "AI \u6B63\u5728\u51C6\u5907\u8F93\u51FA\u2026" })), state.objects?.length > 0 && (_jsx("div", { className: "thinking-objects", children: state.objects.map((o, i) => (_jsxs("div", { className: "thinking-obj", children: ["\u2713 ", describeObject(o.id, o.kind)] }, i))) }))] }));
        }
        catch {
            // 解析失败回退到旧格式
        }
    }
    if (msg.content === '__thinking__' || msg.content.startsWith('__stage__:')) {
        const stage = msg.content.startsWith('__stage__:')
            ? msg.content.slice('__stage__:'.length) : '';
        const text = stageText[stage] || '话图正在思考中';
        return (_jsxs("div", { className: "chat-msg assistant thinking", children: [text, _jsxs("span", { className: "dots", children: [_jsx("span", { children: "." }), _jsx("span", { children: "." }), _jsx("span", { children: "." })] })] }));
    }
    // 按 error_kind 分色
    if (msg.error_kind === 'refuse') {
        return (_jsx("div", { className: "chat-msg refuse", children: _jsx("div", { style: { whiteSpace: 'pre-wrap' }, children: msg.content }) }));
    }
    if (msg.error_kind === 'solve') {
        return (_jsxs("div", { className: "chat-msg solve-error", children: ["\uD83D\uDD27 ", msg.content] }));
    }
    if (msg.error_kind === 'patch') {
        return (_jsxs("div", { className: "chat-msg solve-error", children: ["\u2699 ", msg.content] }));
    }
    if (msg.error_kind === 'network') {
        return (_jsxs("div", { className: "chat-msg error", children: ["\u26A0 ", msg.content] }));
    }
    // 正常 assistant：尝试解析 JSON 给出摘要
    let preview = msg.content;
    try {
        const j = JSON.parse(msg.content);
        const objs = j.objects?.length ?? '?';
        const cons = j.constraints?.length ?? '?';
        preview = `✓ 图形已更新（${objs} 个对象，${cons} 条约束）`;
    }
    catch {
        /* 文本消息原样 */
    }
    return (_jsxs("div", { className: "chat-msg assistant", children: [msg.fallback && (_jsx("div", { className: "fallback-hint", children: "\uFF08AI \u7B2C\u4E00\u6B21\u8F93\u51FA\u4E0E\u73B0\u6709\u56FE\u5F62\u6709\u51B2\u7A81\uFF0C\u5DF2\u81EA\u52A8\u91CD\u65B0\u7406\u89E3\u4E3A\u91CD\u753B\uFF09" })), preview] }));
}
// V2-D：把 (id, kind) 翻译成中文描述，给 thinking 气泡的"已识别对象"列表用
function describeObject(id, kind) {
    switch (kind) {
        case 'point': return `点 ${id}`;
        case 'segment': return `线段 ${id}`;
        case 'line': return `直线 ${id}`;
        case 'circle': return `圆 ${id}`;
        case 'polygon': return `多边形 ${id}`;
        case 'axis': return `坐标系 ${id}`;
        case 'curve': return `曲线 ${id}`;
        case 'transformed_point': return `派生点 ${id}`;
        case 'transformed_polygon': return `变换多边形 ${id}`;
        default: return `${id} (${kind})`;
    }
}
