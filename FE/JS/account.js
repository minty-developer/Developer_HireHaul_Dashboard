'use strict';

const $ = (id) => document.getElementById(id);
const ui = {
    authPanel: $('authPanel'), userPanel: $('userPanel'), authForm: $('authForm'), authEmail: $('authEmail'),
    authPassword: $('authPassword'), displayNameField: $('displayNameField'), displayName: $('displayName'),
    authMessage: $('authMessage'), authSubmit: $('authSubmit'), recoveryMessage: $('recoveryMessage'),
    accountIdentity: $('accountIdentity'), accountNotice: $('accountNotice'), profileForm: $('profileForm'),
    profileName: $('profileDisplayName'), profileMessage: $('profileMessage'), passwordForm: $('passwordForm'),
    currentPassword: $('currentPassword'), newPassword: $('newPassword'), passwordMessage: $('passwordMessage'),
    deleteForm: $('deleteAccountForm'), deletePassword: $('deleteAccountPassword'), deleteMessage: $('deleteAccountMessage')
};
const state = { mode: 'login', user: null, throttleTimer: null };
const nextPage = new URLSearchParams(window.location.search).get('next');

function setMode(mode) {
    state.mode = mode;
    document.getElementById('authHeading').textContent = mode === 'login' ? '계정에 로그인' : '새 계정 만들기';
    ui.authSubmit.textContent = mode === 'login' ? '로그인' : '회원가입';
    ui.displayNameField.classList.toggle('hide', mode !== 'register');
    ui.displayName.required = mode === 'register';
    ui.authPassword.autocomplete = mode === 'login' ? 'current-password' : 'new-password';
    document.querySelectorAll('.authTab').forEach((tab) => {
        const active = tab.dataset.mode === mode;
        tab.classList.toggle('active', active);
        tab.setAttribute('aria-selected', String(active));
    });
    ui.authMessage.textContent = '';
    ui.recoveryMessage.textContent = '';
}

function showAuth(message = '') {
    ui.authPanel.classList.remove('hide');
    ui.userPanel.classList.add('hide');
    ui.authMessage.textContent = message;
}

function showAccount(user) {
    state.user = user;
    ui.authPanel.classList.add('hide');
    ui.userPanel.classList.remove('hide');
    ui.accountIdentity.textContent = `${user.display_name || user.email} · ${user.email} · ${user.email_verified ? '이메일 인증됨' : '이메일 미인증'}`;
    ui.profileName.value = user.display_name || '';
}

async function restoreAccount() {
    if (!window.feedApi.getToken()) {
        showAuth(new URLSearchParams(window.location.search).has('expired') ? '로그인 세션이 만료되었습니다. 다시 로그인해 주세요.' : '');
        return;
    }
    try {
        const payload = await window.feedApi.request('/api/auth/me');
        showAccount(payload?.user ?? payload);
    } catch (error) {
        if (error.status === 401) window.feedApi.clearToken();
        showAuth(error.status === 401 ? '로그인 세션이 만료되었습니다. 다시 로그인해 주세요.' : error.message);
    }
}

function throttleLogin(seconds) {
    clearInterval(state.throttleTimer);
    let remaining = seconds;
    ui.authSubmit.disabled = true;
    ui.authMessage.textContent = `${remaining}초 후 다시 로그인할 수 있습니다.`;
    state.throttleTimer = setInterval(() => {
        remaining -= 1;
        if (remaining <= 0) {
            clearInterval(state.throttleTimer);
            state.throttleTimer = null;
            ui.authSubmit.disabled = false;
            ui.authMessage.textContent = '다시 로그인할 수 있습니다.';
        } else ui.authMessage.textContent = `${remaining}초 후 다시 로그인할 수 있습니다.`;
    }, 1000);
}

async function submitAuth(event) {
    event.preventDefault();
    ui.authMessage.textContent = '';
    ui.authSubmit.disabled = true;
    const email = ui.authEmail.value.trim();
    const password = ui.authPassword.value;
    try {
        if (state.mode === 'register') {
            const payload = await window.feedApi.request('/api/auth/register', {
                method: 'POST', body: JSON.stringify({ email, password, display_name: ui.displayName.value.trim() })
            });
            ui.authForm.reset();
            setMode('login');
            ui.authEmail.value = email;
            ui.authMessage.textContent = payload?.verification_sent
                ? '가입을 완료했습니다. 이메일 인증 링크를 확인한 뒤 로그인하세요.'
                : '가입을 완료했습니다. 인증 메일을 받지 못했다면 다시 요청하세요.';
            return;
        }
        const payload = await window.feedApi.request('/api/auth/login', {
            method: 'POST', body: JSON.stringify({ email, password })
        });
        if (!payload?.token) throw new Error('로그인 응답에 토큰이 없습니다.');
        window.feedApi.setToken(payload.token);
        const destination = nextPage === 'subscriptions.html' ? 'subscriptions.html' : 'index.html';
        window.location.replace(destination);
    } catch (error) {
        ui.authMessage.textContent = error.status === 403
            ? '이메일 인증이 필요합니다. 인증 메일을 확인하거나 다시 요청하세요.'
            : error.message;
        if (error.status === 429 && error.retryAfterSeconds > 0) throttleLogin(error.retryAfterSeconds);
    } finally {
        if (!state.throttleTimer) ui.authSubmit.disabled = false;
    }
}

