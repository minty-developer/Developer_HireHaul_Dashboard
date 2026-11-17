'use strict';

const API_BASE_URL = window.FEED_API_BASE_URL || 'http://127.0.0.1:5000';
const API_TIMEOUT_MS = 30000;
const SEARCH_DELAY_MS = 300;
const TOKEN_KEY = 'techBlogAggregatorToken';
const PAGE_SIZE_LIMIT = 100;

const $ = (id) => document.getElementById(id);
const ui = {
    search: $('searchInput'), source: $('sourceSelect'), from: $('fromDate'), to: $('toDate'),
    company: $('companySelect'), sort: $('sortSelect'), pageSize: $('pageSize'), cards: $('cards'), resultCount: $('resultCount'), loading: $('searchAction'),
    failed: $('searchFailed'), empty: $('searchEmpty'), retry: $('retryButton'), pagination: $('pagination'),
    prev: $('prevPage'), next: $('nextPage'), pageLabel: $('pageLabel'), tags: [...document.querySelectorAll('.tag')],
    blogList: $('blogList'), apiStatus: $('apiStatus'), apiStatusText: $('apiStatusText'), articleDialog: $('articleDialog'), dialogTitle: $('dialogTitle'),
    dialogMeta: $('dialogMeta'), dialogText: $('dialogText'), dialogLink: $('dialogLink'),
    authDialog: $('authDialog'), authOpen: $('authOpen'), accountOpen: $('accountOpen'), accountDialog: $('accountDialog'), logout: $('logoutButton'), userLabel: $('userLabel'),
    authForm: $('authForm'), authTitle: $('authTitle'), authMessage: $('authMessage'), authSubmit: $('authSubmit'),
    authEmail: $('authEmail'), authPassword: $('authPassword'), displayNameField: $('displayNameField'),
    displayName: $('displayName'), authRecoveryMessage: $('authRecoveryMessage'), accountIdentity: $('accountIdentity'), profileForm: $('profileForm'), profileName: $('profileDisplayName'), profileMessage: $('profileMessage'),
    passwordForm: $('passwordForm'), currentPassword: $('currentPassword'), newPassword: $('newPassword'), passwordMessage: $('passwordMessage'),
    deleteAccountForm: $('deleteAccountForm'), deleteAccountPassword: $('deleteAccountPassword'), deleteAccountMessage: $('deleteAccountMessage'),
    subscriptionDialog: $('subscriptionDialog'), subscriptionOpen: $('subscriptionOpen'),
    subscriptionForm: $('subscriptionForm'), keyword: $('keywordInput'), webhook: $('webhookInput'),
    subscriptionList: $('subscriptionList'), subscriptionMessage: $('subscriptionMessage'), subscriptionHint: $('subscriptionHint')
};

const state = {
    token: sessionStorage.getItem(TOKEN_KEY) || '', user: null, blogs: [], articles: [], total: 0,
    offset: 0, pageSize: 20, searchTimer: null, activeTag: '', topicCounts: null, activeArticleId: null, authThrottleTimer: null
};

function apiUrl(path) { return `${API_BASE_URL}${path}`; }
function authHeaders() { return state.token ? { Authorization: `Bearer ${state.token}` } : {}; }

async function api(path, options = {}) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), API_TIMEOUT_MS);
    const headers = { Accept: 'application/json', ...options.headers, ...authHeaders() };
    if (options.body !== undefined) headers['Content-Type'] = 'application/json';
    try {
        const response = await fetch(apiUrl(path), { ...options, headers, signal: controller.signal });
        setApiConnection(true);
        if (response.status === 204) return null;
        const text = await response.text();
        let payload = null;
        if (text) {
            try { payload = JSON.parse(text); } catch { payload = { message: text }; }
        }
        if (!response.ok) {
            const message = payload?.error || payload?.message || `요청에 실패했습니다. (${response.status})`;
            const error = new Error(message);
            error.status = response.status;
            error.retryAfterSeconds = Number(response.headers.get('Retry-After')) || 0;
            if (response.status === 401 && state.token && path !== '/api/auth/login' && path !== '/api/auth/logout') {
                clearSession();
                setAuthUser(null);
                [ui.subscriptionDialog, ui.accountDialog].forEach((dialog) => { if (dialog.open) dialog.close(); });
                if (!ui.authDialog.open) ui.authDialog.showModal();
                setAuthMode('login');
                ui.authMessage.textContent = '로그인 세션이 만료되었습니다. 다시 로그인해 주세요.';
            }
            throw error;
        }
        if (payload?.ok === false) {
            const error = new Error(payload.error || '요청을 처리하지 못했습니다.');
            error.status = 400;
            throw error;
        }
        return payload;
    } catch (error) {
        if (!error.status) setApiConnection(false);
        throw error;
    } finally {
        clearTimeout(timer);
    }
}

