// 車隊頁：從 data/fleet.json 畫出每一款車
(async () => {
  'use strict';
  const { $, capacityHtml } = window.Huanyu;
  try {
    const res = await fetch('data/fleet.json');
    if (!res.ok) throw new Error(res.status);
    const fleet = await res.json();
    $('#fleet-grid').innerHTML = fleet.map(f => `
      <article class="fleet-item">
        <img src="${f.image}" alt="${f.model}" width="800" height="436" loading="lazy">
        <h3>${f.name}</h3>
        <p class="model">${f.model}</p>
        ${capacityHtml({ passengers: f.passengers, luggage: f.bags, seats: `最多 ${f.passengers} 人，行李 ${f.luggage}` })}
        ${f.use ? `<p class="use">${f.use}</p>` : ''}
      </article>`).join('');
  } catch (err) {
    console.error('無法載入 data/fleet.json', err);
    $('#fleet-error').hidden = false;
  }
})();
