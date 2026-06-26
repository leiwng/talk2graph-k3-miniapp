const BASE = '/api';
async function request(path, options = {}) {
    const r = await fetch(BASE + path, {
        headers: {
            'Content-Type': 'application/json',
            ...(options.headers || {}),
        },
        ...options,
    });
    if (!r.ok) {
        let detail = '';
        try {
            const j = await r.json();
            detail = j.detail ?? j.error ?? j;
        }
        catch {
            detail = await r.text();
        }
        // 后端 friendly error 是对象 {code, message, hint, detail}
        if (detail && typeof detail === 'object' && 'message' in detail) {
            const msg = detail.hint ? `${detail.message}（${detail.hint}）` : detail.message;
            const err = new Error(msg);
            err.code = detail.code;
            err.detail = detail.detail;
            throw err;
        }
        throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail));
    }
    return r.json();
}
export const api = {
    // session
    createSession(provider) {
        return request('/session', {
            method: 'POST',
            body: JSON.stringify({ llm_provider: provider ?? null }),
        });
    },
    getSession(sid) {
        return request(`/session/${sid}`);
    },
    deleteSession(sid) {
        return request(`/session/${sid}`, { method: 'DELETE' });
    },
    // dsl & history
    getCurrentDSL(sid) {
        return request(`/session/${sid}/dsl`);
    },
    getMessages(sid) {
        return request(`/session/${sid}/messages`);
    },
    getHistory(sid) {
        return request(`/session/${sid}/history`);
    },
    // chat
    chat(sid, nl, provider) {
        return request(`/session/${sid}/chat`, {
            method: 'POST',
            body: JSON.stringify({ nl, provider: provider ?? null }),
        });
    },
    // direct patch (property panel)
    patch(sid, ops) {
        return request(`/session/${sid}/patch`, {
            method: 'POST',
            body: JSON.stringify({ ops }),
        });
    },
    // undo / redo
    undo(sid) {
        return request(`/session/${sid}/undo`, { method: 'POST' });
    },
    redo(sid) {
        return request(`/session/${sid}/redo`, { method: 'POST' });
    },
    // feedback
    sendFeedback(sid, rating, comment) {
        return request(`/session/${sid}/feedback`, {
            method: 'POST',
            body: JSON.stringify({ rating, comment: comment ?? null }),
        });
    },
    // providers
    listProviders() {
        return request('/providers');
    },
    // export urls (browser navigates directly)
    exportUrl(sid, fmt) {
        return `${BASE}/export/${sid}.${fmt}`;
    },
};
