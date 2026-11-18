'use strict';

const SEARCH_DELAY_MS = 300;
const PAGE_SIZE_LIMIT = 100;

const $ = (id) => document.getElementById(id);
const ui = {
    search: $('searchInput'), source: $('sourceSelect'), from: $('fromDate'), to: $('toDate'),
    company: $('companySelect'), sort: $('sortSelect'), pageSize: $('pageSize'), cards: $('cards'), resultCount: $('resultCount'), loading: $('searchAction'),
    failed: $('searchFailed'), empty: $('searchEmpty'), retry: $('retryButton'), pagination: $('pagination'),
    prev: $('prevPage'), next: $('nextPage'), pageLabel: $('pageLabel'), tags: [...document.querySelectorAll('.tag')],
    blogList: $('blogList'), blogListStatus: $('blogListStatus'), retryBlogs: $('retryBlogsButton'), apiStatus: $('apiStatus'), apiStatusText: $('apiStatusText'), articleDialog: $('articleDialog'), dialogTitle: $('dialogTitle'),
    dialogMeta: $('dialogMeta'), dialogText: $('dialogText'), dialogLink: $('dialogLink'),
    accountLink: $('accountLink'), logout: $('logoutButton'), userLabel: $('userLabel')
};

const state = {
    token: window.feedApi.getToken(), user: null, blogs: [], articles: [], total: 0,
    offset: 0, pageSize: 20, searchTimer: null, activeTag: '', topicCounts: null, activeArticleId: null, taggedArticles: null, taggedQueryKey: ''
};

async function api(path, options = {}) {
    try {
        const payload = await window.feedApi.request(path, options);
        setApiConnection(true);
        return payload;
    } catch (error) {
        setApiConnection(Boolean(error.status));
        if (error.status === 401 && state.token && path !== '/api/auth/login' && path !== '/api/auth/logout') {
            clearSession();
            setAuthUser(null);
            window.location.href = 'account.html?expired=1';
        }
        throw error;
    }
}

