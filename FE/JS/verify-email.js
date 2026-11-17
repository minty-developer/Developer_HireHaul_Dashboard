'use strict';

const message = document.getElementById('flowMessage');
const token = new URLSearchParams(window.location.search).get('token');
const apiBaseUrl = window.FEED_API_BASE_URL || 'http://127.0.0.1:5000';

async function verifyEmail() {
    if (!token) {
        message.textContent = '인증 토큰이 없습니다. 이메일의 인증 링크를 다시 확인하세요.';
        return;
    }
    try {
        const response = await fetch(`${apiBaseUrl}/api/auth/email/verification/confirm`, {
            method: 'POST',
            headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
            body: JSON.stringify({ token })
        });
        const text = await response.text();
        const payload = text ? JSON.parse(text) : null;
        if (!response.ok || payload?.ok === false) throw new Error(payload?.error || '이메일 인증에 실패했습니다. 인증 링크를 다시 요청하세요.');
        message.textContent = '이메일 인증이 완료되었습니다. 이제 로그인할 수 있습니다.';
        const cleanUrl = new URL(window.location.href);
        cleanUrl.searchParams.delete('token');
        window.history.replaceState(null, '', cleanUrl);
    } catch (error) {
        message.textContent = error.name === 'SyntaxError' ? '서버 응답을 읽지 못했습니다.' : error.message;
    }
}

verifyEmail();