function setApiConnection(connected) {
    ui.apiStatus.dataset.state = connected ? 'connected' : 'error';
    ui.apiStatusText.textContent = connected ? 'API 연결됨' : 'API 연결 실패';
}
function clearSession() {
    state.token = '';
    sessionStorage.removeItem(TOKEN_KEY);
}

function setStatus(status) {
    ui.loading.classList.toggle('hide', status !== 'loading');
    ui.failed.classList.toggle('hide', status !== 'failed');
    ui.empty.classList.toggle('hide', status !== 'empty');
}

function clearArticleCards() { ui.cards.querySelectorAll('.card').forEach((node) => node.remove()); }
function safeDate(value) {
    if (!value) return '';
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? String(value) : new Intl.DateTimeFormat('ko-KR', { dateStyle: 'medium', timeZone: 'Asia/Seoul' }).format(date);
}
function makeElement(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
}

async function loadArticles() {
    clearTimeout(state.searchTimer);
    state.offset = Math.max(0, state.offset);
    state.pageSize = Math.min(PAGE_SIZE_LIMIT, Math.max(1, Number(ui.pageSize.value) || 20));
    clearArticleCards();
    ui.resultCount.textContent = '';
    ui.pagination.classList.add('hide');
    setStatus('loading');
    const params = new URLSearchParams({ limit: String(state.pageSize), offset: String(state.offset) });
    const query = ui.search.value.trim();
    if (query) params.set('q', query);
    if (ui.source.value) params.set('blog_id', ui.source.value);
    if (ui.company.value) params.set('company', ui.company.value);
    if (ui.from.value) params.set('from', ui.from.value);
    if (ui.to.value) params.set('to', ui.to.value);
    if (ui.sort.value) params.set('sort', ui.sort.value);
    try {
        const payload = await api(`/api/articles?${params}`);
        state.articles = Array.isArray(payload?.articles) ? payload.articles : [];
        state.total = Number(payload?.total ?? payload?.count ?? state.articles.length);
        renderArticles();
    } catch (error) {
        if (error.name === 'AbortError') return;
        console.error('게시글 조회 실패:', error);
        state.articles = [];
        setStatus('failed');
    }
}