function setApiConnection(connected) {
    ui.apiStatus.dataset.state = connected ? 'connected' : 'error';
    ui.apiStatusText.textContent = connected ? 'API 연결됨' : 'API 연결 실패';
}
function clearSession() {
    state.token = '';
    window.feedApi.clearToken();
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
    const filters = new URLSearchParams();
    const query = ui.search.value.trim();
    if (query) filters.set('q', query);
    if (ui.source.value) filters.set('blog_id', ui.source.value);
    if (ui.company.value) filters.set('company', ui.company.value);
    if (ui.from.value) filters.set('from', ui.from.value);
    if (ui.to.value) filters.set('to', ui.to.value);
    if (ui.sort.value) filters.set('sort', ui.sort.value);
    try {
        if (state.activeTag) {
            const queryKey = `${filters.toString()}|${state.activeTag}`;
            if (state.taggedQueryKey !== queryKey || !Array.isArray(state.taggedArticles)) {
                const all = [];
                let offset = 0;
                let total = 0;
                do {
                    const params = new URLSearchParams(filters);
                    params.set('limit', String(PAGE_SIZE_LIMIT));
                    params.set('offset', String(offset));
                    const payload = await api(`/api/articles?${params}`);
                    const batch = Array.isArray(payload?.articles) ? payload.articles : [];
                    total = Number(payload?.total ?? offset + batch.length);
                    all.push(...batch);
                    offset += batch.length;
                    if (!batch.length) break;
                } while (offset < total);
                state.taggedArticles = all.filter((article) => articleMatchesTag(article, state.activeTag));
                state.taggedQueryKey = queryKey;
            }
            state.total = state.taggedArticles.length;
            state.articles = state.taggedArticles.slice(state.offset, state.offset + state.pageSize);
        } else {
            const params = new URLSearchParams(filters);
            params.set('limit', String(state.pageSize));
            params.set('offset', String(state.offset));
            const payload = await api(`/api/articles?${params}`);
            state.articles = Array.isArray(payload?.articles) ? payload.articles : [];
            state.total = Number(payload?.total ?? payload?.count ?? state.articles.length);
        }
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
    const visibleArticles = state.articles;
    visibleArticles.forEach((article) => {
        const card = makeElement('article', 'card');
        const openButton = makeElement('button', 'cardOpen');
        openButton.type = 'button';
        openButton.setAttribute('aria-label', `게시글 열기: ${article.title || '제목 없음'}`);
        openButton.addEventListener('click', () => openArticle(article));
        const titleBox = makeElement('span', 'cardTitleBox');
        const title = makeElement('span', 'cardTitle', article.title || '제목 없음');
        title.title = article.title || '';
        titleBox.append(title);
        const textBox = makeElement('span', 'cardTextBox');
        textBox.append(makeElement('strong', 'cardCompany', [article.blog_name, article.company].filter(Boolean).join(' · ')));
        const meta = [article.author, safeDate(article.published_at || article.fetched_at)].filter(Boolean).join(' · ');
        if (meta) textBox.append(makeElement('span', 'cardMeta', meta));
        if (article.summary) textBox.append(makeElement('span', 'cardDesc', article.summary));
        openButton.append(titleBox, textBox);
        card.append(openButton);
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
    ui.dialogText.textContent = article.content || article.summary || '본문을 확인할 수 없습니다. 원문에서 확인해 주세요.';
    ui.dialogLink.href = article.url || '#';
    ui.dialogLink.classList.toggle('hide', !article.url);
    ui.articleDialog.showModal();
    if (!article.content && article.id != null) {
        api(`/api/articles/${encodeURIComponent(article.id)}`).then((payload) => {
            const detail = payload?.article;
            if (detail && ui.articleDialog.open && state.activeArticleId === article.id) {
                ui.dialogText.textContent = detail.content || detail.summary || '본문을 확인할 수 없습니다. 원문에서 확인해 주세요.';
                if (detail.url) ui.dialogLink.href = detail.url;
            }
        }).catch((error) => {
            if (state.activeArticleId === article.id) ui.dialogText.textContent = article.summary || '본문을 불러오지 못했습니다. 원문에서 확인해 주세요.';
            console.error('게시글 상세 조회 실패:', error);
        });
    }
}

async function loadBlogs() {
    ui.blogListStatus.textContent = '블로그 목록을 불러오는 중입니다.';
    ui.blogListStatus.classList.remove('hide', 'isError');
    ui.retryBlogs.classList.add('hide');
    try {
        const payload = await api('/api/blogs');
        state.blogs = Array.isArray(payload?.blogs) ? payload.blogs : [];
        fillBlogFilters();
        renderBlogList();
        ui.blogListStatus.classList.toggle('hide', state.blogs.length > 0);
        if (!state.blogs.length) ui.blogListStatus.textContent = '등록된 블로그가 없습니다.';
    } catch (error) {
        console.error('블로그 목록 조회 실패:', error);
        ui.blogListStatus.textContent = '블로그 목록을 불러오지 못했습니다.';
        ui.blogListStatus.classList.add('isError');
        ui.retryBlogs.classList.remove('hide');
    }
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
    ui.accountLink.textContent = state.user ? '내 계정' : '로그인';
    ui.logout.classList.toggle('hide', !state.user);
}
async function restoreSession() {
    if (!state.token) return;
    try {
        const payload = await api('/api/auth/me');
        setAuthUser(payload?.user ?? payload);
    } catch (error) {
        state.token = '';
        window.feedApi.clearToken();
        setAuthUser(null);
        console.warn('저장된 로그인을 복원하지 못했습니다:', error);
    }
}
async function logout() {
    try { if (state.token) await api('/api/auth/logout', { method: 'POST' }); }
    catch (error) { console.warn('로그아웃 요청 실패:', error); }
    clearSession();
    setAuthUser(null);
}

function bindEvents() {
    ui.search.addEventListener('input', () => { state.offset = 0; clearTimeout(state.searchTimer); state.searchTimer = setTimeout(loadArticles, SEARCH_DELAY_MS); });
    ui.search.addEventListener('keydown', (event) => { if (event.key === 'Enter' && !event.isComposing) { clearTimeout(state.searchTimer); state.offset = 0; loadArticles(); } });
    [ui.source, ui.company, ui.from, ui.to, ui.pageSize, ui.sort].forEach((control) => control.addEventListener('change', () => { state.offset = 0; loadArticles(); if (control === ui.source) renderBlogList(); }));
    ui.retry.addEventListener('click', loadArticles);
    ui.retryBlogs.addEventListener('click', loadBlogs);
    ui.prev.addEventListener('click', () => { state.offset = Math.max(0, state.offset - state.pageSize); loadArticles(); });
    ui.next.addEventListener('click', () => { if (state.offset + state.pageSize < state.total) { state.offset += state.pageSize; loadArticles(); } });
    ui.tags.forEach((button) => button.addEventListener('click', () => {
        const name = button.querySelector('.tagName').textContent.trim();
        state.activeTag = state.activeTag === name ? '' : name;
        state.offset = 0;
        state.taggedArticles = null;
        state.taggedQueryKey = '';
        ui.tags.forEach((item) => item.setAttribute('aria-pressed', String(item.querySelector('.tagName').textContent.trim() === state.activeTag)));
        loadArticles();
    }));
    ui.logout.addEventListener('click', logout);
    $('dialogClose').addEventListener('click', () => ui.articleDialog.close());
    ui.articleDialog.addEventListener('click', (event) => { if (event.target === ui.articleDialog) ui.articleDialog.close(); });
}

bindEvents();
loadArticles();
loadBlogs();
updateTagCounts();
loadTopicCounts();
restoreSession();
