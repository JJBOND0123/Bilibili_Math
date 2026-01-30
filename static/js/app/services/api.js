export class ApiError extends Error {
    constructor(message, status, payload) {
        super(message);
        this.status = status;
        this.payload = payload;
        this.name = 'ApiError';
    }
}

/**
 * @param {string} path 
 * @param {Object} [opts]
 * @returns {Promise<any>}
 */
export async function requestJSON(path, opts = {}) {
    const { method = 'GET', params, body, headers = {}, signal } = opts;

    let url = path;
    if (params) {
        const usp = new URLSearchParams();
        for (const key in params) {
            if (params[key] !== undefined && params[key] !== null && params[key] !== '') {
                usp.append(key, params[key]);
            }
        }
        const qs = usp.toString();
        if (qs) {
            url += (url.includes('?') ? '&' : '?') + qs;
        }
    }

    const config = {
        method,
        headers: {
            'Content-Type': 'application/json',
            ...headers
        },
        signal
    };

    if (body) {
        config.body = JSON.stringify(body);
    }

    const response = await fetch(url, config);

    if (!response.ok) {
        let payload = null;
        try { payload = await response.json(); } catch (e) { /* ignore */ }
        throw new ApiError(`Request failed: ${response.status}`, response.status, payload);
    }

    return response.json();
}
