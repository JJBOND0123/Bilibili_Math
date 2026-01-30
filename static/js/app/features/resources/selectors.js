export function getRecommendElements(root) {
    const q = (sel) => root.querySelector(sel);
    const getGlobal = (sel) => document.querySelector(sel);

    return {
        root: root,
        toastContainer: q('[data-role="toast-container"]') || getGlobal('#toastContainer'),
        videoGrid: q('[data-role="video-grid"]'),
        pagination: q('[data-role="pagination"]'),
        totalCount: q('[data-role="total-count"]'),
        totalCountInline: q('[data-role="total-count-inline"]'),
        courseTabs: q('[data-role="course-tabs"]'),
        topicFilters: q('[data-role="topic-filters"]'),
        difficultySelect: q('[data-role="difficulty-select"]'),
        strategySelect: q('[data-role="strategy-select"]'),
    };
}
