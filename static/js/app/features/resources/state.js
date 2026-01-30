export function createRecommendStore(initial = {}) {
    let state = {
        strategy: 'hot',
        course: '',
        topic: '',
        difficulty: '',
        q: '',  // 搜索关键词
        page: 1,
        pageSize: 8,
        onlyRecommended: true,
        ...initial
    };

    const listeners = new Set();

    function get() {
        return { ...state };
    }

    function set(patch) {
        const next = { ...state, ...patch };
        // Shallow compare or just trigger always? Simple trigger first.
        state = next;
        notify();
        return state;
    }

    function subscribe(fn) {
        listeners.add(fn);
        return () => listeners.delete(fn);
    }

    function notify() {
        listeners.forEach(fn => fn(state));
    }

    return { get, set, subscribe };
}
