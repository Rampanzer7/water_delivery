
(function () {
  'use strict';

  var EMAIL_REGEX = /^[a-zA-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)+$/;
  var PHONE_REGEX = /^(?:\+?7|8)?[\s(-]*\d{3}[\s)-]*\d{3}[\s-]*\d{2}[\s-]*\d{2}$/;

  function getErrorMessage(input) {
    var val = (input.value || '').trim();
    var name = (input.name || '').toLowerCase();
    var type = (input.type || '').toLowerCase();
    var isRequired = input.required || input.hasAttribute('required') || input.dataset.required === 'true';

    if (isRequired && !val) {
      if (type === 'checkbox') {
        if (!input.checked) return 'Необходимо отметить этот пункт.';
      } else if (input.tagName === 'SELECT') {
        return 'Пожалуйста, выберите вариант из списка.';
      } else {
        return 'Поле обязательно для заполнения.';
      }
    }

    if (!val) {
      return null;
    }

    if (type === 'email' || name.indexOf('email') !== -1) {
      if (!EMAIL_REGEX.test(val)) {
        return 'Укажите корректный адрес почты (например, name@example.com).';
      }
    }

    if (type === 'tel' || name.indexOf('phone') !== -1 || input.id === 'id_phone') {
      var digits = val.replace(/\D/g, '');
      if (digits.length < 10 || digits.length > 15 || !PHONE_REGEX.test(val)) {
        return 'Укажите корректный номер телефона (например, +7 999 123-45-67).';
      }
    }

    var minLen = input.getAttribute('minlength');
    if (minLen && val.length < parseInt(minLen, 10)) {
      return 'Минимальная длина: ' + minLen + ' симв. (введено: ' + val.length + ').';
    }

    if (name === 'username' && val.length < 3) {
      return 'Имя пользователя должно содержать не менее 3 символов.';
    }

    if (name === 'street' && val.length < 2) {
      return 'Укажите корректное название улицы (не менее 2 символов).';
    }

    if (type === 'number') {
      var num = parseFloat(val);
      var min = input.getAttribute('min');
      var max = input.getAttribute('max');
      if (isNaN(num)) {
        return 'Введите числовое значение.';
      }
      if (min !== null && num < parseFloat(min)) {
        return 'Значение не может быть меньше ' + min + '.';
      }
      if (max !== null && num > parseFloat(max)) {
        return 'Значение не может быть больше ' + max + '.';
      }
    }

    if (type === 'date' || name.indexOf('date') !== -1) {
      var parts = val.split('-');
      if (parts.length === 3) {
        var y = parseInt(parts[0], 10);
        var m = parseInt(parts[1], 10) - 1;
        var d = parseInt(parts[2], 10);
        var chosenDate = new Date(y, m, d);
        var today = new Date();
        today.setHours(0, 0, 0, 0);
        if (chosenDate < today) {
          return 'Нельзя выбрать прошедшую дату.';
        }
      }
    }

    if (type === 'file' && input.files && input.files.length > 0) {
      var file = input.files[0];
      var maxBytes = 2 * 1024 * 1024;
      if (file.size > maxBytes) {
        return 'Размер файла не должен превышать 2 МБ (выбран: ' + (file.size / 1024 / 1024).toFixed(1) + ' МБ).';
      }
      var ext = file.name.split('.').pop().toLowerCase();
      var allowed = ['jpg', 'jpeg', 'png', 'webp'];
      if (allowed.indexOf(ext) === -1) {
        return 'Допустимы только изображения форматов JPG, PNG или WebP.';
      }
    }

    return null;
  }

  function showError(input, message) {
    input.classList.add('is-invalid');
    input.setAttribute('aria-invalid', 'true');

    var parent = input.closest('.field') || input.closest('.wire-field') || input.closest('.wire-filter-group') || input.parentNode;
    var errorEl = parent.querySelector('.wire-client-error');

    if (!errorEl) {
      errorEl = document.createElement('div');
      errorEl.className = 'wire-client-error';
      errorEl.setAttribute('role', 'alert');
      if (input.nextSibling) {
        parent.insertBefore(errorEl, input.nextSibling);
      } else {
        parent.appendChild(errorEl);
      }
    }
    errorEl.textContent = message;
    errorEl.style.display = 'block';
  }

  function clearError(input) {
    input.classList.remove('is-invalid');
    input.removeAttribute('aria-invalid');

    var parent = input.closest('.field') || input.closest('.wire-field') || input.closest('.wire-filter-group') || input.parentNode;
    if (parent) {
      var errorEl = parent.querySelector('.wire-client-error');
      if (errorEl) {
        errorEl.textContent = '';
        errorEl.style.display = 'none';
      }
    }
  }

  function validateField(input) {
    var message = getErrorMessage(input);
    if (message) {
      showError(input, message);
      return false;
    } else {
      clearError(input);
      return true;
    }
  }

  function attachValidation(form) {
    if (form.dataset.validationAttached === 'true') {
      return;
    }
    form.dataset.validationAttached = 'true';

    var inputs = form.querySelectorAll('input, select, textarea');
    Array.prototype.forEach.call(inputs, function (input) {
      if (input.type === 'hidden' || input.type === 'submit' || input.type === 'button') {
        return;
      }
      input.addEventListener('input', function () {
        if (input.classList.contains('is-invalid')) {
          validateField(input);
        }
      });
      input.addEventListener('blur', function () {
        if (input.value || input.required) {
          validateField(input);
        }
      });
      input.addEventListener('change', function () {
        validateField(input);
      });
    });

    form.addEventListener('submit', function (e) {
      var isValid = true;
      var firstInvalidInput = null;

      Array.prototype.forEach.call(inputs, function (input) {
        if (input.type === 'hidden' || input.type === 'submit' || input.type === 'button') {
          return;
        }
        var fieldValid = validateField(input);
        if (!fieldValid) {
          isValid = false;
          if (!firstInvalidInput) {
            firstInvalidInput = input;
          }
        }
      });

      if (!isValid) {
        e.preventDefault();
        e.stopPropagation();
        if (firstInvalidInput) {
          firstInvalidInput.focus();
        }
      }
    });
  }

  function init() {
    var forms = document.querySelectorAll('form[method="post"], form.wire-validate');
    Array.prototype.forEach.call(forms, function (form) {
      if (form.classList.contains('inline-form') && form.action.indexOf('logout') !== -1) {
        return;
      }
      attachValidation(form);
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

  window.WireValidation = {
    validateForm: function (form) {
      var inputs = form.querySelectorAll('input, select, textarea');
      var allValid = true;
      Array.prototype.forEach.call(inputs, function (inp) {
        if (!validateField(inp)) allValid = false;
      });
      return allValid;
    },
    clearError: clearError,
    showError: showError
  };
})();
