'use strict';

const message = document.getElementById('flowMessage');
const token = new URLSearchParams(window.location.search).get('token');

async function verifyEmail() {
    if (!token) {
        message.textContent = '인증 토큰이 없습니다. 이메일의 인증 링크를 다시 확인하세요.';
        return;
    }
    try {
        await window.feedApi.request('/api/auth/email/verification/confirm', {
            method: 'POST', body: JSON.stringify({ token })
        });
        message.textContent = '이메일 인증이 완료되었습니다. 이제 로그인할 수 있습니다.';
        const cleanUrl = new URL(window.location.href);
        cleanUrl.searchParams.delete('token');
        window.history.replaceState(null, '', cleanUrl);
    } catch (error) {
        message.textContent = error.message;
    }
}

verifyEmail();
