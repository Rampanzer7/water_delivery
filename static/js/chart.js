(function () {
  function readJson(id) {
    var element = document.getElementById(id);
    return element ? JSON.parse(element.textContent) : [];
  }

  function drawBars(canvas, labels, values) {
    var width = canvas.parentNode.clientWidth;
    var height = canvas.height;
    canvas.width = width;
    var ctx = canvas.getContext('2d');
    ctx.clearRect(0, 0, width, height);

    if (!values.length) {
      ctx.fillStyle = '#6b7a88';
      ctx.font = '16px sans-serif';
      ctx.fillText('Пока нет данных', 20, 40);
      return;
    }

    var left = 36;
    var bottom = 48;
    var top = 16;
    var maxValue = Math.max.apply(null, values);
    var plotHeight = height - top - bottom;
    var slot = (width - left - 10) / values.length;
    var barWidth = Math.min(slot * 0.6, 56);

    ctx.strokeStyle = '#cfd8e0';
    ctx.fillStyle = '#6b7a88';
    ctx.font = '12px sans-serif';
    ctx.textAlign = 'right';
    for (var step = 0; step <= 4; step++) {
      var y = top + plotHeight - (plotHeight * step) / 4;
      ctx.beginPath();
      ctx.moveTo(left, y);
      ctx.lineTo(width - 6, y);
      ctx.stroke();
      ctx.fillText(Math.round((maxValue * step) / 4), left - 6, y + 4);
    }

    ctx.textAlign = 'center';
    values.forEach(function (value, index) {
      var barHeight = (value / maxValue) * plotHeight;
      var x = left + slot * index + (slot - barWidth) / 2;
      var y = top + plotHeight - barHeight;
      ctx.fillStyle = '#1e88c9';
      ctx.fillRect(x, y, barWidth, barHeight);
      ctx.fillStyle = '#1f2d3a';
      ctx.fillText(value, x + barWidth / 2, y - 4);
      ctx.fillStyle = '#6b7a88';
      var label = labels[index];
      if (label.length > 11 && slot < 90) {
        label = label.slice(0, 10) + '…';
      }
      ctx.fillText(label, x + barWidth / 2, height - bottom + 18);
    });
  }

  function render() {
    drawBars(document.getElementById('chart-days'), readJson('day-labels'), readJson('day-values'));
    drawBars(document.getElementById('chart-districts'), readJson('district-labels'), readJson('district-values'));
  }

  render();
  window.addEventListener('resize', render);
})();