function tagPattern(tag) {
    if (tag === 'Front End') return /front[\s-]?end|frontend|react|vue|angular|svelte|next\.?js|javascript|typescript|\bcss\b|\bhtml\b/i;
    if (tag === 'Back End') return /back[\s-]?end|backend|spring|django|flask|fastapi|node\.?js|\bjava\b|python|golang|\bsql\b|\bapi\b/i;
    return /(^|[^a-z])(ai|ml|llm|nlp)([^a-z]|$)|machine learning|deep learning|data science|인공지능|머신러닝/i;
}
function articleMatchesTag(article, tag) {
    const text = [article.title, article.summary, article.content, article.author, article.company, article.blog_name].filter(Boolean).join(' ');
    return tagPattern(tag).test(text);
}
function updateTagCounts() {
    ui.tags.forEach((button) => {
        const name = button.querySelector('.tagName').textContent.trim();
        const count = state.topicCounts === null
            ? '…'
            : state.topicCounts === false
                ? '—'
                : String(state.topicCounts[name] || 0).padStart(2, '0');
        button.querySelector('.tagCount').textContent = count;
    });
}
async function loadTopicCounts() {
    const counts = Object.fromEntries(ui.tags.map((button) => [button.querySelector('.tagName').textContent.trim(), 0]));
    let offset = 0;
    let total = 0;
    try {
        do {
            const params = new URLSearchParams({ limit: String(PAGE_SIZE_LIMIT), offset: String(offset) });
            const payload = await api(`/api/articles?${params}`);
            const articles = Array.isArray(payload?.articles) ? payload.articles : [];
            total = Number(payload?.total ?? (offset + articles.length));
            articles.forEach((article) => {
                Object.keys(counts).forEach((tag) => {
                    if (articleMatchesTag(article, tag)) counts[tag] += 1;
                });
            });
            if (!articles.length) break;
            offset += articles.length;
        } while (offset < total);
        state.topicCounts = counts;
    } catch (error) {
        console.warn('전체 주제별 글 수를 불러오지 못했습니다:', error);
        state.topicCounts = false;
    }
    updateTagCounts();
}
function renderArticles() {
    clearArticleCards();
    const visibleArticles = state.activeTag ? state.articles.filter((article) => articleMatchesTag(article, state.activeTag)) : state.articles;
    visibleArticles.forEach((article) => {
        const card = makeElement('button', 'card');
        card.type = 'button';
        card.addEventListener('click', () => openArticle(article));
        const titleBox = makeElement('div', 'cardTitleBox');
        const title = makeElement('h3', 'cardTitle', article.title || '제목 없음');
        title.title = article.title || '';
        titleBox.append(title);
        const textBox = makeElement('div', 'cardTextBox');
        textBox.append(makeElement('strong', 'cardCompany', [article.blog_name, article.company].filter(Boolean).join(' · ')));
        const meta = [article.author, safeDate(article.published_at || article.fetched_at)].filter(Boolean).join(' · ');
        if (meta) textBox.append(makeElement('span', 'cardMeta', meta));
        if (article.summary) textBox.append(makeElement('p', 'cardDesc', article.summary));
        card.append(titleBox, textBox);
        ui.cards.append(card);
    });

    updateTagCounts();
    ui.resultCount.textContent = state.activeTag
        ? `아티클 ${state.total.toLocaleString('ko-KR')}개 · ${state.activeTag} ${visibleArticles.length}개 표시`
        : `아티클 ${state.total.toLocaleString('ko-KR')}개 중 ${visibleArticles.length}개 표시`;
    setStatus(visibleArticles.length ? 'done' : 'empty');
    renderPagination();
}

function renderPagination() {
    const page = Math.floor(state.offset / state.pageSize) + 1;
    const pages = Math.max(1, Math.ceil(state.total / state.pageSize));
    ui.pagination.classList.toggle('hide', state.total <= state.pageSize);
    ui.pageLabel.textContent = `${page} / ${pages}`;
    ui.prev.disabled = state.offset <= 0;
    ui.next.disabled = state.offset + state.pageSize >= state.total;
}

function openArticle(article) {
    state.activeArticleId = article.id;
    ui.dialogTitle.textContent = article.title || '제목 없음';
    ui.dialogMeta.textContent = [article.blog_name, article.company, article.author, safeDate(article.published_at || article.fetched_at)].filter(Boolean).join(' · ');
    ui.dialogText.textContent = article.content || article.summary || '본문을 불러오고 있습니다.';
    ui.dialogLink.href = article.url || '#';
    ui.dialogLink.classList.toggle('hide', !article.url);
    ui.articleDialog.showModal();
    if (!article.content && article.id != null) {
        api(`/api/articles/${encodeURIComponent(article.id)}`).then((payload) => {
            const detail = payload?.article;
            if (detail && ui.articleDialog.open && state.activeArticleId === article.id) {
                ui.dialogText.textContent = detail.content || detail.summary || '본문이 제공되지 않습니다.';
                if (detail.url) ui.dialogLink.href = detail.url;
            }
        }).catch((error) => {
            if (state.activeArticleId === article.id) ui.dialogText.textContent = article.summary || '본문을 불러오지 못했습니다.';
            console.error('게시글 상세 조회 실패:', error);
        });
    }
}

