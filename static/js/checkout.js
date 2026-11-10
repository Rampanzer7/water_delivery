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

  function loadSlots() {
    if (!addressSelect.value) {
      return;
    }
    var chosen = slotSelect.value;
    fetch(slotsUrl + '?address=' + encodeURIComponent(addressSelect.value))
      .then(function (response) { return response.json(); })
      .then(function (data) {
        slotSelect.innerHTML = '';
        data.slots.forEach(function (slot) {
          var option = document.createElement('option');
          option.value = slot.id;
          option.textContent = slot.label;
          option.selected = String(slot.id) === chosen;
          slotSelect.appendChild(option);
        });
      });
  }

  function showTotals(data) {
    document.getElementById('sum-goods').textContent = Number(data.goods).toLocaleString('ru-RU');
    document.getElementById('sum-deposit').textContent = Number(data.deposit).toLocaleString('ru-RU');
    document.getElementById('sum-total').textContent = Number(data.total).toLocaleString('ru-RU');
    document.getElementById('sum-bottles').textContent = data.bottles;
    document.getElementById('sum-missing').textContent = data.missing;
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
    fetch(url)
      .then(function (response) { return response.json(); })
      .then(showTotals);
  }

  addressSelect.addEventListener('change', loadSlots);
  returnedInput.addEventListener('input', loadTotals);
  loadSlots();
  loadTotals();
})();
