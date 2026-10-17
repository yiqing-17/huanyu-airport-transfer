// 首頁：價格試算（登機證）與車型一覽
(async () => {
  'use strict';
  const { $, $$, fmt, money, DIR, areasOf, lineMessageUrl, bookingUrl, capacityHtml, reduceMotion, ready } = window.Huanyu;
  const data = await ready;
  if (!data) return;

  const state = { dir: 'send', airportId: data.airports[0].id, vehicleId: data.vehicles[0].id, areaName: null };
  let lastPrice = null;

  const airport = () => data.airports.find(a => a.id === state.airportId);
  const vehicle = () => data.vehicles.find(v => v.id === state.vehicleId);
  const currentArea = () => {
    const list = areasOf(airport());
    return list.find(a => a.name === state.areaName) || list[0];
  };
  const priceOf = area => area.prices[state.vehicleId][DIR[state.dir].index];

  function quoteLines() {
    const area = currentArea();
    return [
      `服務：${DIR[state.dir].label}`,
      `機場：${airport().name}`,
      `地區：${area.name}`,
      `車型：${vehicle().name}`,
      `報價：${money(priceOf(area))}`,
    ];
  }

  function renderVehicleChips() {
    $('#vehicle-chips').innerHTML = data.vehicles.map(v => `
      <label>
        <input type="radio" name="vehicle" value="${v.id}">
        <span>${v.image ? `<img src="${v.image}" alt="" loading="lazy">` : ''}${v.name}${capacityHtml(v)}</span>
      </label>`).join('');
  }

  function renderControls() {
    const airportSel = $('#airport');
    airportSel.innerHTML = data.airports.map(a => `<option value="${a.id}">${a.name}</option>`).join('');
    airportSel.value = state.airportId;

    const areaSel = $('#area');
    areaSel.innerHTML = airport().groups.map(g =>
      `<optgroup label="${g.name}">${g.areas.map(a =>
        `<option value="${a.name}">${a.name}</option>`).join('')}</optgroup>`).join('');
    areaSel.value = currentArea().name;
    state.areaName = areaSel.value;

    // 下拉選單放不下長地區名時，在下方顯示完整名稱
    const note = $('#area-full');
    note.textContent = state.areaName;
    note.hidden = state.areaName.length <= 12;

    $$('input[name="dir"]').forEach(r => { r.checked = r.value === state.dir; });
    $$('input[name="vehicle"]').forEach(r => { r.checked = r.value === state.vehicleId; });
  }

  function renderPrice() {
    const area = currentArea();
    const price = priceOf(area);
    const el = $('#price');
    el.textContent = fmt(price);
    if (lastPrice !== null && lastPrice !== price && !reduceMotion) {
      el.animate(
        [{ transform: 'translateY(35%)', opacity: 0 }, { transform: 'none', opacity: 1 }],
        { duration: 220, easing: 'ease-out' }
      );
    }
    lastPrice = price;
    $('#price-desc').textContent = `${DIR[state.dir].label}，${airport().name}，${vehicle().name}，${area.name}`;
    $('#quote-line').href = lineMessageUrl(['您好，我想預約：', ...quoteLines()].join('\n'));
    $('#quote-more').href = bookingUrl({ airportId: state.airportId, dir: state.dir, vehicleId: state.vehicleId, areaName: area.name });
  }

  function renderVehicleGrid() {
    $('#vehicle-grid').innerHTML = data.vehicles.map(v => `
      <article class="fleet-item">
        ${v.image ? `<img src="${v.image}" alt="${v.name}" width="800" height="436" loading="lazy">` : ''}
        <h3>${v.name}</h3>
        ${capacityHtml(v)}
      </article>`).join('');
  }

  function render() {
    renderControls();
    renderPrice();
  }

  $('#estimator').addEventListener('change', e => {
    const t = e.target;
    if (t.name === 'dir') state.dir = t.value;
    if (t.id === 'airport') { state.airportId = t.value; state.areaName = null; }
    if (t.id === 'area') state.areaName = t.value;
    if (t.name === 'vehicle') state.vehicleId = t.value;
    render();
  });
  $('#estimator').addEventListener('submit', e => e.preventDefault());

  renderVehicleChips();
  renderVehicleGrid();
  render();
})();
