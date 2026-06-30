import { jsx as _jsx, Fragment as _Fragment, jsxs as _jsxs } from "react/jsx-runtime";
import { useEffect, useRef, useState } from 'react';
import { useStore } from '../store';
import { ExampleHints } from './TopBar';
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
    return (_jsxs("section", { children: [_jsx("div", { className: "section-header", children: "\u5BF9\u8BDD" }), _jsxs("div", { className: "chat-list", ref: listRef, children: [messages.length === 0 && seq === 0 && (_jsxs(_Fragment, { children: [_jsx("div", { className: "chat-msg assistant", children: "\u4F60\u597D\uFF0C\u8001\u5E08\u3002\u8BF4\u4E00\u53E5\u8BDD\u6211\u5C31\u7ED9\u4F60\u753B\u56FE\u3002" }), _jsx(ExampleHints, { onClick: (t) => setText(t) })] })), messages.map((m) => (_jsx(ChatMsgItem, { msg: m }, m.id))), errorBanner && (_jsxs("div", { className: "chat-msg error", children: ["\u26A0 ", errorBanner, _jsx("button", { onClick: dismissError, style: { marginLeft: 8, padding: '2px 6px', fontSize: 11 }, children: "\u5173\u95ED" })] }))] }), _jsxs("div", { className: "chat-input", children: [_jsx("textarea", { value: text, onChange: (e) => setText(e.target.value), placeholder: "\u4F8B\u5982\uFF1A\u753B\u4E00\u4E2A\u5185\u5207\u5706\u534A\u5F84\u4E3A 3 \u7684\u7B49\u8170\u4E09\u89D2\u5F62", onKeyDown: (e) => {
                            if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
                                e.preventDefault();
                                submit();
                            }
                        }, disabled: busy }), _jsxs("div", { className: "actions", children: [_jsx("span", { className: "hint", children: "\u2318/Ctrl + Enter \u53D1\u9001" }), _jsx("button", { className: "primary", onClick: submit, disabled: busy || !text.trim(), children: busy ? '生成中…' : '发送' })] })] })] }));
}
function ChatMsgItem({ msg }) {
    if (msg.role === 'user') {
        return (_jsx("div", { className: `chat-msg user ${msg.pending ? 'pending' : ''}`, children: msg.content }));
    }
    // 思考占位
    if (msg.content === '__thinking__') {
        return (_jsxs("div", { className: "chat-msg assistant thinking", children: ["\u8BDD\u56FE\u6B63\u5728\u601D\u8003\u4E2D", _jsxs("span", { className: "dots", children: [_jsx("span", { children: "." }), _jsx("span", { children: "." }), _jsx("span", { children: "." })] })] }));
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
