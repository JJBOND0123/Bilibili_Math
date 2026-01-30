export function formatDuration(seconds) {
    if (!seconds) return '0:00';
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = seconds % 60;
    
    if (h > 0) {
        return `${h}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
    }
    return `${m}:${s.toString().padStart(2, '0')}`;
}

export function formatCount(count) {
    if (!count) return '0';
    if (count >= 10000) {
        return (count / 10000).toFixed(1) + '万';
    }
    return count.toString();
}

export function getDifficultyClass(difficulty) {
    switch (difficulty) {
        case '入门': return 'easy';
        case '进阶': return 'medium';
        case '高阶': return 'hard';
        default: return '';
    }
}

export function escapeHtml(str) {
    if (!str) return '';
    // Use browser's built-in escaping if possible, or simple regex
    // Since we are in browser environment:
    const div = document.createElement('div');
    div.innerText = str;
    return div.innerHTML;
}
