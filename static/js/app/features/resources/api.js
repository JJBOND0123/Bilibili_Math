import { requestJSON } from '../../services/api.js';

export async function fetchTopics(opts = {}) {
    return requestJSON('/api/topics', { signal: opts.signal });
}

export async function fetchRecommendations(query, opts = {}) {
    const params = {
        strategy: query.strategy,
        page: query.page,
        page_size: query.pageSize,
        only_recommended: query.onlyRecommended,
    };
    if (query.course) params.course = query.course;
    if (query.topic) params.topic = query.topic;
    if (query.difficulty) params.difficulty = query.difficulty;
    if (query.q) params.q = query.q;  // 搜索关键词

    return requestJSON('/api/recommend', { params, signal: opts.signal });
}

export async function toggleFav(bvid, nextIsFav, opts = {}) {
    const url = nextIsFav ? '/api/action' : '/api/remove_action';
    return requestJSON(url, {
        method: 'POST',
        body: { bvid, type: 'fav' },
        signal: opts.signal
    });
}
