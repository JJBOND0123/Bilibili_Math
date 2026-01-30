import { formatDuration, formatCount, escapeHtml } from '../../utils/format.js';

export function setLoading(els) {
    if (els.videoGrid) {
        els.videoGrid.innerHTML = `
            <div class="loading-state">
                <div class="loading-spinner">
                    <div class="spinner-ring"></div>
                    <i class="fas fa-graduation-cap"></i>
                </div>
                <p>正在为您筛选优质内容...</p>
            </div>
        `;
    }
}

export function setEmpty(els, message = '暂无推荐视频') {
    if (els.videoGrid) {
        els.videoGrid.innerHTML = `
            <div class="empty-state">
                <i class="fas fa-inbox"></i>
                <h3>${escapeHtml(message)}</h3>
                <p>请尝试调整筛选条件</p>
            </div>
        `;
    }
}

export function setError(els, message) {
    if (els.videoGrid) {
        els.videoGrid.innerHTML = `
            <div class="empty-state">
                <i class="fas fa-exclamation-triangle" style="color: #f5576c;"></i>
                <h3>加载失败</h3>
                <p>${escapeHtml(message)}</p>
            </div>
        `;
    }
}

export function renderCourseTabs(els, courses, activeCourse, total) {
    if (!els.courseTabs) return;

    const sumCount = (courses || []).reduce((sum, c) => sum + (c.count || 0), 0);
    const totalCount = (typeof total === 'number' && Number.isFinite(total)) ? total : sumCount;
    const allActive = !activeCourse ? 'active' : '';

    let html = `
        <div class="course-tab ${allActive}" data-action="course" data-course="">
            全部 <span class="count">(${totalCount})</span>
        </div>
    `;

    (courses || []).forEach(course => {
        const isActive = course.course === activeCourse ? 'active' : '';
        html += `
            <div class="course-tab ${isActive}" data-action="course" data-course="${escapeHtml(course.course)}">
                ${escapeHtml(course.course)} <span class="count">(${course.count || 0})</span>
            </div>
        `;
    });

    els.courseTabs.innerHTML = html;
}

export function renderTopicFilters(els, courses, activeCourse, activeTopic, total) {
    if (!els.topicFilters) return;

    const course = (activeCourse || '').trim();

    // 如果没有选择具体科目（即"全部"），则不显示知识点标签
    if (!course) {
        els.topicFilters.innerHTML = '';
        return;
    }

    let topics = [];
    let allCount = 0;
    const hit = (courses || []).find(c => c.course === course);
    topics = hit?.topics || [];
    allCount = hit?.count || 0;

    if (!allCount) {
        allCount = topics.reduce((sum, t) => sum + (t.count || 0), 0);
    }
    const allActive = !activeTopic ? 'active' : '';

    let html = `
        <div class="topic-chip ${allActive}" data-action="filter" data-filter="topic" data-value="">
            <span>全部</span>
            <span class="chip-count" id="topicAllCount">${allCount}</span>
        </div>
    `;

    topics.forEach(topic => {
        const isActive = topic.topic === activeTopic ? 'active' : '';
        html += `
            <div class="topic-chip ${isActive}" data-action="filter" data-filter="topic" data-value="${escapeHtml(topic.topic)}">
                <span>${escapeHtml(topic.topic)}</span>
                <span class="chip-count">${topic.count || 0}</span>
            </div>
        `;
    });

    els.topicFilters.innerHTML = html;
}

export function syncActiveUI(els, state) {
    const root = els.root || document;

    // Course Tabs
    root.querySelectorAll('[data-action="course"]').forEach(tab => {
        tab.classList.toggle('active', (tab.dataset.course ?? '') === (state.course || ''));
    });

    // Topic Filters
    syncFilterActive(els.topicFilters, 'topic', state.topic);

    // Strategy Select
    if (els.strategySelect) {
        const normalized = state.strategy || 'hot';
        if (els.strategySelect.value !== normalized) {
            els.strategySelect.value = normalized;
        }
    }

    // Difficulty Select
    if (els.difficultySelect) {
        const normalized = state.difficulty || '';
        if (els.difficultySelect.value !== normalized) {
            els.difficultySelect.value = normalized;
        }
    }
}

function syncFilterActive(container, filterType, activeValue) {
    if (!container) return;
    const normalized = activeValue || '';

    container.querySelectorAll('.topic-chip').forEach(item => {
        if (item.dataset.action !== 'filter') return;
        if (item.dataset.filter && item.dataset.filter !== filterType) return;
        const value = item.dataset.value ?? '';
        item.classList.toggle('active', value === normalized);
    });
}

export function renderVideos(els, items) {
    if (!els.videoGrid) return;
    if (!items || items.length === 0) {
        setEmpty(els);
        return;
    }

    els.videoGrid.innerHTML = items.map((video, index) => createVideoCard(video, index)).join('');
}

