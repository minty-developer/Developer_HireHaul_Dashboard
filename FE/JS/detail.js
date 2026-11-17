'use strict';

const API_BASE_URL = window.FEED_API_BASE_URL || 'http://127.0.0.1:5000';
const PAGE_SIZE = 20;
const REQUEST_TIMEOUT_MS = 30000;
const $ = (id) => document.getElementById(id);

const ui = {
    breadcrumbBlog: $('breadcrumbBlog'), blogLoading: $('blogLoading'), blogError: $('blogError'), blogErrorText: $('blogErrorText'),
    retryButton: $('retryButton'), blogProfile: $('blogProfile'), blogCompany: $('blogCompany'), blogName: $('blogName'),
    blogDescription: $('blogDescription'), articleCount: $('articleCount'), siteLink: $('siteLink'), feedLink: $('feedLink'),
    articleSection: $('articleSection'), articleLoading: $('articleLoading'), articleError: $('articleError'),
    articleErrorText: $('articleErrorText'), retryArticlesButton: $('retryArticlesButton'), articleEmpty: $('articleEmpty'),
    articleTotal: $('articleTotal'), articleList: $('articleList'), pagination: $('pagination'), prevPage: $('prevPage'),
    nextPage: $('nextPage'), pageLabel: $('pageLabel')
};
const blogId = new URLSearchParams(window.location.search).get('blog_id');
const state = { offset: 0, total: 0, loadingBlog: false, loadingArticles: false };

function apiUrl(path) { return `${API_BASE_URL}${path}`; }

async function request(path) {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
    try {
        const response = await fetch(apiUrl(path), { headers: { Accept: 'application/json' }, signal: controller.signal });
        const text = await response.text();
        let payload = null;
        if (text) {
            try { payload = JSON.parse(text); }
            catch { payload = { message: text }; }
        }
        if (!response.ok || payload?.ok === false) {
            const error = new Error(payload?.error || payload?.message || `요청에 실패했습니다. (${response.status})`);
            error.status = response.status;
            throw error;
        }
        return payload;
    } finally { clearTimeout(timeout); }
}

function showBlogError(message) {
    ui.blogLoading.classList.add('hide');
    ui.blogProfile.classList.add('hide');
    ui.articleSection.classList.add('hide');
    ui.blogErrorText.textContent = message;
    ui.blogError.classList.remove('hide');
}

function formatDate(value) {
    if (!value) return '';
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? String(value) : new Intl.DateTimeFormat('ko-KR', { dateStyle: 'medium', timeZone: 'Asia/Seoul' }).format(date);
}

function setExternalLink(element, value) {
    if (!value) {
        element.classList.add('hide');
        element.removeAttribute('href');
        return;
    }
    try {
        const parsed = new URL(value, window.location.href);
        if (!['http:', 'https:'].includes(parsed.protocol)) throw new Error('지원하지 않는 링크입니다.');
        element.href = parsed.href;
        element.classList.remove('hide');
    } catch {
        element.classList.add('hide');
        element.removeAttribute('href');
    }
}

async function loadBlog() {
    if (!blogId) {
        showBlogError('블로그를 찾을 수 없습니다. 블로그 목록에서 다시 선택해 주세요.');
        return;
    }
    if (state.loadingBlog) return;
    state.loadingBlog = true;
    ui.blogError.classList.add('hide');
    ui.blogLoading.classList.remove('hide');
    ui.blogProfile.classList.add('hide');
    ui.articleSection.classList.add('hide');
    try {
        const payload = await request(`/api/blogs/${encodeURIComponent(blogId)}`);
        const blog = payload?.blog;
        if (!blog) throw new Error('블로그 정보를 찾을 수 없습니다.');
        const name = blog.name || '이름 없는 블로그';
        ui.breadcrumbBlog.textContent = name;
        ui.blogName.textContent = name;
        ui.blogCompany.textContent = blog.company || '';
        ui.blogCompany.classList.toggle('hide', !blog.company);
        ui.blogDescription.textContent = blog.description || '등록된 블로그 소개가 없습니다.';
        ui.articleCount.textContent = Number(blog.article_count || 0).toLocaleString('ko-KR');
        setExternalLink(ui.siteLink, blog.site_url);
        setExternalLink(ui.feedLink, blog.feed_url);
        document.title = `${name} — FEED`;
        ui.blogLoading.classList.add('hide');
        ui.blogProfile.classList.remove('hide');
        ui.articleSection.classList.remove('hide');
        await loadArticles();
    } catch (error) {
        console.error('블로그 상세 조회 실패:', error);
        showBlogError(error.name === 'AbortError' ? '블로그 정보를 불러오는 시간이 초과되었습니다.' : error.message);
    } finally { state.loadingBlog = false; }
}

