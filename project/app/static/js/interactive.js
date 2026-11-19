(function () {
  'use strict';

  function getCsrfToken() {
    var cookieVal = null;
    if (document.cookie && document.cookie !== '') {
      var cookies = document.cookie.split(';');
      for (var i = 0; i < cookies.length; i++) {
        var cookie = cookies[i].trim();
        if (cookie.substring(0, 10) === 'csrftoken=') {
          cookieVal = decodeURIComponent(cookie.substring(10));
          break;
        }
      }
    }
    if (!cookieVal) {
      var csrfInput = document.querySelector('input[name="csrfmiddlewaretoken"]');
      if (csrfInput) cookieVal = csrfInput.value;
    }
    return cookieVal;
  }

  function showToast(message, type) {
    type = type || 'success';
    var toast = document.getElementById('wireToast');
    if (!toast) {
      toast = document.createElement('div');
      toast.id = 'wireToast';
      toast.className = 'wire-toast';
      document.body.appendChild(toast);
    }
    toast.textContent = message;
    toast.className = 'wire-toast wire-toast-' + type + ' show';
    clearTimeout(toast._timeout);
    toast._timeout = setTimeout(function () {
      toast.className = 'wire-toast';
    }, 3500);
  }

  function setupLiveSearch() {
    var searchInputs = document.querySelectorAll('.wire-search-input');
    Array.prototype.forEach.call(searchInputs, function (input) {
      var form = input.closest('form');
      if (!form) return;

      var dropdown = document.createElement('div');
      dropdown.className = 'wire-search-dropdown';
      dropdown.style.display = 'none';
      input.parentNode.style.position = 'relative';
      input.parentNode.appendChild(dropdown);

      var timer = null;

      function closeDropdown() {
        dropdown.style.display = 'none';
        dropdown.innerHTML = '';
      }

      input.addEventListener('input', function () {
        var query = input.value.trim();
        clearTimeout(timer);

        if (query.length < 2) {
          closeDropdown();
          return;
        }

        dropdown.innerHTML = '<div class="wire-search-status"><span class="wire-spinner"></span> Поиск товаров...</div>';
        dropdown.style.display = 'block';

        timer = setTimeout(function () {
          fetch('/api/search/?q=' + encodeURIComponent(query))
            .then(function (res) {
              if (!res.ok) throw new Error('Ошибка сервера');
              return res.json();
            })
            .then(function (data) {
              if (!data.results || data.results.length === 0) {
                dropdown.innerHTML = '<div class="wire-search-empty">По запросу «' + escapeHtml(query) + '» ничего не найдено</div>';
                return;
              }

              var html = '<div class="wire-search-results-list">';
              data.results.forEach(function (item) {
                html += '<a href="' + item.url + '" class="wire-search-item">';
                html += '<img src="' + item.photo + '" alt="" width="36" height="36" class="wire-search-thumb">';
                html += '<div class="wire-search-info">';
                html += '<div class="wire-search-name">' + escapeHtml(item.name) + '</div>';
                html += '<div class="wire-search-sub">' + escapeHtml(item.volume) + '</div>';
                html += '</div>';
                html += '<div class="wire-search-price">' + (item.type === 'cooler' ? '' : 'от ') + item.price + ' ₽</div>';
                html += '</a>';
              });
              html += '</div>';
              dropdown.innerHTML = html;
            })
            .catch(function () {
              dropdown.innerHTML = '<div class="wire-search-empty">Не удалось выполнить поиск. Попробуйте позже.</div>';
            });
        }, 250);
      });

      document.addEventListener('click', function (e) {
        if (!input.contains(e.target) && !dropdown.contains(e.target)) {
          closeDropdown();
        }
      });

      input.addEventListener('keydown', function (e) {
        if (e.key === 'Escape') {
          closeDropdown();
        }
      });
    });
  }

  var modalEl = null;

  function ensureModal() {
    if (modalEl) return modalEl;
    modalEl = document.createElement('div');
    modalEl.id = 'wireProductModal';
    modalEl.className = 'wire-modal-overlay';
    modalEl.innerHTML = [
      '<div class="wire-modal" role="dialog" aria-modal="true" aria-labelledby="modalTitle">',
      '  <button type="button" class="wire-modal-close" aria-label="Закрыть">&times;</button>',
      '  <div id="modalContent" class="wire-modal-content">',
      '    <div class="wire-modal-loading"><span class="wire-spinner"></span> Загрузка информации о товаре...</div>',
      '  </div>',
      '</div>'
    ].join('\n');
    document.body.appendChild(modalEl);

    var closeBtn = modalEl.querySelector('.wire-modal-close');
    closeBtn.addEventListener('click', closeModal);
    modalEl.addEventListener('click', function (e) {
      if (e.target === modalEl) closeModal();
    });
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && modalEl.classList.contains('open')) {
        closeModal();
      }
    });

    return modalEl;
  }

  function openQuickView(productId) {
    ensureModal();
    var content = document.getElementById('modalContent');
    content.innerHTML = '<div class="wire-modal-loading"><span class="wire-spinner"></span> Загрузка информации о товаре...</div>';
    modalEl.classList.add('open');
    document.body.style.overflow = 'hidden';

    fetch('/api/quickview/' + productId + '/')
      .then(function (res) {
        if (!res.ok) throw new Error('Товар не найден');
        return res.json();
      })
      .then(function (data) {
        var stockBadge = data.in_stock
          ? '<span class="wire-stock-badge wire-stock-badge-in">В наличии</span>'
          : '<span class="wire-stock-badge wire-stock-badge-out">Под заказ</span>';

        content.innerHTML = [
          '<div class="wire-modal-grid">',
          '  <div class="wire-modal-img-box">',
          '    <img src="' + data.photo + '" alt="' + escapeHtml(data.name) + '" width="180" height="180" class="wire-modal-img">',
          '  </div>',
          '  <div class="wire-modal-details">',
          '    <div class="wire-modal-meta">' + stockBadge + ' <span class="wire-modal-vol">' + escapeHtml(data.volume) + '</span></div>',
          '    <h2 id="modalTitle" class="wire-modal-title">' + escapeHtml(data.name) + '</h2>',
          '    <div class="wire-modal-price">' + escapeHtml(data.price) + ' ₽ <small class="wire-modal-deposit">(залог: ' + escapeHtml(data.deposit_price) + ' ₽)</small></div>',
          '    <p class="wire-modal-desc">' + escapeHtml(data.description) + '</p>',
          '    <div class="wire-modal-actions">',
          data.in_stock
            ? '      <button type="button" class="wire-btn wire-btn-quick-add" data-product-id="' + data.id + '">Добавить в заказ</button>'
            : '      <button type="button" class="wire-btn" disabled>Нет в наличии</button>',
          '      <a href="' + data.url + '" class="wire-btn wire-btn-secondary">Подробнее</a>',
          '    </div>',
          '  </div>',
          '</div>'
        ].join('\n');

        var quickAddBtn = content.querySelector('.wire-btn-quick-add');
        if (quickAddBtn) {
          quickAddBtn.addEventListener('click', function () {
            addToCartAjax(data.id, quickAddBtn);
          });
        }
      })
      .catch(function () {
        content.innerHTML = '<div class="wire-modal-error">Не удалось загрузить данные о товаре. Пожалуйста, откройте страницу каталога.</div>';
      });
  }

  function closeModal() {
    if (modalEl) {
      modalEl.classList.remove('open');
      document.body.style.overflow = '';
    }
  }

  function addToCartAjax(productId, btnEl, quantity) {
    quantity = quantity || 1;
    var csrfToken = getCsrfToken();
    var oldText = btnEl ? btnEl.textContent : '';

    if (btnEl) {
      btnEl.disabled = true;
      btnEl.innerHTML = '<span class="wire-spinner wire-spinner-sm"></span>';
    }

    var formData = new FormData();
    formData.append('quantity', quantity);
    if (csrfToken) {
      formData.append('csrfmiddlewaretoken', csrfToken);
    }

    var headers = {
      'X-Requested-With': 'XMLHttpRequest',
      'Accept': 'application/json'
    };
    if (csrfToken) {
      headers['X-CSRFToken'] = csrfToken;
    }

    fetch('/cart/add/' + productId + '/', {
      method: 'POST',
      headers: headers,
      body: formData
    })
      .then(function (res) {
        if (!res.ok) throw new Error('Ошибка добавления');
        return res.json();
      })
      .then(function (data) {
        if (btnEl) {
          btnEl.textContent = 'Добавлено ✓';
          setTimeout(function () {
            btnEl.textContent = oldText;
            btnEl.disabled = false;
          }, 1500);
        }

        updateHeaderCartBadge(data.cart_count);
        showToast(data.message || 'Товар добавлен в корзину');
      })
      .catch(function (err) {
        if (btnEl) {
          btnEl.textContent = oldText;
          btnEl.disabled = false;
        }
        showToast('Не удалось добавить товар: возможно, он закончился.', 'error');
      });
  }

  function updateHeaderCartBadge(count) {
    var orderButtons = document.querySelectorAll('.wire-header-right a[href*="cart"], .mobile-menu a[href*="cart"]');
    Array.prototype.forEach.call(orderButtons, function (btn) {
      if (btn.classList.contains('wire-btn')) {
        btn.textContent = count > 0 ? 'Заказать (' + count + ')' : 'Заказать';
      }
    });
  }

  function setupQuickViewTriggers() {
    var cards = document.querySelectorAll('.wire-catalog-card, .wire-cards-grid .wire-card');
    Array.prototype.forEach.call(cards, function (card) {
      if (card.dataset.quickviewInit === 'true') return;
      card.dataset.quickviewInit = 'true';

      var link = card.querySelector('h2 a, h3 a');
      if (!link) return;
      var href = link.getAttribute('href') || '';
      var match = href.match(/\/catalog\/(\d+)\//);
      if (!match) return;
      var productId = match[1];

      var imgBox = card.querySelector('.wire-card-img-box');
      if (imgBox) {
        var qvBtn = document.createElement('button');
        qvBtn.type = 'button';
        qvBtn.className = 'wire-quickview-btn';
        qvBtn.textContent = 'Быстрый просмотр';
        qvBtn.setAttribute('aria-label', 'Быстрый просмотр товара');
        qvBtn.addEventListener('click', function (e) {
          e.preventDefault();
          e.stopPropagation();
          openQuickView(productId);
        });
        imgBox.appendChild(qvBtn);
      }
    });
  }

  function setupDetailCartForm() {
    var detailForms = document.querySelectorAll('.wire-detail-form');
    Array.prototype.forEach.call(detailForms, function (form) {
      form.addEventListener('submit', function (e) {
        e.preventDefault();
        var submitter = e.submitter;
        var btn = submitter || (window.innerWidth <= 768 ? form.querySelector('.mobile-only[type="submit"]') : form.querySelector('.desktop-only[type="submit"]')) || form.querySelector('button[type="submit"]');
        var qtyInput = form.querySelector('input[name="quantity"]');
        var qty = qtyInput ? parseInt(qtyInput.value, 10) || 1 : 1;
        var action = form.getAttribute('action') || '';
        var match = action.match(/\/cart\/add\/(\d+)\//);
        if (match) {
          addToCartAjax(match[1], btn, qty);
        } else {
          form.submit();
        }
      });
    });
  }

  function escapeHtml(str) {
    if (!str) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function init() {
    setupLiveSearch();
    setupQuickViewTriggers();
    setupDetailCartForm();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

  window.WireInteractive = {
    openQuickView: openQuickView,
    addToCartAjax: addToCartAjax,
    showToast: showToast
  };
})();
