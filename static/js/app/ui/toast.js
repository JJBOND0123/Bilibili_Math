export function createToast(container) {
    /**
     * @param {string} message 
     * @param {Object} [opts]
     * @param {'info'|'success'|'warning'|'danger'} [opts.variant='info']
     * @param {number} [opts.timeoutMs=3000]
     */
    function show(message, opts = {}) {
        const { variant = 'info', timeoutMs = 3000 } = opts;

        const toastEl = document.createElement('div');
        toastEl.className = `toast align-items-center text-white bg-${variant} border-0 show`;
        toastEl.setAttribute('role', 'alert');
        toastEl.setAttribute('aria-live', 'assertive');
        toastEl.setAttribute('aria-atomic', 'true');

        toastEl.innerHTML = `
            <div class="d-flex">
                <div class="toast-body">
                    ${message}
                </div>
                <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
            </div>
        `;

        // Add to container (prepend so new ones show on top/bottom as configured, usually append for bottom)
        container.appendChild(toastEl);

        // Auto remove
        const timer = setTimeout(() => {
            remove();
        }, timeoutMs);

        // Close button handler
        const btn = toastEl.querySelector('.btn-close');
        btn.onclick = () => {
            clearTimeout(timer);
            remove();
        };

        function remove() {
            toastEl.classList.remove('show');
            setTimeout(() => {
                if (toastEl.parentNode === container) {
                    container.removeChild(toastEl);
                }
            }, 300); // Wait for transition
        }
    }

    function dispose() {
        container.innerHTML = '';
    }

    return { show, dispose };
}
