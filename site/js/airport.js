// 機場頁：路線圖與航班資訊看板風格的價目表，選了地區後底部出現預約列
(async () => {
  'use strict';
  const { $, $$, fmt, money, DIR, areasOf, lineMessageUrl, bookingUrl, capacityHtml, ready } = window.Huanyu;
  const data = await ready;
  if (!data) return;

  const airport = data.airports.find(a => a.id === document.body.dataset.airport);
  if (!airport) return;

  // 路線圖資料（失敗或沒有這個機場時，只顯示完整價目表）
  let routes = null;
  try {
    const res = await fetch('data/routes.json');
    if (res.ok) routes = (await res.json())[airport.id] || null;
  } catch (err) {
    console.warn('無法載入 data/routes.json', err);
  }

  const state = {
    vehicleId: data.vehicles[0].id,
    dir: 'send',
    areaName: null,
    view: routes ? 'map' : 'table',
  };

  const vehicle = () => data.vehicles.find(v => v.id === state.vehicleId);
  const areaByName = new Map(areasOf(airport).map(a => [a.name, a]));
  const selectedArea = () => areaByName.get(state.areaName);
  const priceOf = (area, dir) => area.prices[state.vehicleId][DIR[dir].index];

  function renderTabs() {
    $('#vehicle-tabs').innerHTML = data.vehicles.map(v => `
      <button type="button" data-vehicle="${v.id}" aria-pressed="${v.id === state.vehicleId}">
        ${v.name}${capacityHtml(v)}
      </button>`).join('');
  }

  function renderViews() {
    $$('#view-tabs [data-view]').forEach(b => {
      b.hidden = !routes;
      b.setAttribute('aria-pressed', String(b.dataset.view === state.view));
    });
    $('#view-tabs').hidden = !routes;
    $('#view-map').hidden = state.view !== 'map';
    $('#view-table').hidden = state.view !== 'table';
  }

  function renderMap() {
    if (!routes) return;
    const code = airport.id.toUpperCase();
    $('#route-grid').innerHTML = routes.lines.map(line => `
      <section class="route-line">
        <h3 class="route-name">${line.name}</h3>
        <ol class="route-stops">
          <li class="route-start" aria-hidden="true"><span>${code}</span></li>
          ${line.stops.map(st => {
            const area = areaByName.get(st.area);
            const on = st.area === state.areaName;
            return `
          <li>
            <button type="button" class="stop" data-area="${st.area}" aria-pressed="${on}">
              <span class="stop-name">${st.label}</span>
              <span class="stop-price">${fmt(priceOf(area, state.dir))}</span>
            </button>
          </li>`;
          }).join('')}
        </ol>
      </section>`).join('');
  }

  function renderBoard() {
    $('#board-caption').textContent = `${airport.name} ${vehicle().name} 接送價目表`;
    $('#board-body').innerHTML = airport.groups.map(g => `
      <tr class="group"><th scope="colgroup" colspan="3">${g.name}</th></tr>
      ${g.areas.map(a => `
        <tr class="${a.name === state.areaName ? 'is-selected' : ''}">
          <td><button type="button" class="row-pick" data-area="${a.name}" aria-pressed="${a.name === state.areaName}">${a.name}</button></td>
          <td class="num" data-label="送機">${fmt(priceOf(a, 'send'))}</td>
          <td class="num" data-label="接機">${fmt(priceOf(a, 'pickup'))}</td>
        </tr>`).join('')}
    `).join('');
  }

  function renderPremium() {
    const box = $('#premium');
    const p = airport.premium;
    box.hidden = !p;
    if (!p) return;
    $('#premium-title').textContent = p.name;
    $('#premium-caption').textContent = p.caption;
    $('#premium-body').innerHTML = p.rows.map(([name, price]) =>
      `<tr><td>${name}</td><td class="num">${fmt(price)}</td></tr>`).join('');
  }

  function renderNotes() {
    const notes = [...(data.notes || []), ...(airport.notes || [])];
    $('#notes').innerHTML = notes.map(n => `<li>${n}</li>`).join('');
  }

  function renderBar() {
    const area = selectedArea();
    $('#quote-bar').hidden = !area;
    document.body.classList.toggle('has-quote-bar', Boolean(area));
    $$('input[name="qbdir"], input[name="mapdir"]').forEach(r => { r.checked = r.value === state.dir; });
    if (!area) return;
    const price = priceOf(area, state.dir);
    $('#qb-area').textContent = area.name;
    $('#qb-vehicle').textContent = `${airport.name}，${vehicle().name}`;
    $('#qb-price').textContent = fmt(price);
    $('#qb-more').href = bookingUrl({ airportId: airport.id, dir: state.dir, vehicleId: state.vehicleId, areaName: area.name });
    $('#qb-line').href = lineMessageUrl([
      '您好，我想預約：',
      `服務：${DIR[state.dir].label}`,
      `機場：${airport.name}`,
      `地區：${area.name}`,
      `車型：${vehicle().name}`,
      `報價：${money(price)}`,
    ].join('\n'));
  }

  function renderAll() {
    renderTabs();
    renderViews();
    renderMap();
    renderBoard();
    renderBar();
  }

  const toggleArea = name => {
    state.areaName = state.areaName === name ? null : name;
    renderMap();
    renderBoard();
    renderBar();
  };

  $('#vehicle-tabs').addEventListener('click', e => {
    const b = e.target.closest('[data-vehicle]');
    if (!b) return;
    state.vehicleId = b.dataset.vehicle;
    renderAll();
  });

  $('#view-tabs').addEventListener('click', e => {
    const b = e.target.closest('[data-view]');
    if (!b) return;
    state.view = b.dataset.view;
    renderViews();
  });

  $('#route-grid').addEventListener('click', e => {
    const b = e.target.closest('[data-area]');
    if (b) toggleArea(b.dataset.area);
  });

  $('#board-body').addEventListener('click', e => {
    const b = e.target.closest('[data-area]');
    if (b) toggleArea(b.dataset.area);
  });

  // 路線圖上的方向切換與底部預約列的方向切換共用同一個狀態
  document.addEventListener('change', e => {
    if (e.target.name === 'qbdir' || e.target.name === 'mapdir') {
      state.dir = e.target.value;
      renderMap();
      renderBar();
    }
  });

  renderPremium();
  renderNotes();
  renderAll();
})();
