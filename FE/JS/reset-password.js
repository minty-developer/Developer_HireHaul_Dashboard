'use strict';

const token = new URLSearchParams(window.location.search).get('token');
const form = document.getElementById('resetForm');
const newPassword = document.getElementById('newPassword');
const confirmPassword = document.getElementById('confirmPassword');
const message = document.getElementById('flowMessage');
const submit = document.getElementById('resetSubmit');

if (!token) {
    message.textContent = '재설정 토큰이 없습니다. 비밀번호 재설정 메일을 다시 요청하세요.';
    submit.disabled = true;
}

form.addEventListener('submit', async (event) => {
    event.preventDefault();
    message.textContent = '';
    if (!token) return;
    if (newPassword.value !== confirmPassword.value) {
        message.textContent = '두 비밀번호가 일치하지 않습니다.';
        confirmPassword.focus();
        return;
    }
    submit.disabled = true;
    try {
        await window.feedApi.request('/api/auth/password/reset/confirm', {
            method: 'POST', body: JSON.stringify({ token, new_password: newPassword.value })
        });
        form.reset();
        message.textContent = '비밀번호를 변경했습니다. 새 비밀번호로 로그인하세요.';
        document.getElementById('returnLink').textContent = '로그인하기';
        const cleanUrl = new URL(window.location.href);
        cleanUrl.searchParams.delete('token');
        window.history.replaceState(null, '', cleanUrl);
    } catch (error) {
        message.textContent = error.message;
    } finally { submit.disabled = false; }
});