async function loadBlogs() {
    try {
        const payload = await api('/api/blogs');
        state.blogs = Array.isArray(payload?.blogs) ? payload.blogs : [];
        fillBlogFilters();
        renderBlogList();
    } catch (error) { console.error('블로그 목록 조회 실패:', error); }
}
function fillBlogFilters() {
    const current = ui.source.value;
    const currentCompany = ui.company.value;
    ui.source.replaceChildren(new Option('전체 블로그', ''));
    state.blogs.forEach((blog) => ui.source.add(new Option(`${blog.name}${blog.company ? ` · ${blog.company}` : ''}`, String(blog.id))));
    if (state.blogs.some((blog) => String(blog.id) === current)) ui.source.value = current;
    const companies = [...new Set(state.blogs.map((blog) => String(blog.company || '').trim()).filter(Boolean))]
        .sort((a, b) => a.localeCompare(b, 'ko'));
    ui.company.replaceChildren(new Option('전체 회사', ''));
    companies.forEach((company) => ui.company.add(new Option(company, company)));
    if (companies.includes(currentCompany)) ui.company.value = currentCompany;
}
function renderBlogList() {
    ui.blogList.replaceChildren();
    state.blogs.forEach((blog) => {
        const link = makeElement('a', 'blogItem');
        link.href = `detail.html?blog_id=${encodeURIComponent(blog.id)}`;
        link.append(makeElement('strong', '', blog.name || '이름 없는 블로그'), makeElement('span', '', `${blog.company || ''}${blog.article_count != null ? ` · ${blog.article_count}개 글` : ''}`));
        ui.blogList.append(link);
    });
}

