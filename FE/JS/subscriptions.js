'use strict';

const $ = (id) => document.getElementById(id);
const ui = {
    prompt: $('authPrompt'), promptMessage: $('authPromptMessage'), manager: $('subscriptionManager'), form: $('subscriptionForm'),
    keyword: $('keywordInput'), webhook: $('webhookInput'), message: $('subscriptionMessage'),
    list: $('subscriptionList'), refresh: $('refreshSubscriptions')
};

async function api(path, options) {
    try { return await window.feedApi.request(path, options); }
    catch (error) {
        if (error.status === 401) {
            window.feedApi.clearToken();
            window.location.replace('account.html?expired=1&next=subscriptions.html');
        }
        throw error;
    }
}

function setSignedIn(signedIn) {
    ui.prompt.classList.toggle('hide', signedIn);
    ui.manager.classList.toggle('hide', !signedIn);
}

function makeAction(label, className = 'textAction') {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = className;
    button.textContent = label;
    return button;
}

async function loadSubscriptions() {
    if (!window.feedApi.getToken()) {
        setSignedIn(false);
        return;
    }
    setSignedIn(true);
    ui.promptMessage.textContent = '구독을 관리하려면 로그인하세요.';
    ui.message.textContent = '구독을 불러오는 중…';
    try {
        const payload = await api('/api/subscriptions');
        renderSubscriptions(Array.isArray(payload?.subscriptions) ? payload.subscriptions : []);
        ui.message.textContent = '';
    } catch (error) {
        if (error.status === 401) {
            window.feedApi.clearToken();
            setSignedIn(false);
            ui.message.textContent = '로그인 세션이 만료되었습니다. 다시 로그인해 주세요.';
        } else ui.message.textContent = error.message;
    }
}

function renderSubscriptions(subscriptions) {
    ui.list.replaceChildren();
    if (!subscriptions.length) {
        const empty = document.createElement('p');
        empty.className = 'flowHint';
        empty.textContent = '등록된 키워드가 없습니다.';
        ui.list.append(empty);
        return;
    }
    subscriptions.forEach((subscription) => {
        const row = document.createElement('article');
        row.className = 'managedSubscription';
        const isActive = subscription.active === 1 || subscription.active === true;
        const details = document.createElement('div');
        const title = document.createElement('h3');
        title.textContent = subscription.keyword;
        const status = document.createElement('p');
        status.className = 'flowHint';
        status.textContent = `${isActive ? '구독 중' : '일시정지'} · ${subscription.discord_webhook_url ? '웹훅 등록됨 · 실제 알림 발송 대기 중' : '웹훅 미설정'}`;
        details.append(title, status);

        const actions = document.createElement('div');
        actions.className = 'managedActions';
        const toggle = makeAction(isActive ? '일시정지' : '다시 켜기');
        const webhook = makeAction(subscription.discord_webhook_url ? '웹훅 변경' : '웹훅 연결');
        const remove = makeAction('삭제', 'dangerAction');
        toggle.addEventListener('click', async () => {
            try {
                await api(`/api/subscriptions/${encodeURIComponent(subscription.id)}`, {
                    method: 'PATCH', body: JSON.stringify({ active: !isActive })
                });
                await loadSubscriptions();
                ui.message.textContent = isActive ? '키워드 알림을 일시정지했습니다.' : '키워드 알림을 다시 켰습니다.';
            } catch (error) { ui.message.textContent = error.message; }
        });
        webhook.addEventListener('click', async () => {
            const url = window.prompt('Discord 웹훅 URL을 입력하세요. 비우면 연결을 해제합니다.', subscription.discord_webhook_url || '');
            if (url === null) return;
            try {
                await api(`/api/subscriptions/${encodeURIComponent(subscription.id)}`, {
                    method: 'PATCH', body: JSON.stringify({ discord_webhook_url: url.trim() || null })
                });
                await loadSubscriptions();
            } catch (error) { ui.message.textContent = error.message; }
        });
        remove.addEventListener('click', async () => {
            if (!window.confirm(`“${subscription.keyword}” 구독을 삭제할까요?`)) return;
            try {
                await api(`/api/subscriptions/${encodeURIComponent(subscription.id)}`, { method: 'DELETE' });
                await loadSubscriptions();
                ui.message.textContent = '키워드 구독을 삭제했습니다.';
            } catch (error) { ui.message.textContent = error.message; }
        });
        actions.append(toggle, webhook, remove);
        row.append(details, actions);
        ui.list.append(row);
    });
}

async function createSubscription(event) {
    event.preventDefault();
    ui.message.textContent = '';
    try {
        await api('/api/subscriptions', {
            method: 'POST',
            body: JSON.stringify({ keyword: ui.keyword.value.trim(), discord_webhook_url: ui.webhook.value.trim() || undefined })
        });
        ui.form.reset();
        await loadSubscriptions();
        ui.message.textContent = '키워드 구독을 추가했습니다.';
    } catch (error) { ui.message.textContent = error.message; }
}

ui.form.addEventListener('submit', createSubscription);
ui.refresh.addEventListener('click', loadSubscriptions);
loadSubscriptions();
