'use strict';

(() => {
    const TOKEN_KEY = 'techBlogAggregatorToken';
    const API_TIMEOUT_MS = 65000;

    async function request(path, options = {}) {
        const controller = new AbortController();
        const timeout = setTimeout(() => controller.abort(), API_TIMEOUT_MS);
        const token = sessionStorage.getItem(TOKEN_KEY) || '';
        const headers = { Accept: 'application/json', ...options.headers };
        if (token) headers.Authorization = `Bearer ${token}`;
        if (options.body !== undefined && !headers['Content-Type']) headers['Content-Type'] = 'application/json';
        try {
            const response = await fetch(`${window.FEED_API_BASE_URL || 'https://tech-blog-aggregator.onrender.xn--com-db3mme233k'}${path}`, {
                ...options, headers, signal: controller.signal
            });
            if (response.status === 204) return null;
            const text = await response.text();
            let payload = null;
            if (text) {
                try { payload = JSON.parse(text); }
                catch { payload = { message: text }; }
            }
            if (!response.ok || payload?.ok === false) {
                const error = new Error(payload?.error || payload?.message || `요청에 실패했습니다. (${response.status})`);
                error.status = response.status;
                error.retryAfterSeconds = Number(response.headers.get('Retry-After')) || 0;
                throw error;
            }
            return payload;
        } finally { clearTimeout(timeout); }
    }

    window.feedApi = {
        request,
        getToken: () => sessionStorage.getItem(TOKEN_KEY) || '',
        setToken: (token) => sessionStorage.setItem(TOKEN_KEY, token),
        clearToken: () => sessionStorage.removeItem(TOKEN_KEY)
    };
})();
