import { createToast } from '../../ui/toast.js';

export function initRecommendController(els, store, api, ui) {
    let abortController = null;
    let cachedCourses = [];
    let cachedTotal = 0;
    let toast = createToast(els.toastContainer || document.body);

    function init() {
        // Initial load
        loadFilters();
        loadRecommendations();

        // Subscribe to state changes
        const unsubscribe = store.subscribe((state) => {
            ui.syncActiveUI(els, state);
        });

        // Event Delegation
        els.root.addEventListener('click', handleClick);
        els.difficultySelect?.addEventListener('change', handleDifficultyChange);
        els.strategySelect?.addEventListener('change', handleStrategyChange);

        // Return cleanup
        return () => {
            if (abortController) abortController.abort();
            unsubscribe();
            els.root.removeEventListener('click', handleClick);
            els.difficultySelect?.removeEventListener('change', handleDifficultyChange);
            els.strategySelect?.removeEventListener('change', handleStrategyChange);
            toast.dispose();
        };
    }

    // --- Actions ---

    async function loadFilters() {
        try {
            const topicsRes = await api.fetchTopics();
            cachedCourses = topicsRes.courses || [];
            cachedTotal = (typeof topicsRes.total === 'number' && Number.isFinite(topicsRes.total)) ? topicsRes.total : 0;
            ui.renderCourseTabs(els, cachedCourses, store.get().course, cachedTotal);
            ui.renderTopicFilters(els, cachedCourses, store.get().course, store.get().topic, cachedTotal);
        } catch (error) {
            console.error('Failed to load filters:', error);
            // Non-critical, maybe toast?
        }
    }

    async function loadRecommendations() {
        // Cancel previous request
        if (abortController) {
            abortController.abort();
        }
        abortController = new AbortController();

        ui.setLoading(els);

        try {
            const state = store.get();
            const res = await api.fetchRecommendations(state, { signal: abortController.signal });

            ui.renderVideos(els, res.items || []);
            ui.renderPagination(els, res.page, res.pages);
            ui.updateTotalCount(els, res.total || 0);

        } catch (error) {
            if (error.name === 'AbortError') return;
            console.error('Failed to load recommendations:', error);
            ui.setError(els, error.message || 'Unknown error');
        } finally {
            abortController = null;
        }
    }

    async function handleToggleFav(bvid, btn) {
        if (!bvid) return;
        const isFav = btn.classList.contains('active');
        const nextIsFav = !isFav;

        // Optimistic UI update could be done here, but let's wait for server for safety or do optimistic?
        // Let's do optimistic for responsiveness, revert on error.

        // Optimistic toggle
        btn.classList.toggle('active');
        const icon = btn.querySelector('i');
        if (icon) icon.className = nextIsFav ? 'fas fa-heart' : 'far fa-heart';

        try {
            await api.toggleFav(bvid, nextIsFav);
            toast.show(nextIsFav ? '收藏成功' : '已取消收藏', { variant: 'success', timeoutMs: 2000 });
        } catch (error) {
            // Revert
            btn.classList.toggle('active');
            if (icon) icon.className = isFav ? 'fas fa-heart' : 'far fa-heart'; // Back to original
            toast.show('操作失败: ' + error.message, { variant: 'danger' });
        }
    }

    // --- Event Handlers ---

    function updateAndReload(patch) {
        store.set(patch);
        loadRecommendations();
    }

    function handleDifficultyChange(e) {
        const val = e.target?.value ?? '';
        updateAndReload({ difficulty: val, page: 1 });
    }

    function handleStrategyChange(e) {
        const val = e.target?.value ?? 'hot';
        updateAndReload({ strategy: val, page: 1 });
    }

    function handleClick(e) {
        // Traverse up to find data-action
        const target = e.target.closest('[data-action]');
        if (!target) return;

        const action = target.dataset.action;
        const ds = target.dataset;

        switch (action) {
            case 'course':
                const course = ds.course ?? '';
                store.set({ course, topic: '', page: 1 });
                ui.renderCourseTabs(els, cachedCourses, course, cachedTotal);
                ui.renderTopicFilters(els, cachedCourses, course, '', cachedTotal);
                loadRecommendations();
                break;
            case 'filter':
                const filterType = ds.filter; // topic
                const val = ds.value ?? '';
                if (!filterType) return;
                if (filterType === 'topic') updateAndReload({ topic: val, page: 1 });
                break;
            case 'refresh':
                loadRecommendations();
                break;
            case 'page':
                const page = parseInt(ds.page, 10);
                if (!isNaN(page)) {
                    updateAndReload({ page });
                    window.scrollTo({ top: 0, behavior: 'smooth' });
                }
                break;
            case 'open-video':
                if (ds.bvid) window.open(`/go/${ds.bvid}`, '_blank');
                break;
            case 'toggle-fav':
                e.stopPropagation(); // Prevent card click
                handleToggleFav(ds.bvid, target);
                break;
            case 'open-up':
                e.stopPropagation();
                if (ds.upMid) window.open(`https://space.bilibili.com/${ds.upMid}`, '_blank');
                break;
        }
    }

    // Run init and return dispose
    const dispose = init();
    return { dispose };
}
