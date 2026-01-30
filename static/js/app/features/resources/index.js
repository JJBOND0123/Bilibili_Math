import { createRecommendStore } from './state.js';
import { getRecommendElements } from './selectors.js';
import * as api from './api.js'; // Import all as object to pass to controller
import * as render from './render.js';
import { initRecommendController } from './controller.js';

export function initRecommend(root, options = {}) {
    const els = getRecommendElements(root);

    // Check if critical elements exist
    if (!els.videoGrid) {
        console.error('Critical elements for recommend feature not found.');
        return { dispose: () => { } };
    }

    const store = createRecommendStore(options.initialState);

    // Link everything in Controller
    const controller = initRecommendController(els, store, api, render);

    return controller;
}
