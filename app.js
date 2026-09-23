'use strict';

const BUDGET = 20;
// Сколько игроков каждой позиции попадает в пул (на двоих)
const POOL_SIZE = { GK: 2, DEF: 4, MID: 2, FWD: 2 };
// Состав каждой команды — ровно половина пула
const SQUAD = { GK: 1, DEF: 2, MID: 1, FWD: 1 };
const POS_NAME = { GK: 'Вратарь', DEF: 'Защитник', MID: 'Полузащитник', FWD: 'Нападающий' };
const POS_SHORT = { GK: 'ВРТ', DEF: 'ЗАЩ', MID: 'ПЗ', FWD: 'НАП' };
const POS_ORDER = ['GK', 'DEF', 'MID', 'FWD'];
// Режимы: минимальный рейтинг игроков в пуле
const MODES = [
  { min: 85, label: '85+', hint: 'только звёзды' },
  { min: 80, label: '80+', hint: 'сильные' },
  { min: 75, label: '75+', hint: 'крепкие' },
  { min: 0, label: 'Все', hint: 'вся база' },
];

const $ = (id) => document.getElementById(id);

let database = [];
let game = null;
let mode = MODES[1];

// ---------- утилиты ----------

function shuffle(arr) {
  const a = arr.slice();
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

function initials(name) {
  return name.split(/\s+/).map((w) => w[0]).slice(0, 2).join('').toUpperCase();
}

// Круг с фото; если фото нет или не загрузилось — инициалы
function avatar(p, cls = '') {
  const ini = initials(p.name);
  if (!p.photo) return `<span class="avatar ${cls}">${ini}</span>`;
  return `<span class="avatar ${cls}"><img src="${escapeHtml(p.photo)}" alt="" loading="lazy"
    onerror="this.parentNode.textContent='${ini}'"></span>`;
}

const other = (i) => 1 - i;

// ---------- логика команды ----------

const SQUAD_SIZE = POS_ORDER.reduce((s, p) => s + SQUAD[p], 0);

function slotsLeft(team) {
  return SQUAD_SIZE - team.players.length;
}

function needs(team, pos) {
  return team.players.filter((p) => p.position === pos).length < SQUAD[pos];
}

// Максимальная ставка: нужно оставить хотя бы по $1 на каждое оставшееся место
function maxBid(team) {
  return team.money - (slotsLeft(team) - 1);
}

// ---------- ход игры ----------

function newGame() {
  const names = [$('name1').value.trim() || 'Игрок 1', $('name2').value.trim() || 'Игрок 2'];

  let pool = [];
  for (const pos of POS_ORDER) {
    const candidates = shuffle(database.filter((p) => p.position === pos && p.rating >= mode.min));
    pool.push(...candidates.slice(0, POOL_SIZE[pos]));
  }
  pool = shuffle(pool).map((p, i) => ({ ...p, id: i, soldTo: null, price: null }));

  game = {
    teams: names.map((name) => ({ name, money: BUDGET, players: [] })),
    pool,
    lotNumber: 0,
    opener: Math.random() < 0.5 ? 0 : 1, // кто открывает торги в первом лоте
    lot: null,
  };

  show('screen-game');
  nextLot();
}

function nextLot() {
  const remaining = game.pool.filter((p) => p.soldTo === null);
  if (remaining.length === 0) return endGame();

  const player = remaining[Math.floor(Math.random() * remaining.length)];
  game.lotNumber++;
  const opener = game.lotNumber === 1 ? game.opener : other(game.lot.opener);

  game.lot = { player, opener, bid: 0, leader: null, turn: opener, amount: 1, log: [] };

  $('result').classList.add('hidden');
  $('bid-box').classList.remove('hidden');

  // Если одной команде эта позиция уже не нужна — футболист уходит другой за $1
  const canTake = [0, 1].map((i) => needs(game.teams[i], player.position));
  if (!canTake[0] || !canTake[1]) {
    const winner = canTake[0] ? 0 : 1;
    const loser = other(winner);
    game.lot.log.push(`${game.teams[loser].name}: позиция «${POS_NAME[player.position]}» уже закрыта`);
    render();
    return sell(winner, 1, true);
  }

  render();
}

function placeBid() {
  const lot = game.lot;
  const team = game.teams[lot.turn];
  const amount = lot.amount;
  if (amount <= lot.bid || amount > maxBid(team)) return;

  lot.bid = amount;
  lot.leader = lot.turn;
  lot.log.push(`${team.name} ставит $${amount}`);

  const rival = other(lot.turn);
  // Если сопернику нечем перебить — лот уходит сразу
  if (maxBid(game.teams[rival]) <= lot.bid) {
    lot.log.push(`${game.teams[rival].name} не может перебить ставку`);
    return sell(lot.turn, lot.bid);
  }

  lot.turn = rival;
  lot.amount = lot.bid + 1;
  render();
}

function pass() {
  const lot = game.lot;
  if (lot.leader === null) return; // открывающий обязан поставить
  lot.log.push(`${game.teams[lot.turn].name} пасует`);
  sell(lot.leader, lot.bid);
}

function sell(teamIndex, price, auto = false) {
  const lot = game.lot;
  const team = game.teams[teamIndex];
  const player = lot.player;

  player.soldTo = teamIndex;
  player.price = price;
  team.money -= price;
  team.players.push(player);
  lot.turn = null;

  $('bid-box').classList.add('hidden');
  $('result').classList.remove('hidden');
  $('result-text').innerHTML =
    `<strong>${escapeHtml(player.name)}</strong> уходит в команду ` +
    `<span class="p${teamIndex}">${escapeHtml(team.name)}</span> за <strong>$${price}</strong>` +
    (auto ? ' (автоматически)' : '');
  const last = game.pool.every((p) => p.soldTo !== null);
  $('btn-next').textContent = last ? 'К итогам →' : 'Следующий лот →';

  render();
}

function endGame() {
  const scores = game.teams.map((t) => t.players.reduce((s, p) => s + p.rating, 0));
  let title;
  if (scores[0] === scores[1]) title = 'Ничья по рейтингу!';
  else {
    const w = scores[0] > scores[1] ? 0 : 1;
    title = `Сильнее состав у <span class="p${w}">${escapeHtml(game.teams[w].name)}</span>`;
  }
  $('end-title').innerHTML = title;

  $('final-teams').innerHTML = game.teams.map((t, i) => `
    <div class="final p${i}-border">
      <h3 class="p${i}">${escapeHtml(t.name)}</h3>
      <p class="muted">Рейтинг состава: <strong>${scores[i]}</strong> · Осталось: <strong>$${t.money}</strong></p>
      <div class="formation">
        ${['FWD', 'MID', 'DEF', 'GK'].map((pos) => `
          <div class="line">
            ${t.players.filter((p) => p.position === pos).map((p) => `
              <div class="chip">
                ${avatar(p)}
                <span class="chip-name">${escapeHtml(p.name)}</span>
                <span class="muted small">${p.rating} · $${p.price}</span>
              </div>`).join('')}
          </div>`).join('')}
      </div>
    </div>`).join('');

  show('screen-end');
}

// ---------- отрисовка ----------

function show(id) {
  for (const s of document.querySelectorAll('.screen')) s.classList.toggle('hidden', s.id !== id);
}

function render() {
  const lot = game.lot;
  const p = lot.player;

  $('lot-info').textContent = `Лот ${game.lotNumber} из ${game.pool.length}`;
  $('card').innerHTML = `
    <div class="pos pos-${p.position}">${POS_NAME[p.position]}</div>
    ${avatar(p, 'big')}
    <div class="name">${escapeHtml(p.name)}</div>
    <div class="meta">${escapeHtml(p.club)} · ${escapeHtml(p.country)}</div>
    <div class="rating">${p.rating}</div>`;

  $('current-bid').textContent = lot.bid ? `$${lot.bid}` : '—';
  $('current-leader').innerHTML = lot.leader !== null
    ? `у <span class="p${lot.leader}">${escapeHtml(game.teams[lot.leader].name)}</span>` : '';

  if (lot.turn !== null) {
    const team = game.teams[lot.turn];
    $('turn').innerHTML = `Ход: <span class="p${lot.turn}">${escapeHtml(team.name)}</span>` +
      ` <span class="muted">(макс. ставка $${maxBid(team)})</span>`;
    $('bid-amount').textContent = `$${lot.amount}`;
    $('btn-bid').textContent = lot.leader === null ? `Открыть за $${lot.amount}` : `Поднять до $${lot.amount}`;
    $('btn-bid').className = `btn primary bg${lot.turn}`;
    $('btn-pass').classList.toggle('hidden', lot.leader === null);
    $('btn-pass').textContent = lot.leader === null ? '' : `Пас — отдать за $${lot.bid}`;
  }

  $('log').innerHTML = lot.log.map((l) => `<li>${escapeHtml(l)}</li>`).join('');

  game.teams.forEach((t, i) => renderTeam(t, i));
}

function renderTeam(team, i) {
  const active = game.lot && game.lot.turn === i;
  const slots = [];
  for (const pos of POS_ORDER) {
    const have = team.players.filter((p) => p.position === pos);
    for (let k = 0; k < SQUAD[pos]; k++) {
      const pl = have[k];
      slots.push(pl
        ? `<li class="slot filled"><span class="tag pos-${pos}">${POS_SHORT[pos]}</span>
             <span class="slot-name">${escapeHtml(pl.name)}</span><span class="price">$${pl.price}</span></li>`
        : `<li class="slot"><span class="tag pos-${pos}">${POS_SHORT[pos]}</span><span class="muted">пусто</span></li>`);
    }
  }
  $(`team-${i}`).className = `team p${i}-border${active ? ' active' : ''}`;
  $(`team-${i}`).innerHTML = `
    <h2 class="p${i}">${escapeHtml(team.name)}</h2>
    <div class="money">$${team.money}</div>
    <ul class="slots">${slots.join('')}</ul>`;
}

// ---------- события ----------

for (const b of document.querySelectorAll('.step')) {
  b.addEventListener('click', () => {
    const lot = game.lot;
    if (lot.turn === null) return;
    const max = maxBid(game.teams[lot.turn]);
    const min = lot.bid + 1;
    lot.amount = Math.min(max, Math.max(min, lot.amount + Number(b.dataset.step)));
    render();
  });
}

$('btn-play').addEventListener('click', newGame);
$('btn-bid').addEventListener('click', placeBid);
$('btn-pass').addEventListener('click', pass);
$('btn-next').addEventListener('click', nextLot);
$('btn-again').addEventListener('click', () => show('screen-setup'));

function renderModes() {
  $('modes').innerHTML = MODES.map((m, i) => {
    const count = database.filter((p) => p.rating >= m.min).length;
    return `<button class="mode${m === mode ? ' selected' : ''}" data-i="${i}">
      <strong>${m.label}</strong><span>${m.hint}</span><span class="muted small">${count} игроков</span>
    </button>`;
  }).join('');
}

$('modes').addEventListener('click', (e) => {
  const b = e.target.closest('.mode');
  if (!b) return;
  mode = MODES[Number(b.dataset.i)];
  try { localStorage.setItem('mode', mode.label); } catch (_) {}
  renderModes();
});

// ---------- загрузка базы ----------

fetch('data/players.json')
  .then((r) => {
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    return r.json();
  })
  .then((data) => {
    database = data;
    for (const m of MODES) {
      for (const pos of POS_ORDER) {
        if (data.filter((p) => p.position === pos && p.rating >= m.min).length < POOL_SIZE[pos]) {
          throw new Error(`в режиме ${m.label} мало игроков позиции ${pos}`);
        }
      }
    }
    try { mode = MODES.find((m) => m.label === localStorage.getItem('mode')) || mode; } catch (_) {}
    renderModes();
    $('btn-play').disabled = false;
    $('btn-play').textContent = 'Играть';
  })
  .catch((e) => {
    $('btn-play').textContent = 'Ошибка';
    $('load-error').classList.remove('hidden');
    $('load-error').textContent =
      `Не удалось загрузить data/players.json (${e.message}). ` +
      'Если открываете файл напрямую, запустите локальный сервер: python -m http.server';
  });
