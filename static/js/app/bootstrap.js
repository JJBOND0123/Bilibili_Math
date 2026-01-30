// Bootstrap logic
// Reads data-page from body/html and loads corresponding page script

(async function bootstrap() {
    const pageName = document.body.dataset.page || document.documentElement.dataset.page;

    if (!pageName) {
        // console.log('No data-page defined, skipping page specific init.');
        return;
    }

    // No-bundler setup: only load page modules that exist.
    // Add more entries here as you modularize other pages.
    const supportedPages = new Set(['resources']);
    if (!supportedPages.has(pageName)) {
        return;
    }

    try {
        // Dynamic import
        const module = await import(`../pages/${pageName}.js`);

        // Convention: export function init<PageName>Page or just initPage?
        // Let's us specific name or a standard 'default' or 'init'.
        // The prompt requirement said: export function initRecommendPage

        // Helper to find init function: init{PageName}Page (CamelCase)
        const pascalCase = pageName.charAt(0).toUpperCase() + pageName.slice(1);
        const initFnName = `init${pascalCase}Page`;

        if (typeof module[initFnName] === 'function') {
            const instance = module[initFnName]();

            // Handle unload if needed?
            window.addEventListener('beforeunload', () => {
                if (instance && typeof instance.dispose === 'function') {
                    instance.dispose();
                }
            });
        } else {
            console.warn(`Page module loaded but ${initFnName} not found.`);
        }

    } catch (error) {
        console.error(`Failed to load page script for ${pageName}:`, error);
    }
})();