async function requestEmailAction(path, successMessage) {
    ui.recoveryMessage.textContent = '';
    if (!ui.authEmail.value.trim() || !ui.authEmail.checkValidity()) {
        ui.authEmail.reportValidity();
        return;
    }
    try {
        const payload = await window.feedApi.request(path, {
            method: 'POST', body: JSON.stringify({ email: ui.authEmail.value.trim() })
        });
        ui.recoveryMessage.textContent = payload?.message || successMessage;
    } catch (error) { ui.recoveryMessage.textContent = error.message; }
}

async function updateProfile(event) {
    event.preventDefault();
    ui.profileMessage.textContent = '';
    const displayName = ui.profileName.value.trim();
    if (!displayName || displayName.length > 50) {
        ui.profileMessage.textContent = '표시 이름은 공백을 제외하고 1~50자로 입력하세요.';
        return;
    }
    try {
        const payload = await window.feedApi.request('/api/auth/me', {
            method: 'PATCH', body: JSON.stringify({ display_name: displayName })
        });
        showAccount(payload?.user ?? payload);
        ui.profileMessage.textContent = '표시 이름을 저장했습니다.';
    } catch (error) { ui.profileMessage.textContent = error.message; }
}

async function changePassword(event) {
    event.preventDefault();
    ui.passwordMessage.textContent = '';
    if (ui.currentPassword.value === ui.newPassword.value) {
        ui.passwordMessage.textContent = '새 비밀번호는 현재 비밀번호와 달라야 합니다.';
        return;
    }
    try {
        await window.feedApi.request('/api/auth/password', {
            method: 'PUT', body: JSON.stringify({ current_password: ui.currentPassword.value, new_password: ui.newPassword.value })
        });
        const email = state.user?.email || '';
        window.feedApi.clearToken();
        ui.authForm.reset();
        setMode('login');
        ui.authEmail.value = email;
        showAuth('비밀번호가 변경되었습니다. 새 비밀번호로 다시 로그인하세요.');
        window.scrollTo({ top: 0, behavior: 'smooth' });
    } catch (error) { ui.passwordMessage.textContent = error.message; }
}

async function deleteAccount(event) {
    event.preventDefault();
    ui.deleteMessage.textContent = '';
    if (!window.confirm('계정을 탈퇴할까요? 이 작업은 되돌릴 수 없습니다.')) return;
    try {
        await window.feedApi.request('/api/auth/me', {
            method: 'DELETE', body: JSON.stringify({ password: ui.deletePassword.value })
        });
        window.feedApi.clearToken();
        window.location.replace('index.html');
    } catch (error) { ui.deleteMessage.textContent = error.message; }
}

async function logout() {
    try { await window.feedApi.request('/api/auth/logout', { method: 'POST' }); }
    catch (error) { if (error.status !== 401) console.warn('로그아웃 요청 실패:', error); }
    window.feedApi.clearToken();
    window.location.replace('index.html');
}

document.querySelectorAll('.authTab').forEach((tab) => tab.addEventListener('click', () => setMode(tab.dataset.mode)));
ui.authForm.addEventListener('submit', submitAuth);
document.getElementById('verificationResend').addEventListener('click', () => requestEmailAction('/api/auth/email/verification/request', '인증 메일을 요청했습니다.'));
document.getElementById('passwordResetRequest').addEventListener('click', () => requestEmailAction('/api/auth/password/reset/request', '비밀번호 재설정 메일을 요청했습니다.'));
ui.profileForm.addEventListener('submit', updateProfile);
ui.passwordForm.addEventListener('submit', changePassword);
ui.deleteForm.addEventListener('submit', deleteAccount);
document.getElementById('logoutButton').addEventListener('click', logout);

if (new URLSearchParams(window.location.search).has('expired')) {
    ui.authMessage.textContent = '로그인 세션이 만료되었습니다. 다시 로그인해 주세요.';
}
restoreAccount();