function createVideoCard(video, index) {
    const duration = formatDuration(video.duration);
    const views = formatCount(video.view_count);
    const scoreVal = video.quality_score;
    const score = (typeof scoreVal === 'number' && Number.isFinite(scoreVal) && scoreVal > 0) ? Math.round(scoreVal) : null;

    const picUrl = video.pic_url || 'https://placehold.co/320x180/667eea/fff?text=Video';
    const upFace = video.up_face || 'https://placehold.co/50x50/E3E5E7/999?text=U';
    const isFav = video.is_fav;
    const favClass = isFav ? 'active' : '';
    const favIcon = isFav ? 'fas fa-heart' : 'far fa-heart';

    // Format date
    let dateStr = '近期';
    if (video.pubdate) {
        const d = new Date(video.pubdate);

        if (!isNaN(d.getTime())) {
            const m = d.getMonth() + 1;
            const da = d.getDate();
            dateStr = (m < 10 ? '0' + m : m) + '-' + (da < 10 ? '0' + da : da);
        }
    }

    return `
    <div class="video-card fade-in-up" style="animation-delay: ${index * 0.05}s">
        <div class="card-cover" data-action="open-video" data-bvid="${video.bvid}">
            <img src="${picUrl}" referrerpolicy="no-referrer" 
                 onerror="this.src='https://placehold.co/320x180/f1f2f3/9499a0?text=加载失败'" 
                 alt="${escapeHtml(video.title)}">
            <div class="cover-overlay"></div>
            <div class="play-btn">
                <i class="fas fa-play"></i>
            </div>
            <div class="card-badges">
                <span class="duration-badge">${duration || 'HD'}</span>
                ${score ? `<span class="quality-badge">${score}分</span>` : ''}
            </div>
        </div>

        <div class="card-body">
            <div class="card-title" data-action="open-video" data-bvid="${video.bvid}" title="${escapeHtml(video.title)}">
                ${escapeHtml(video.title)}
            </div>

            <div class="card-meta">
                <div class="up-info" data-action="open-up" data-up-mid="${video.up_mid || ''}">
                    <img class="up-avatar" src="${upFace}" referrerpolicy="no-referrer" 
                         onerror="this.src='https://placehold.co/50x50/E3E5E7/999?text=U'">
                    <span class="up-name">${escapeHtml(video.up_name || '未知UP主')}</span>
                </div>
                <div class="stat-row">
                    <div class="stat">
                        <i class="fas fa-play"></i>
                        <span>${views}</span>
                    </div>
                    <div class="stat">
                        <i class="far fa-clock"></i>
                        <span>${dateStr}</span>
                    </div>
                </div>
            </div>
        </div>

        <div class="card-footer">
            <button class="action-btn fav-btn ${favClass}" data-action="toggle-fav" data-bvid="${video.bvid}">
                <i class="${favIcon}"></i>
                <span>${isFav ? '已收藏' : '收藏'}</span>
            </button>
        </div>
    </div>`;
}

export function renderPagination(els, page, pages) {
    if (!els.pagination) return;
    if (!pages || pages <= 1) {
        els.pagination.innerHTML = '';
        return;
    }

    let html = '';

    // Prev
    html += `<li class="page-item ${page <= 1 ? 'disabled' : ''}">
                <button class="page-link" data-action="page" data-page="${page - 1}">
                    <i class="fas fa-chevron-left"></i>
                </button>
             </li>`;

    const startPage = Math.max(1, page - 2);
    const endPage = Math.min(pages, page + 2);

    if (startPage > 1) {
        html += `<li class="page-item"><button class="page-link" data-action="page" data-page="1">1</button></li>`;
        if (startPage > 2) html += `<li class="page-item disabled"><span class="page-link">...</span></li>`;
    }

    for (let i = startPage; i <= endPage; i++) {
        html += `<li class="page-item ${i === page ? 'active' : ''}">
                    <button class="page-link" data-action="page" data-page="${i}">${i}</button>
                 </li>`;
    }

    if (endPage < pages) {
        if (endPage < pages - 1) html += `<li class="page-item disabled"><span class="page-link">...</span></li>`;
        html += `<li class="page-item"><button class="page-link" data-action="page" data-page="${pages}">${pages}</button></li>`;
    }

    // Next
    html += `<li class="page-item ${page >= pages ? 'disabled' : ''}">
                <button class="page-link" data-action="page" data-page="${page + 1}">
                    <i class="fas fa-chevron-right"></i>
                </button>
             </li>`;

    els.pagination.innerHTML = `<ul class="bili-pager">${html}</ul>`;
}

export function updateTotalCount(els, total) {
    if (els.totalCount) {
        els.totalCount.textContent = total;
    }
    if (els.totalCountInline) {
        els.totalCountInline.textContent = total;
    }
}
