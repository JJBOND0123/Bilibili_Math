import { initRecommend } from '../app/features/resources/index.js';

export function initResourcesPage() {
    // Find the feature container
    const container = document.querySelector('[data-feature="resources"]');
    if (!container) {
        console.warn('Resources feature container not found');
        return;
    }

    // 从 URL 读取搜索参数
    const urlParams = new URLSearchParams(window.location.search);
    const q = urlParams.get('q') || '';

    // 如果有搜索关键词，同步到搜索框
    if (q) {
        const searchInput = document.getElementById('global-search-input');
        if (searchInput) searchInput.value = q;
    }

    const feature = initRecommend(container, {
        initialState: { q }
    });

    // Return dispose
    return {
        dispose: () => {
            feature.dispose();
        }
    };
}
