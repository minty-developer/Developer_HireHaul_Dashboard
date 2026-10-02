'use strict';

// ===== 설정 =====
const SERVER_URL = 'https://developer-hirehaul-dashboard.onrender.com';
const JOBS_LIMIT = 100;         // 한 번에 가져올 공고 수
const SEARCH_DELAY = 300;       // 입력 후 검색까지 대기(ms)
const HEALTH_INTERVAL = 15000;  // 서버 깨우기용 health 체크 주기(ms)
const SLOW_HINT_DELAY = 4000;   // 이 시간 이상 걸리면 "서버 깨우는 중" 안내(ms)
const REQUEST_TIMEOUT = 60000;  // 요청 제한 시간(ms) - Render Free 콜드 스타트 고려
const LOADING_TEXT = '검색 중입니다.';
const SLOW_TEXT = '서버를 깨우는 중입니다. 최대 1분 정도 걸릴 수 있습니다.';

// ===== 요소 =====
const $ = (id) => document.getElementById(id);
const searchInput = $('searchInput');
const searchAction = $('searchAction');
const searchFailed = $('searchFailed');
const searchEmpty = $('searchEmpty');
const resultCount = $('resultCount');
const retryButton = $('retryButton');
const cards = $('cards');
const locationSelect = $('locationSelect');
const sourceSelect = $('sourceSelect');
const statsBox = $('statsBox');
const jobDialog = $('jobDialog');
const dialogTitle = $('dialogTitle');
const dialogMeta = $('dialogMeta');
const dialogText = $('dialogText');
const dialogLink = $('dialogLink');
const dialogClose = $('dialogClose');
const tagButtons = document.querySelectorAll('.tag');

// 태그별 키워드 (제목/회사/설명/태그 텍스트에 적용)
const TAG_PATTERNS = {
    'Front End': /front[\s-]?end|프론트|react|vue|angular|svelte|next\.?js|javascript|typescript|\bcss\b|\bhtml\b/i,
    'Back End': /back[\s-]?end|백엔드|서버|spring|django|flask|fastapi|node\.?js|\bjava\b|python|golang|\bsql\b|\bapi\b/i,
    'AI': /(^|[^a-z])(ai|ml|llm|nlp)([^a-z]|$)|인공지능|머신러닝|딥러닝|machine learning|deep learning|data scien|데이터\s?사이언/i,
};

// ===== 상태 =====
let allJobs = [];
let hasLoaded = false;
const activeTags = new Set();
const knownLocations = new Set(); // 드롭다운 옵션: 받은 공고에서 누적
const knownSources = new Set();
let searchTimer = null;
let slowTimer = null;
let requestController = null;

// ===== 유틸 =====
function checkElements() {
    const items = { searchInput, searchAction, searchFailed, searchEmpty, resultCount, retryButton, cards,
        locationSelect, sourceSelect, statsBox, jobDialog, dialogTitle, dialogMeta, dialogText, dialogLink, dialogClose };
    Object.entries(items).forEach(([name, element]) => {
        if (!element) console.warn(`${name} 요소가 null 또는 undefined입니다.`);
    });
    if (!tagButtons.length) console.warn('태그 버튼을 찾을 수 없습니다.');
}

function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text) node.textContent = text;
    return node;
}

/** 서버 응답의 공고 1건을 화면용 형태로 변환 (필드명이 달라도 대응) */
function normalizeJob(job) {
    const url = job.url ?? job.link ?? job.apply_url ?? '';
    const tags = Array.isArray(job.tags) ? job.tags.join(' ') : (job.tags || '');
    const description = job.description ?? job.summary ?? '';
    return {
        name: job.title || job.position || '(제목 없음)',
        company: job.company || job.company_name || '',
        location: job.location || '',
        source: job.source || '',
        description,
        url: /^https?:\/\//i.test(url) ? url : '',
        text: [job.title, job.company, description, tags].filter(Boolean).join(' '),
    };
}

// ===== 상태 표시 =====
function setStatus(state) { // 'loading' | 'failed' | 'empty' | 'done'
    searchAction.classList.toggle('hide', state !== 'loading');
    searchFailed.classList.toggle('hide', state !== 'failed');
    searchEmpty.classList.toggle('hide', state !== 'empty');
}

function clearCards() {
    cards.querySelectorAll('.card').forEach((card) => card.remove()); // 상태 요소는 유지
}

// ===== 서버 통신 =====
async function fetchJobs() {
    if (requestController) requestController.abort(); // 이전 요청 취소
    requestController = new AbortController();
    const signal = AbortSignal.any([requestController.signal, AbortSignal.timeout(REQUEST_TIMEOUT)]);

    const params = new URLSearchParams({ limit: JOBS_LIMIT });
    const query = searchInput.value.trim();
    if (query) params.set('q', query);
    if (locationSelect.value) params.set('location', locationSelect.value);
    if (sourceSelect.value) params.set('source', sourceSelect.value);

    const response = await fetch(`${SERVER_URL}/api/jobs?${params}`, { signal });
    if (!response.ok) throw new Error(`fetch 실패. status: ${response.status}`);
    const data = await response.json();
    return (Array.isArray(data) ? data : data.jobs ?? []).map(normalizeJob);
}

async function search() {
    hasLoaded = false;
    clearCards();
    resultCount.textContent = '';
    searchAction.textContent = LOADING_TEXT;
    setStatus('loading');
    clearTimeout(slowTimer);
    slowTimer = setTimeout(() => { searchAction.textContent = SLOW_TEXT; }, SLOW_HINT_DELAY);
    try {
        allJobs = await fetchJobs();
        hasLoaded = true;
        collectOptions();
        clearTimeout(slowTimer);
        renderCards();
    } catch (err) {
        if (err.name === 'AbortError') return; // 새 검색이 시작됨
        clearTimeout(slowTimer);
        console.error(err);
        allJobs = [];
        setStatus('failed');
    }
}

