// 所有頁面共用：店家資料、價目資料載入、小工具。
// 各頁面的程式（home.js、airport.js）從 window.Huanyu 取用。
(() => {
  'use strict';

  const SITE = window.SITE || {};
  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];
  const reduceMotion = matchMedia('(prefers-reduced-motion: reduce)').matches;
  const fmt = n => n.toLocaleString('en-US');
  const money = n => `NT$ ${fmt(n)}`;

  // 送機 / 接機：價格在 prices.json 裡是 [送機, 接機]
  const DIR = {
    send:   { label: '送機', index: 0 },
    pickup: { label: '接機', index: 1 },
  };

  const areasOf = airport => airport.groups.flatMap(g => g.areas);
  const minPrice = airport =>
    Math.min(...areasOf(airport).flatMap(a => Object.values(a.prices).flat()));
  const toIntl = n => {
    const d = (n || '').replace(/\D/g, '');
    return d.startsWith('0') ? '886' + d.slice(1) : d;
  };

  /* 座位與行李圖示：人數、行李數用小圖示重複畫出來，旁邊附上給讀屏軟體的文字 */
  const ICON_PERSON = '<svg class="cap-icon" viewBox="0 0 16 16" aria-hidden="true" focusable="false"><circle cx="8" cy="4.5" r="2.7"/><path d="M2.5 14.5c0-3.2 2.4-5.2 5.5-5.2s5.5 2 5.5 5.2z"/></svg>';
  const ICON_BAG = '<svg class="cap-icon" viewBox="0 0 16 16" aria-hidden="true" focusable="false"><rect x="2.5" y="5" width="11" height="9" rx="1.6"/><path d="M5.5 5V3.6c0-.8.6-1.4 1.4-1.4h2.2c.8 0 1.4.6 1.4 1.4V5" fill="none" stroke="currentColor" stroke-width="1.3"/></svg>';
  const capacityHtml = v => `
    <span class="cap">
      <span class="cap-row">${ICON_PERSON.repeat(v.passengers)}</span>
      <span class="cap-row cap-bags">${ICON_BAG.repeat(v.luggage)}</span>
      <span class="sr">${v.seats}</span>
    </span>`;

  /* 台灣時間的深夜與凌晨：天空變深，並提醒「一樣接受預約」 */
  function applyNight() {
    let hour;
    try {
      hour = Number(new Intl.DateTimeFormat('en-GB',
        { timeZone: 'Asia/Taipei', hour: '2-digit', hourCycle: 'h23' }).format(new Date()));
    } catch (err) { return; }
    if (Number.isNaN(hour)) return;
    const night = hour >= 22 || hour < 6;
    document.documentElement.classList.toggle('is-night', night);
    const note = $('#night-note');
    if (note) {
      note.hidden = !night;
      note.textContent = hour >= 22 ? '現在是深夜，一樣 24 小時接受預約。' : '現在是凌晨，一樣 24 小時接受預約。';
    }
  }

  /* 店家資料（來自 js/config.js）填進頁面 */
  function applySiteInfo() {
    const links = {
      phone: `tel:+${toIntl(SITE.phone)}`,
      ownerPhone: `tel:+${toIntl(SITE.ownerPhone)}`,
      line: `https://line.me/R/ti/p/${encodeURIComponent(SITE.lineId || '')}`,
      whatsapp: `https://wa.me/${toIntl(SITE.phone)}`,
      map: `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(SITE.address || '')}`,
    };
    $$('[data-text]').forEach(el => {
      const value = SITE[el.dataset.text];
      if (value) el.textContent = value;
    });
    $$('[data-link]').forEach(el => { el.href = links[el.dataset.link] || '#'; });
    if (SITE.showWhatsapp === false) $$('[data-whatsapp]').forEach(el => { el.hidden = true; });
  }

  // 連到預約頁，並帶著目前選好的行程（預約頁會讀取這些參數）
  const bookingUrl = ({ airportId, dir, vehicleId, areaName }) =>
    'booking.html?' + new URLSearchParams({ airport: airportId, dir, vehicle: vehicleId, area: areaName }).toString();

  // 官方 LINE 的「帶入預約內容」連結
  const lineMessageUrl = text =>
    `https://line.me/R/oaMessage/${encodeURIComponent(SITE.lineId || '')}/?${encodeURIComponent(text)}`;

  // 載入價目資料；失敗時顯示頁面上的錯誤提示
  const ready = fetch('data/prices.json')
    .then(res => { if (!res.ok) throw new Error(res.status); return res.json(); })
    .then(data => {
      $$('[data-min-airport]').forEach(el => {
        const a = data.airports.find(x => x.id === el.dataset.minAirport);
        if (a) el.textContent = fmt(minPrice(a));
      });
      return data;
    })
    .catch(err => {
      console.error('無法載入 data/prices.json', err);
      $$('.js-error').forEach(el => { el.hidden = false; });
      return null;
    });

  applySiteInfo();
  applyNight();
  window.Huanyu = { SITE, $, $$, fmt, money, DIR, areasOf, minPrice, lineMessageUrl, bookingUrl, capacityHtml, reduceMotion, ready };
})();