function setAuthUser(user) {
    state.user = user || null;
    ui.userLabel.textContent = state.user?.display_name || state.user?.email || '';
    ui.authOpen.classList.toggle('hide', Boolean(state.user));
    ui.accountOpen.classList.toggle('hide', !state.user);
    ui.logout.classList.toggle('hide', !state.user);
    if (ui.subscriptionDialog.open) updateSubscriptionAccess();
}
async function restoreSession() {
    if (!state.token) return;
    try {
        const payload = await api('/api/auth/me');
        setAuthUser(payload?.user ?? payload);
    } catch (error) {
        state.token = '';
        sessionStorage.removeItem(TOKEN_KEY);
        setAuthUser(null);
        console.warn('저장된 로그인을 복원하지 못했습니다:', error);
    }
}
let authMode = 'login';
function setAuthMode(mode) {
    authMode = mode;
    ui.authTitle.textContent = mode === 'login' ? '로그인' : '회원가입';
    ui.authSubmit.textContent = mode === 'login' ? '로그인' : '계정 만들기';
    ui.displayNameField.classList.toggle('hide', mode !== 'register');
    $('authRecoveryActions').classList.toggle('hide', mode !== 'login');
    ui.displayName.required = mode === 'register';
    ui.authPassword.autocomplete = mode === 'login' ? 'current-password' : 'new-password';
    document.querySelectorAll('.authTab').forEach((tab) => tab.classList.toggle('active', tab.dataset.mode === mode));
    ui.authMessage.textContent = '';
    ui.authRecoveryMessage.textContent = '';
}
async function submitAuth(event) {
    event.preventDefault();
    ui.authMessage.textContent = '';
    ui.authSubmit.disabled = true;
    const body = { email: ui.authEmail.value.trim(), password: ui.authPassword.value };
    if (authMode === 'register') body.display_name = ui.displayName.value.trim();
    try {
        if (authMode === 'register') {
            const payload = await api('/api/auth/register', { method: 'POST', body: JSON.stringify(body) });
            ui.authForm.reset();
            setAuthMode('login');
            ui.authEmail.value = body.email;
            ui.authMessage.textContent = payload?.verification_sent
                ? '가입을 완료했습니다. 이메일 인증 링크를 확인한 뒤 로그인하세요.'
                : '가입을 완료했습니다. 인증 메일을 받지 못했다면 아래에서 다시 요청하세요.';
            return;
        }
        const payload = await api('/api/auth/login', { method: 'POST', body: JSON.stringify({ email: body.email, password: body.password }) });
        if (!payload?.token) throw new Error('로그인 응답에 토큰이 없습니다.');
        state.token = payload.token;
        sessionStorage.setItem(TOKEN_KEY, state.token);
        setAuthUser(payload.user);
        ui.authDialog.close();
        ui.authForm.reset();
        if (ui.subscriptionDialog.open) await loadSubscriptions();
    } catch (error) {
        ui.authMessage.textContent = error.status === 403
            ? '이메일 인증이 필요합니다. 인증 메일을 확인하거나 다시 요청하세요.'
            : error.message;
        if (error.status === 429 && error.retryAfterSeconds > 0) throttleLogin(error.retryAfterSeconds);
    } finally {
        if (!state.authThrottleTimer) ui.authSubmit.disabled = false;
    }
}
function throttleLogin(seconds) {
    clearInterval(state.authThrottleTimer);
    let remaining = seconds;
    ui.authSubmit.disabled = true;
    ui.authMessage.textContent = `${remaining}초 후 다시 로그인할 수 있습니다.`;
    state.authThrottleTimer = setInterval(() => {
        remaining -= 1;
        if (remaining <= 0) {
            clearInterval(state.authThrottleTimer);
            state.authThrottleTimer = null;
            ui.authSubmit.disabled = false;
            ui.authMessage.textContent = '다시 로그인할 수 있습니다.';
        } else ui.authMessage.textContent = `${remaining}초 후 다시 로그인할 수 있습니다.`;
    }, 1000);
}
async function requestVerificationEmail() {
    ui.authRecoveryMessage.textContent = '';
    if (!ui.authEmail.value.trim() || !ui.authEmail.checkValidity()) {
        ui.authEmail.reportValidity();
        return;
    }
    try {
        const payload = await api('/api/auth/email/verification/request', {
            method: 'POST', body: JSON.stringify({ email: ui.authEmail.value.trim() })
        });
        ui.authRecoveryMessage.textContent = payload?.message || '인증 메일을 요청했습니다.';
    } catch (error) { ui.authRecoveryMessage.textContent = error.message; }
}
async function requestPasswordReset() {
    ui.authRecoveryMessage.textContent = '';
    if (!ui.authEmail.value.trim() || !ui.authEmail.checkValidity()) {
        ui.authEmail.reportValidity();
        return;
    }
    try {
        const payload = await api('/api/auth/password/reset/request', {
            method: 'POST', body: JSON.stringify({ email: ui.authEmail.value.trim() })
        });
        ui.authRecoveryMessage.textContent = payload?.message || '비밀번호 재설정 메일을 요청했습니다.';
    } catch (error) { ui.authRecoveryMessage.textContent = error.message; }
}
function openAccountSettings() {
    ui.profileName.value = state.user?.display_name || '';
    ui.accountIdentity.textContent = `${state.user?.email || ''} · ${state.user?.email_verified ? '이메일 인증됨' : '이메일 미인증'}`;
    ui.profileMessage.textContent = '';
    ui.passwordMessage.textContent = '';
    ui.deleteAccountMessage.textContent = '';
    ui.passwordForm.reset();
    ui.deleteAccountForm.reset();
    ui.accountDialog.showModal();
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
        const payload = await api('/api/auth/me', {
            method: 'PATCH', body: JSON.stringify({ display_name: displayName })
        });
        setAuthUser(payload?.user ?? payload);
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
        await api('/api/auth/password', {
            method: 'PUT', body: JSON.stringify({ current_password: ui.currentPassword.value, new_password: ui.newPassword.value })
        });
        clearSession();
        setAuthUser(null);
        ui.accountDialog.close();
        setAuthMode('login');
        ui.authMessage.textContent = '비밀번호가 변경되었습니다. 새 비밀번호로 다시 로그인하세요.';
        ui.authDialog.showModal();
    } catch (error) { ui.passwordMessage.textContent = error.message; }
}
async function deleteAccount(event) {
    event.preventDefault();
    ui.deleteAccountMessage.textContent = '';
    if (!window.confirm('계정과 구독 정보를 삭제할까요? 이 작업은 되돌릴 수 없습니다.')) return;
    try {
        await api('/api/auth/me', {
            method: 'DELETE', body: JSON.stringify({ password: ui.deleteAccountPassword.value })
        });
        clearSession();
        setAuthUser(null);
        ui.accountDialog.close();
        ui.authOpen.focus();
    } catch (error) { ui.deleteAccountMessage.textContent = error.message; }
}
async function logout() {
    try { if (state.token) await api('/api/auth/logout', { method: 'POST' }); }
    catch (error) { console.warn('로그아웃 요청 실패:', error); }
    clearSession();
    setAuthUser(null);
    ui.subscriptionList.replaceChildren();
}

