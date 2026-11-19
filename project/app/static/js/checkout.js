(function () {
  var form = document.getElementById('order-form');
  if (!form) {
    return;
  }

  var addressSelect = document.getElementById('id_address');
  var slotSelect = document.getElementById('id_slot');
  var returnedInput = document.getElementById('id_returned_bottles');
  var slotsUrl = form.dataset.slotsUrl;
  var calcUrl = form.dataset.calcUrl;
  var orderId = form.dataset.order;

  var totalBox = document.querySelector('.checkout-totals') || document.querySelector('.wire-checkout-totals');

  function setLoading(element, isLoading, text) {
    if (!element) return;
    if (isLoading) {
      element.classList.add('wire-is-loading');
      if (text) {
        element.setAttribute('data-prev-text', element.textContent);
        element.textContent = text;
      }
    } else {
      element.classList.remove('wire-is-loading');
      var prev = element.getAttribute('data-prev-text');
      if (prev) {
        element.removeAttribute('data-prev-text');
      }
    }
  }

  function loadSlots() {
    if (!addressSelect.value) {
      return;
    }
    var chosen = slotSelect.value;
    slotSelect.disabled = true;
    slotSelect.innerHTML = '<option value="">Загрузка доступных интервалов...</option>';

    fetch(slotsUrl + '?address=' + encodeURIComponent(addressSelect.value))
      .then(function (response) { return response.json(); })
      .then(function (data) {
        slotSelect.innerHTML = '';
        if (!data.slots || data.slots.length === 0) {
          var emptyOption = document.createElement('option');
          emptyOption.value = '';
          emptyOption.textContent = 'Нет доступных интервалов для этого адреса';
          slotSelect.appendChild(emptyOption);
        } else {
          data.slots.forEach(function (slot) {
            var option = document.createElement('option');
            option.value = slot.id;
            option.textContent = slot.label;
            option.selected = String(slot.id) === chosen;
            slotSelect.appendChild(option);
          });
        }
      })
      .catch(function () {
        slotSelect.innerHTML = '<option value="">Ошибка загрузки интервалов</option>';
      })
      .finally(function () {
        slotSelect.disabled = false;
      });
  }

  function showTotals(data) {
    var sumGoods = document.getElementById('sum-goods');
    var sumDeposit = document.getElementById('sum-deposit');
    var sumTotal = document.getElementById('sum-total');
    var sumTotalMobile = document.getElementById('sum-total-mobile');
    var sumBottles = document.getElementById('sum-bottles');
    var sumMissing = document.getElementById('sum-missing');

    if (sumGoods) sumGoods.textContent = Number(data.goods).toLocaleString('ru-RU');
    if (sumDeposit) sumDeposit.textContent = Number(data.deposit).toLocaleString('ru-RU');
    if (sumTotal) sumTotal.textContent = Number(data.total).toLocaleString('ru-RU');
    if (sumTotalMobile) sumTotalMobile.textContent = Number(data.total).toLocaleString('ru-RU');
    if (sumBottles) sumBottles.textContent = data.bottles;
    if (sumMissing) sumMissing.textContent = data.missing;
  }

  function loadTotals() {
    var returned = parseInt(returnedInput.value, 10);
    if (isNaN(returned) || returned < 0) {
      returned = 0;
    }
    var url = calcUrl + '?returned=' + returned;
    if (orderId) {
      url += '&order=' + encodeURIComponent(orderId);
    }

    var sumTotal = document.getElementById('sum-total');
    var sumTotalMobile = document.getElementById('sum-total-mobile');
    setLoading(sumTotal, true, '...');
    if (sumTotalMobile) setLoading(sumTotalMobile, true, '...');
    if (totalBox) totalBox.classList.add('wire-calc-loading');

    fetch(url)
      .then(function (response) { return response.json(); })
      .then(showTotals)
      .finally(function () {
        setLoading(sumTotal, false);
        if (sumTotalMobile) setLoading(sumTotalMobile, false);
        if (totalBox) totalBox.classList.remove('wire-calc-loading');
      });
  }

  addressSelect.addEventListener('change', loadSlots);
  returnedInput.addEventListener('input', loadTotals);
  loadSlots();
  loadTotals();
})();