function makeArticle(article) {
    const item = document.createElement('article');
    item.className = 'articleItem';
    const titleText = article.title || '제목 없음';
    if (article.url) {
        const title = document.createElement('a');
        title.className = 'articleTitle';
        title.href = article.url;
        title.target = '_blank';
        title.rel = 'noopener noreferrer';
        title.textContent = titleText;
        item.append(title);
    } else {
        const title = document.createElement('h3');
        title.className = 'articleTitle';
        title.textContent = titleText;
        item.append(title);
    }
    if (article.summary) {
        const summary = document.createElement('p');
        summary.className = 'articleSummary';
        summary.textContent = article.summary;
        item.append(summary);
    }
    const metadata = [article.author, formatDate(article.published_at || article.fetched_at)].filter(Boolean).join(' · ');
    if (metadata) {
        const meta = document.createElement('p');
        meta.className = 'articleMeta';
        meta.textContent = metadata;
        item.append(meta);
    }
    const arrow = document.createElement('span');
    arrow.className = 'articleArrow';
    arrow.setAttribute('aria-hidden', 'true');
    arrow.textContent = '↗';
    item.append(arrow);
    return item;
}

function renderPagination() {
    const page = Math.floor(state.offset / PAGE_SIZE) + 1;
    const pageCount = Math.max(1, Math.ceil(state.total / PAGE_SIZE));
    ui.pagination.classList.toggle('hide', state.total <= PAGE_SIZE);
    ui.pageLabel.textContent = `${page} / ${pageCount}`;
    ui.prevPage.disabled = state.offset === 0;
    ui.nextPage.disabled = state.offset + PAGE_SIZE >= state.total;
}

async function loadArticles() {
    if (!blogId || state.loadingArticles) return;
    state.loadingArticles = true;
    ui.articleLoading.classList.remove('hide');
    ui.articleError.classList.add('hide');
    ui.articleEmpty.classList.add('hide');
    ui.pagination.classList.add('hide');
    ui.articleList.replaceChildren();
    try {
        const params = new URLSearchParams({ blog_id: blogId, limit: String(PAGE_SIZE), offset: String(state.offset) });
        const payload = await request(`/api/articles?${params}`);
        const articles = Array.isArray(payload?.articles) ? payload.articles : [];
        state.total = Number(payload?.total ?? payload?.count ?? articles.length);
        ui.articleTotal.textContent = `${state.total.toLocaleString('ko-KR')}개`;
        ui.articleList.replaceChildren(...articles.map(makeArticle));
        ui.articleEmpty.classList.toggle('hide', articles.length > 0);
        renderPagination();
    } catch (error) {
        console.error('블로그 게시글 조회 실패:', error);
        ui.articleErrorText.textContent = error.name === 'AbortError' ? '게시글을 불러오는 시간이 초과되었습니다.' : error.message;
        ui.articleError.classList.remove('hide');
    } finally {
        ui.articleLoading.classList.add('hide');
        state.loadingArticles = false;
    }
}

ui.retryButton.addEventListener('click', loadBlog);
ui.retryArticlesButton.addEventListener('click', loadArticles);
ui.prevPage.addEventListener('click', () => {
    if (state.offset <= 0) return;
    state.offset = Math.max(0, state.offset - PAGE_SIZE);
    loadArticles();
});
ui.nextPage.addEventListener('click', () => {
    if (state.offset + PAGE_SIZE >= state.total) return;
    state.offset += PAGE_SIZE;
    loadArticles();
});

loadBlog();