async function loadStats() {
    try {
        const response = await fetch(`${SERVER_URL}/api/stats`, { signal: AbortSignal.timeout(REQUEST_TIMEOUT) });
        if (!response.ok) throw new Error(`stats 실패. status: ${response.status}`);
        renderStats(await response.json());
    } catch (err) {
        console.warn('통계를 불러오지 못했습니다.', err);
    }
}

async function pingServer() {
    try {
        const response = await fetch(`${SERVER_URL}/api/health`);
        console.log(`${response.ok ? '접속 성공' : '재 접속 시도'}. statusCode: ${response.status} ${response.statusText}`);
    } catch (err) {
        console.warn('서버에 연결할 수 없습니다.', err);
    }
}

// ===== 통계 =====
const pickNumber = (obj, keys) => {
    const key = keys.find((k) => typeof obj?.[k] === 'number');
    return key ? obj[key] : null;
};

function renderStats(stats) {
    const data = stats?.stats ?? stats ?? {};
    const rows = [];
    const jobs = pickNumber(data, ['jobs', 'job_count', 'total_jobs', 'total']);
    const companies = pickNumber(data, ['companies', 'company_count', 'total_companies']);
    if (jobs !== null) rows.push(['공고', jobs]);
    if (companies !== null) rows.push(['기업', companies]);

    const sources = data.sources ?? data.by_source ?? data.source_counts;
    if (Array.isArray(sources)) {
        sources.forEach((s) => rows.push([s.source ?? s.name, s.count ?? s.jobs]));
    } else if (sources && typeof sources === 'object') {
        Object.entries(sources).forEach(([name, count]) => rows.push([name, count]));
    }

    const valid = rows.filter(([label, value]) => label && Number.isFinite(value));
    statsBox.replaceChildren(...valid.map(([label, value]) => {
        const row = el('div', 'statRow');
        row.append(el('span', '', String(label)), el('strong', '', String(value)));
        return row;
    }));
    statsBox.classList.toggle('hide', !valid.length);
}

// ===== 필터 옵션 (지역 / 출처) =====
function fillSelect(select, values) {
    const current = select.value;
    select.querySelectorAll('option:not([value=""])').forEach((option) => option.remove());
    [...values].sort((a, b) => a.localeCompare(b, 'ko')).forEach((v) => select.append(new Option(v, v)));
    select.value = current;
}

function collectOptions() {
    allJobs.forEach((job) => {
        if (job.location) knownLocations.add(job.location);
        if (job.source) knownSources.add(job.source);
    });
    fillSelect(locationSelect, knownLocations);
    fillSelect(sourceSelect, knownSources);
}

// ===== 태그 필터 / 렌더링 =====
function matchesTag(job, tag) {
    const pattern = TAG_PATTERNS[tag] ?? new RegExp(tag.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'i');
    return pattern.test(job.text);
}

function filterJobs(jobs) {
    if (!activeTags.size) return jobs;
    return jobs.filter((job) => [...activeTags].some((tag) => matchesTag(job, tag)));
}

function openDialog(job) {
    dialogTitle.textContent = job.name;
    dialogMeta.textContent = [job.company, job.location, job.source].filter(Boolean).join(' / ');
    dialogText.textContent = job.description || '등록된 상세 설명이 없습니다.';
    dialogLink.href = job.url || '#';
    dialogLink.classList.toggle('hide', !job.url);
    jobDialog.showModal();
}

function createCard(job) {
    const card = el('button', 'card');
    card.type = 'button';
    card.addEventListener('click', () => openDialog(job));

    const titleBox = el('div', 'cardTitleBox');
    const title = el('h3', 'cardTitle', job.name);
    title.title = job.name;
    titleBox.appendChild(title);

    const textBox = el('div', 'cardTextBox');
    if (job.company) textBox.appendChild(el('strong', 'cardCompany', job.company));
    if (job.location) textBox.appendChild(el('span', 'cardMeta', job.location));
    if (job.description) textBox.appendChild(el('p', 'cardDesc', job.description));
    if (job.source) textBox.appendChild(el('span', 'cardSource', job.source));

    card.append(titleBox, textBox);
    return card;
}

function renderCards() {
    clearCards();
    const shown = filterJobs(allJobs);
    resultCount.textContent = `공고 ${shown.length}건`;
    setStatus(shown.length ? 'done' : 'empty');
    cards.append(...shown.map(createCard));
}

function setupTags() {
    tagButtons.forEach((button) => {
        const name = button.textContent.trim();

        button.addEventListener('click', () => {
            const isOn = !activeTags.has(name);
            if (isOn) activeTags.add(name); else activeTags.delete(name);
            button.classList.toggle('tagClicked', isOn);
            button.setAttribute('aria-pressed', String(isOn));
            if (hasLoaded) renderCards();
        });
    });
}

// ===== 이벤트 =====
searchInput.addEventListener('input', () => {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(search, SEARCH_DELAY);
});

searchInput.addEventListener('keydown', (ev) => {
    if (ev.key !== 'Enter' || ev.isComposing) return; // 한글 조합 중 Enter 무시
    clearTimeout(searchTimer);
    search();
});

locationSelect.addEventListener('change', search);
sourceSelect.addEventListener('change', search);
retryButton.addEventListener('click', search);

dialogClose.addEventListener('click', () => jobDialog.close());
jobDialog.addEventListener('click', (ev) => { if (ev.target === jobDialog) jobDialog.close(); }); // 바깥 클릭

window.addEventListener('load', () => {
    checkElements();
    setupTags();
    search();
    loadStats();
    setInterval(pingServer, HEALTH_INTERVAL);
});