function openSubscriptions() {
    ui.subscriptionMessage.textContent = '';
    updateSubscriptionAccess();
    ui.subscriptionDialog.showModal();
    if (state.user) loadSubscriptions();
}
function updateSubscriptionAccess() {
    const signedIn = Boolean(state.user && state.token);
    ui.subscriptionHint.textContent = signedIn ? '등록된 키워드 알림을 관리합니다.' : '키워드 구독을 관리하려면 먼저 로그인하세요.';
    ui.subscriptionForm.classList.toggle('hide', !signedIn);
    if (!signedIn) {
        ui.subscriptionList.replaceChildren();
        const login = makeElement('button', 'inlineAction', '로그인');
        login.type = 'button';
        login.addEventListener('click', () => { ui.subscriptionDialog.close(); ui.authDialog.showModal(); setAuthMode('login'); });
        ui.subscriptionList.append(login);
    }
}
async function loadSubscriptions() {
    if (!state.token) return;
    ui.subscriptionMessage.textContent = '구독 목록을 불러오는 중…';
    try {
        const payload = await api('/api/subscriptions');
        renderSubscriptions(Array.isArray(payload?.subscriptions) ? payload.subscriptions : []);
        ui.subscriptionMessage.textContent = '';
    } catch (error) {
        if (error.status === 401) { state.token = ''; sessionStorage.removeItem(TOKEN_KEY); setAuthUser(null); }
        ui.subscriptionMessage.textContent = error.message;
    }
}
function renderSubscriptions(subscriptions) {
    ui.subscriptionList.replaceChildren();
    if (!subscriptions.length) {
        ui.subscriptionList.append(makeElement('p', 'modalHint', '아직 등록된 키워드가 없습니다.'));
        return;
    }
    subscriptions.forEach((subscription) => {
        const row = makeElement('div', 'subscriptionItem');
        const isActive = subscription.active === 1 || subscription.active === true;
        row.append(makeElement('strong', '', subscription.keyword), makeElement('small', '', `${isActive ? '구독 중' : '일시정지'} · ${subscription.discord_webhook_url ? '디스코드 알림 연결됨' : '웹훅 미설정'}`));
        const actions = makeElement('div', 'subscriptionActions');
        const toggle = makeElement('button', '', isActive ? '일시정지' : '다시 켜기');
        const edit = makeElement('button', '', subscription.discord_webhook_url ? '웹훅 변경' : '웹훅 연결');
        const remove = makeElement('button', '', '삭제');
        toggle.type = edit.type = remove.type = 'button';
        toggle.addEventListener('click', async () => {
            try {
                await api(`/api/subscriptions/${encodeURIComponent(subscription.id)}`, {
                    method: 'PATCH', body: JSON.stringify({ active: !isActive })
                });
                await loadSubscriptions();
                ui.subscriptionMessage.textContent = isActive ? '키워드 알림을 일시정지했습니다.' : '키워드 알림을 다시 켰습니다.';
            } catch (error) { ui.subscriptionMessage.textContent = error.message; }
        });
        edit.addEventListener('click', async () => {
            const url = window.prompt('디스코드 웹훅 URL을 입력하세요. 비우면 연결을 해제합니다.', subscription.discord_webhook_url || '');
            if (url === null) return;
            try {
                await api(`/api/subscriptions/${encodeURIComponent(subscription.id)}`, { method: 'PATCH', body: JSON.stringify({ discord_webhook_url: url.trim() || null }) });
                await loadSubscriptions();
            } catch (error) { ui.subscriptionMessage.textContent = error.message; }
        });
        remove.addEventListener('click', async () => {
            if (!window.confirm(`“${subscription.keyword}” 구독을 삭제할까요?`)) return;
            try {
                await api(`/api/subscriptions/${encodeURIComponent(subscription.id)}`, { method: 'DELETE' });
                await loadSubscriptions();
            } catch (error) { ui.subscriptionMessage.textContent = error.message; }
        });
        actions.append(toggle, edit, remove);
        row.append(actions);
        ui.subscriptionList.append(row);
    });
}
async function createSubscription(event) {
    event.preventDefault();
    ui.subscriptionMessage.textContent = '';
    try {
        await api('/api/subscriptions', { method: 'POST', body: JSON.stringify({ keyword: ui.keyword.value.trim(), discord_webhook_url: ui.webhook.value.trim() || undefined }) });
        ui.subscriptionForm.reset();
        await loadSubscriptions();
        ui.subscriptionMessage.textContent = '키워드 구독을 추가했습니다.';
    } catch (error) { ui.subscriptionMessage.textContent = error.message; }
}

