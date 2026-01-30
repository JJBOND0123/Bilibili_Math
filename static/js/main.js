// Shared helpers used across templates to keep naming aligned with backend fields.
(function (window) {
  function zeroPad(num) {
    return num < 10 ? '0' + num : String(num);
  }

  window.escapeHtml = function (text) {
    if (text === null || text === undefined) return '';
    return String(text)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/\"/g, '&quot;')
      .replace(/'/g, '&#039;');
  };

  window.formatCount = function (num) {
    const value = Number(num) || 0;
    if (value >= 100000000) return (value / 100000000).toFixed(2) + '\u4ebf';
    if (value >= 10000) return (value / 10000).toFixed(1) + '\u4e07';
    return value.toLocaleString();
  };

  window.formatDuration = function (seconds) {
    const total = Math.max(0, parseInt(seconds || 0, 10));
    const h = Math.floor(total / 3600);
    const m = Math.floor((total % 3600) / 60);
    const s = total % 60;
    return h > 0 ? `${h}:${zeroPad(m)}:${zeroPad(s)}` : `${zeroPad(m)}:${zeroPad(s)}`;
  };

  window.formatDate = function (dateInput) {
    if (!dateInput) return '';
    const d = new Date(dateInput);
    if (Number.isNaN(d.getTime())) return '';
    const month = d.getMonth() + 1;
    const day = d.getDate();
    return `${zeroPad(month)}-${zeroPad(day)}`;
  };

  window.showToast = function (msg, type) {
    const container = document.getElementById('toastContainer');
    if (!container) return;
    const safe = window.escapeHtml(msg);
    const kind = type || 'success';
    const icon =
      kind === 'success'
        ? '<i class="fas fa-check-circle"></i>'
        : '<i class="fas fa-info-circle"></i>';
    const toast = document.createElement('div');
    toast.className = 'custom-toast';
    toast.innerHTML = `${icon} <span>${safe}</span>`;
    container.appendChild(toast);

    setTimeout(() => toast.classList.add('show'), 10);
    setTimeout(() => {
      toast.classList.remove('show');
      setTimeout(() => toast.remove(), 260);
    }, 2000);
  };

  window.showSkeleton = function ($container, count, colClass) {
    if (!window.$ || !$container || !$container.length) return;
    const cols = colClass || 'col-lg-3 col-md-4 col-sm-6';
    const n = Number(count || 4);
    let html = '';
    for (let i = 0; i < n; i++) {
      html += `
        <div class="${cols}">
          <div class="bili-card p-0" style="height:240px; border:none;">
            <div class="skeleton" style="width:100%; height:140px;"></div>
            <div class="p-3">
              <div class="skeleton mb-2" style="width:90%; height:18px;"></div>
              <div class="skeleton mb-2" style="width:60%; height:14px;"></div>
              <div class="skeleton" style="width:40%; height:14px;"></div>
            </div>
          </div>
        </div>`;
    }
    $container.html(html);
  };

  /**
   * 通用视频卡片渲染（resources/profile 等页面复用）
   * @param {Object} v 后端返回的视频对象
   * @param {Object} options 可选项：dateText, actionHtml
   */
  window.renderVideoCard = function (v, options) {
    const opts = options || {};
    const bvid = window.escapeHtml(v && v.bvid);
    const title = window.escapeHtml(v && v.title);
    const upName = window.escapeHtml((v && v.up_name) || '');
    const upFace = (v && v.up_face) || 'https://placehold.co/20x20/E3E5E7/999?text=U';
    const pic = (v && v.pic_url) || 'https://placehold.co/320x200/F6F7F8/9499A0?text=%E5%B0%81%E9%9D%A2';
    const duration = window.escapeHtml((v && v.category) || window.formatDuration(v && v.duration));
    const view = window.formatCount(v && v.view_count);

    const rawDateText =
      opts.dateText !== undefined
        ? typeof opts.dateText === 'function'
          ? opts.dateText(v)
          : opts.dateText
        : window.formatDate(v && v.pubdate);
    const date = window.escapeHtml(rawDateText);

    const isFav = !!(v && v.is_fav);

    const upRowHtml = `
        <div class="up-row">
          <img src="${upFace}" class="up-avatar" loading="lazy" decoding="async" referrerpolicy="no-referrer"
               onerror="this.src='https://placehold.co/20x20/E3E5E7/999?text=U'">
          <span class="text-truncate">${upName}</span>
        </div>`;

    const defaultActionHtml = `
      <div class="card-actions">
        <div class="card-action-btn ${isFav ? 'active' : ''}" onclick="doAction('${bvid}', 'fav', this, false, event)">
          <i class="${isFav ? 'fas' : 'far'} fa-heart"></i> ${isFav ? '\u5df2\u6536\u85cf' : '\u6536\u85cf'}
        </div>
      </div>`;

    const actionHtml =
      opts.actionHtml !== undefined
        ? typeof opts.actionHtml === 'function'
          ? opts.actionHtml(v)
          : opts.actionHtml
        : defaultActionHtml;

    return `
      <div class="bili-card">
        <div class="card-img-box">
          <a href="/go/${bvid}" target="_blank">
            <img src="${pic}" loading="lazy" decoding="async" referrerpolicy="no-referrer"
                 onerror="this.src='https://placehold.co/320x200/eee/999?text=Error'">
          </a>
          <div class="duration-badge">${duration}</div>
        </div>
        <div class="card-info">
          <a href="/go/${bvid}" target="_blank" class="card-title" title="${title}">${title}</a>
          ${upRowHtml}
          <div class="stat-row">
            <span><i class="far fa-play-circle me-1"></i>${view}</span>
            <span><i class="far fa-clock me-1"></i>${date}</span>
          </div>
          ${actionHtml || ''}
        </div>
      </div>`;
  };

  /**
   * 生成标准移除按钮 HTML（复用于收藏/历史等页面）
   * @param {string} bvid 视频 ID
   * @param {string} type 类型：'fav' 或 'history'
   * @param {string} text 按钮文字
   * @param {string} icon 按钮图标 class
   */
  window.renderRemoveButton = function (bvid, type, text, icon) {
    const safeId = window.escapeHtml(bvid || '');
    const safeType = window.escapeHtml(type || '');
    const iconClass = icon || 'fas fa-trash-alt';
    const label = text || '删除';
    return `<div class="card-actions">
      <button type="button" class="card-action-btn" onclick="removeAction('${safeId}', '${safeType}')">
        <i class="${iconClass}"></i> ${label}
      </button>
    </div>`;
  };

  window.renderVideoGrid = function (videos, $container, options) {
    if (!window.$ || !$container || !$container.length) return;
    if (!videos || videos.length === 0) {
      $container.html('<div class="col-12 text-center py-5 text-muted">暂无相关数据</div>');
      return;
    }
    const opts = options || {};
    const colClass = opts.colClass || 'col-lg-3 col-md-4 col-sm-6';
    let html = '';
    videos.forEach((v) => {
      html += `<div class="${colClass}">${window.renderVideoCard(v, opts.cardOptions ? opts.cardOptions(v) : opts.cardOptions)}</div>`;
    });
    $container.html(html);
  };

  window.doAction = function (bvid, type, btn, _isSmallBtn, evt) {
    if (evt) {
      evt.preventDefault();
      evt.stopPropagation();
    }
    if (!window.$ || !btn || !bvid) return;
    if ((type || '').toString() !== 'fav') return;

    const $btn = $(btn);
    const wasActive = $btn.hasClass('active');
    const url = wasActive ? '/api/remove_action' : '/api/action';

    $.ajax({
      url: url,
      type: 'POST',
      contentType: 'application/json',
      data: JSON.stringify({ bvid: bvid, type: 'fav' }),
      success: function () {
        const nextActive = !wasActive;
        $btn.toggleClass('active', nextActive);

        const $icon = $btn.find('i');
        if ($icon.length) {
          $icon.removeClass('fas far').addClass(nextActive ? 'fas' : 'far');
        }

        $btn
          .contents()
          .filter(function () {
            return this.nodeType === Node.TEXT_NODE;
          })
          .remove();
        $btn.append(document.createTextNode(nextActive ? ' \u5df2\u6536\u85cf' : ' \u6536\u85cf'));

        if (window.showToast) {
          window.showToast(
            nextActive ? '\u6536\u85cf\u6210\u529f' : '\u5df2\u53d6\u6d88\u6536\u85cf',
            'success'
          );
        }
      },
      error: function () {
        if (window.showToast) window.showToast('\u64cd\u4f5c\u5931\u8d25', 'info');
      },
    });
  };
})(window);
