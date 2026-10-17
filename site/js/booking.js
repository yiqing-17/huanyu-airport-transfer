// 預約頁：選行程、填乘客資料，組成預約訊息後用 LINE 傳出
// 可以從機場頁、首頁帶參數進來：booking.html?airport=tpe&dir=send&vehicle=sedan&area=...
(async () => {
  'use strict';
  const { $, $$, fmt, money, DIR, areasOf, lineMessageUrl, capacityHtml, reduceMotion, ready } = window.Huanyu;
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

  // 讀取網址參數；不合法的值一律忽略
  (() => {
    const q = new URLSearchParams(location.search);
    if (DIR[q.get('dir')]) state.dir = q.get('dir');
    const ap = data.airports.find(a => a.id === q.get('airport'));
    if (ap) state.airportId = ap.id;
    const v = data.vehicles.find(x => x.id === q.get('vehicle'));
    if (v) state.vehicleId = v.id;
    const name = q.get('area');
    if (name && areasOf(airport()).some(a => a.name === name)) state.areaName = name;
  })();

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

  const LABELS = {
    send:   { time: '上車時間',     address: '上車地址', flight: '起飛航班（選填）' },
    pickup: { time: '航班抵達時間', address: '下車地址', flight: '抵達航班（選填）' },
  };

  function buildMessage(orderNo) {
    const l = LABELS[state.dir];
    const v = id => ($(id).value || '').trim();
    const rows = [
      ['姓名', v('#f-name')],
      ['電話', v('#f-phone')],
      ['日期', v('#f-date')],
      [l.time, v('#f-time')],
      [l.address, v('#f-address')],
      [l.flight.replace('（選填）', ''), v('#f-flight')],
      ['人數', v('#f-pax')],
      ['行李數', v('#f-bags')],
      ['備註', v('#f-note')],
    ];
    const lines = [`【${window.SITE.brand || ''} 預約】`];
    if (orderNo) lines.push(`訂單編號：${orderNo}`);
    lines.push(...quoteLines());
    rows.forEach(([name, value]) => { if (value) lines.push(`${name}：${value}`); });
    return lines.join('\n');
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
  }

  function renderForm() {
    const l = LABELS[state.dir];
    $('#l-time').textContent = l.time;
    $('#l-address').textContent = l.address;
    $('#l-flight').textContent = l.flight;
    $('#preview').value = buildMessage();
  }

  function render() {
    renderControls();
    renderPrice();
    renderForm();
  }

  $('#trip').addEventListener('change', e => {
    const t = e.target;
    if (t.name === 'dir') state.dir = t.value;
    if (t.id === 'airport') { state.airportId = t.value; state.areaName = null; }
    if (t.id === 'area') state.areaName = t.value;
    if (t.name === 'vehicle') state.vehicleId = t.value;
    render();
  });
  $('#trip').addEventListener('submit', e => e.preventDefault());

  const form = $('#booking-form');
  form.addEventListener('input', () => { $('#preview').value = buildMessage(); });
  function setStatus(text) {
    const status = $('#copy-status');
    status.textContent = text;
    if (text) setTimeout(() => { if (status.textContent === text) status.textContent = ''; }, 8000);
  }

  // 把預約存到後台（只有這個網站有後端時才會成功）。
  // 失敗、逾時、沒有後端，都不影響預約：照常用 LINE 傳給客服。
  async function recordBooking() {
    const v = id => ($(id).value || '').trim();
    const payload = {
      dir: state.dir, airport: state.airportId, vehicle: state.vehicleId, area: currentArea().name,
      name: v('#f-name'), phone: v('#f-phone'), date: v('#f-date'), time: v('#f-time'),
      address: v('#f-address'), flight: v('#f-flight'), passengers: v('#f-pax'),
      luggage: v('#f-bags'), note: v('#f-note'),
    };
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 4000);
    try {
      const res = await fetch('/api/bookings', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload), signal: controller.signal,
      });
      const body = await res.json().catch(() => null);
      if (res.ok && body && body.ok) return { orderNo: body.order_no };
      if (res.status === 400 && body && body.message) {
        return { error: (body.errors || [body.message]).join('；') };   // 資料有問題：請客人修正
      }
      return {};
    } catch (err) {
      return {};
    } finally {
      clearTimeout(timer);
    }
  }

  form.addEventListener('submit', async e => {
    e.preventDefault(); // 只有通過必填檢查才會進到這裡
    const button = form.querySelector('button[type="submit"]');
    button.disabled = true;
    // 先同步開一個空白分頁，等存檔完成再導向 LINE，才不會被瀏覽器當成彈出視窗擋掉
    const tab = window.open('', '_blank');
    const result = await recordBooking();
    button.disabled = false;
    if (result.error) {
      if (tab) tab.close();
      setStatus(result.error);
      return;
    }
    const url = lineMessageUrl(buildMessage(result.orderNo));
    if (tab) { tab.opener = null; tab.location.href = url; } else { window.location.href = url; }
    setStatus(result.orderNo ? `已建立訂單 ${result.orderNo}，請在 LINE 傳送預約內容給客服。` : '');
  });

  $('#copy-btn').addEventListener('click', async () => {
    const text = $('#preview').value;
    const status = $('#copy-status');
    try {
      await navigator.clipboard.writeText(text);
      status.textContent = '已複製預約內容';
    } catch {
      $('#preview').select();
      status.textContent = document.execCommand('copy') ? '已複製預約內容' : '複製失敗，請手動選取文字';
    }
    setTimeout(() => { status.textContent = ''; }, 3000);
  });

  // 日期不能選過去
  $('#f-date').min = new Date().toLocaleDateString('sv-SE');

  renderVehicleChips();
  render();
})();