function bindEvents() {
    ui.search.addEventListener('input', () => { state.offset = 0; clearTimeout(state.searchTimer); state.searchTimer = setTimeout(loadArticles, SEARCH_DELAY_MS); });
    ui.search.addEventListener('keydown', (event) => { if (event.key === 'Enter' && !event.isComposing) { clearTimeout(state.searchTimer); state.offset = 0; loadArticles(); } });
    [ui.source, ui.company, ui.from, ui.to, ui.pageSize, ui.sort].forEach((control) => control.addEventListener('change', () => { state.offset = 0; loadArticles(); if (control === ui.source) renderBlogList(); }));
    ui.retry.addEventListener('click', loadArticles);
    ui.prev.addEventListener('click', () => { state.offset = Math.max(0, state.offset - state.pageSize); loadArticles(); });
    ui.next.addEventListener('click', () => { if (state.offset + state.pageSize < state.total) { state.offset += state.pageSize; loadArticles(); } });
    ui.tags.forEach((button) => button.addEventListener('click', () => {
        const name = button.querySelector('.tagName').textContent.trim();
        state.activeTag = state.activeTag === name ? '' : name;
        ui.tags.forEach((item) => item.setAttribute('aria-pressed', String(item.querySelector('.tagName').textContent.trim() === state.activeTag)));
        renderArticles();
    }));
    ui.authOpen.addEventListener('click', () => { setAuthMode('login'); ui.authDialog.showModal(); });
    ui.accountOpen.addEventListener('click', openAccountSettings);
    ui.logout.addEventListener('click', logout);
    ui.authForm.addEventListener('submit', submitAuth);
    document.querySelectorAll('.authTab').forEach((tab) => tab.addEventListener('click', () => setAuthMode(tab.dataset.mode)));
    $('verificationResend').addEventListener('click', requestVerificationEmail);
    $('passwordResetRequest').addEventListener('click', requestPasswordReset);
    ui.profileForm.addEventListener('submit', updateProfile);
    ui.passwordForm.addEventListener('submit', changePassword);
    ui.deleteAccountForm.addEventListener('submit', deleteAccount);
    ui.subscriptionOpen.addEventListener('click', openSubscriptions);
    ui.subscriptionForm.addEventListener('submit', createSubscription);
    document.querySelectorAll('[data-close]').forEach((button) => button.addEventListener('click', () => $(button.dataset.close).close()));
    $('dialogClose').addEventListener('click', () => ui.articleDialog.close());
    [ui.articleDialog, ui.authDialog, ui.accountDialog, ui.subscriptionDialog].forEach((dialog) => dialog.addEventListener('click', (event) => { if (event.target === dialog) dialog.close(); }));
}

bindEvents();
loadArticles();
loadBlogs();
updateTagCounts();
loadTopicCounts();
restoreSession();
