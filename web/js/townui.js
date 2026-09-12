/* Python Coding Gauntlet Legend — THE TOWN SQUARE.
 *
 * The loop the player comes back to, and the one screen in this game where
 * nothing is trying to kill you. Five people stand on it:
 *
 *   MARGIT ORR    the Mender. Health, afflictions and a fainted companion, all
 *                 FREE, and she says so before she is asked.
 *   FERRO         the smith. Armour integrity, priced per point, cheapest-first
 *                 when you cannot pay for all of it.
 *   THE VENDOR    seventeen of them, one per region, each with its own shelf,
 *                 its own prices and its own restock clock.
 *   ORIN TALLOW   the assayer. One trial open at a time, quoted before the work.
 *   EVERYBODY ELSE  forty-seven voices, who read the area, your gear and what is
 *                 coming, and who are drawn IDENTITY FIRST — a screen that draws
 *                 only the advice has built a kiosk out of a town.
 *
 * WHY HEALTH IS FREE, said once here because it is the whole shape of the
 * screen: health gates ATTEMPTS. Charging for attempts steepens the learning
 * curve exactly where it should flatten, so gold goes to the smith instead and
 * the Mender takes none of it. upkeep.py's own `free_because` is rendered
 * verbatim rather than paraphrased.
 *
 * NOTHING HERE DECIDES ANYTHING. Every price, every refusal, every sentence is
 * the server's. Where this file looks like it is computing something it is
 * formatting: a percentage of an income the server measured, a bar width off two
 * numbers it sent. A second opinion about whether you can afford a pauldron is
 * how a shop ends up disagreeing with the save file.
 */
import { api } from './api.js';
import * as sprites from './sprites.js';
import {
  $, el, esc, lines, num, card, prose, meter, makeDisposer, faceFor,
  HOST, refusal, isSealed, sealedTitle, refusalCard,
} from './uikit.js';

export const TOWN_UI_VERSION = '1.0.0';

const D = makeDisposer();
export const leave = D.leave;

/* Which counter the player is standing at. Kept across repaints so mending a
 * greave does not throw them back to the Mender. */
let TAB = 'mender';
/* The last full reading of the square. Every counter is drawn from one call, so
 * the loop report on the header and the smith's quote below it cannot disagree
 * about how much gold is in the purse. */
let TOWN = null;
/* The alarm band the player was last TOLD about. upkeep.py asks for a latch:
 * speak on a transition downward and never every frame. */
let SAID_BAND = '';

const TABS = [
  { id: 'mender', label: 'THE MENDER', blurb: 'Health, afflictions, and a companion back on its feet. Free.' },
  { id: 'smith', label: 'FERRO', blurb: 'Armour integrity, priced by the point.' },
  { id: 'shelf', label: 'THE SHELF', blurb: 'What this region’s vendor is carrying today.' },
  { id: 'broker', label: 'ORIN TALLOW', blurb: 'One trial, quoted before the work.' },
  { id: 'voices', label: 'THE VOICES', blurb: 'Who is standing here, and what they have noticed.' },
];

/* ------------------------------------------------------------------ paint */

export async function paintTown(tab) {
  D.leave();
  if (tab) TAB = tab;
  HOST.panel('THE TOWN SQUARE', `
    <p class="small muted">The Mender charges nothing and will tell you why.
    Everything else here costs gold, and the gold comes from graded Python.</p>
    <div id="town-head"></div>
    <div id="town-tabs" class="row" style="flex-wrap:wrap;margin:12px 0"></div>
    <div id="town-body"></div>`);

  const head = $('#town-head');
  head.innerHTML = '<p class="small muted">Crossing the square…</p>';
  let view;
  try {
    view = await api.town();
  } catch (e) {
    head.innerHTML = refusalCard({ error: e.message }, { title: 'THE SQUARE IS EMPTY' });
    return;
  }
  if (!head.isConnected) return;
  if (view && view.error) { head.innerHTML = refusalCard(view); return; }
  TOWN = view;
  /* WALKING IN IS THE VISIT. `Game.town()` runs `upkeep.town_visit`, which
   * heals for free and resets the since-town counters — that is not a side
   * effect to be hidden, it is what arriving in town means. So it is said out
   * loud, once, with the number beside it, rather than letting the player
   * discover their bar refilled and wonder what did it. */
  const arrival = (view.visit || {}).healer || {};
  if (arrival.did_something) {
    HOST.sfx('unlock');
    HOST.toast('SHE HAD YOU SAT DOWN BEFORE YOU ASKED',
      `+${num(arrival.restored)} health${
        (arrival.cured_names || []).length
          ? `, ${arrival.cured_names.join(' and ')} lifted` : ''}${
        (arrival.revived || []).length
          ? `, ${arrival.revived.join(' and ')} back on its feet` : ''}
       — ${num(arrival.gold_cost)} gold.`, 'green');
  }

  paintHead();
  paintTabs();
  await paintBody();
}

/* The header: the purse, the alarm band, and the one sentence upkeep.py writes
 * about whether this loop is affordable. All three are visible from every
 * counter, because they are what the player is deciding between. */
function paintHead() {
  const head = $('#town-head');
  if (!head) return;
  const t = TOWN || {};
  const alarm = t.alarm || {};
  const loop = t.loop || {};
  const cond = t.condition || {};
  /* Two readings and they are not the same thing. `share_of_income_actual` is
   * measured from what this save has ACTUALLY earned and is null until there is
   * enough of it; `share_of_income` is the model's own figure. Preferring the
   * measurement and falling back to the model is right — printing a zero
   * because the measurement has not happened yet is not. */
  const measured = loop.share_of_income_actual !== null
    && loop.share_of_income_actual !== undefined;
  const share = measured ? num(loop.share_of_income_actual) : num(loop.share_of_income);
  head.innerHTML = `
    <div class="frame" style="padding:14px;display:flex;gap:18px;flex-wrap:wrap;
         align-items:flex-start;border-left:4px solid ${esc(alarm.colour || 'var(--line-hi)')}">
      <div style="flex:0 0 120px">
        <div class="section-title" style="margin:0 0 6px">PURSE</div>
        <div class="pixel" style="font-size:18px;color:var(--gold-hi)">${num(t.gold)}</div>
        <div class="small muted">gold</div>
      </div>
      <div style="flex:1 1 230px;min-width:200px">
        <div class="section-title" style="margin:0 0 6px">CONDITION</div>
        <div class="pixel" style="font-size:12px;color:${esc(alarm.colour || 'var(--ink)')}">
          ${esc(String(alarm.name || '—').toUpperCase())}</div>
        <div class="small muted">${num(alarm.health)}/${num(alarm.health_max, 1)} health
          · ${num(alarm.failures_left)} bad submission(s) of grace</div>
        <div class="small muted">kit: ${esc(cond.label || '—')}
          ${cond.worst ? `· worst is the ${esc(cond.worst)}` : ''}</div>
      </div>
      <div style="flex:3 1 340px;min-width:280px">
        <div class="section-title" style="margin:0 0 6px">THE LOOP</div>
        <p class="small" style="margin:0 0 6px">${esc(loop.line || '')}</p>
        <p class="small muted" style="margin:0">
          Upkeep runs ${num(loop.upkeep_per_encounter).toFixed(1)} gold an encounter
          against ${num(loop.income_per_encounter)} earned —
          <span style="color:${loop.within_budget ? 'var(--green)' : 'var(--orange)'}">
          ${Math.round(share * 100)}% of what you make${measured ? '' : ' (expected)'}</span>,
          and the budget this game holds itself to is
          ${Math.round(num(loop.budget) * 100)}%.</p>
      </div>
    </div>`;
  latchAlarm(alarm);
}

/* upkeep.py: "latch on `band` and only speak on a transition downward." The
 * town is where a player looks up from the problem, so it is the one place the
 * advice is worth a sentence rather than a colour. */
function latchAlarm(alarm) {
  const band = String(alarm.band || '');
  if (!band || band === SAID_BAND) return;
  const order = ['DIRE', 'CRITICAL', 'WORN', 'STEADY'];
  const worse = order.indexOf(band) < order.indexOf(SAID_BAND || 'STEADY');
  SAID_BAND = band;
  if (worse && alarm.advice) HOST.toast(band, alarm.advice, band === 'DIRE' ? 'red' : 'violet');
}

function paintTabs() {
  const host = $('#town-tabs');
  if (!host) return;
  host.innerHTML = '';
  for (const t of TABS) {
    const b = el('button', `btn small${TAB === t.id ? ' primary' : ''}`, t.label);
    b.title = t.blurb;
    b.onclick = () => { TAB = t.id; HOST.sfx('select'); paintTabs(); paintBody(); };
    host.appendChild(b);
  }
}

async function paintBody() {
  const body = $('#town-body');
  if (!body) return;
  if (TAB === 'mender') return paintMender(body);
  if (TAB === 'smith') return paintSmith(body);
  if (TAB === 'shelf') return paintShelf(body);
  if (TAB === 'broker') return paintBroker(body);
  return paintVoices(body);
}

/* ----------------------------------------------------------- the Mender */

function paintMender(body) {
  const t = TOWN || {};
  const healer = t.healer || {};
  const alarm = t.alarm || {};
  const visit = t.visit || {};
  const her = visit.healer || {};
  const loop = t.loop || {};
  body.innerHTML = `
    <div class="frame" style="padding:16px;display:flex;gap:16px;flex-wrap:wrap">
      <div id="mender-face" style="flex:0 0 96px"></div>
      <div style="flex:1 1 340px;min-width:260px">
        <div class="pixel" style="font-size:13px;color:var(--gold-hi)">
          ${esc(String(healer.name || 'THE MENDER').toUpperCase())}</div>
        <div class="small" style="color:var(--violet);margin:4px 0 10px">
          ${esc(healer.title || '')}</div>
        <p class="small">${esc(healer.blurb || '')}</p>
        <div class="frame" style="padding:12px;margin-top:10px;border-left:4px solid var(--green)">
          <div class="section-title" style="margin-top:0">IT IS FREE, AND HERE IS WHY</div>
          <p class="small" style="margin:0">${esc(healer.free_because || '')}</p>
        </div>
      </div>
    </div>
    <div class="grid2" style="margin-top:12px">
      ${card('WHAT SHE WOULD DO RIGHT NOW', `
        ${meter('HEALTH', alarm.health, alarm.health_max, alarm.colour)}
        <p class="small muted" style="margin:8px 0 0">${esc(alarm.blurb || '')}
          ${alarm.advice ? esc(' ' + alarm.advice) : ''}</p>
        ${her.cured_names && her.cured_names.length
          ? `<p class="small">Afflictions she would lift: ${
              esc(her.cured_names.join(', '))}.</p>` : ''}
        ${her.revived && her.revived.length
          ? `<p class="small" style="color:var(--green)">A fainted companion would
             be back on its feet: ${esc(her.revived.join(', '))}.</p>` : ''}
        <div class="actions" style="margin-top:12px">
          <button class="btn good" id="btn-heal">ASK HER AGAIN — FREE</button>
        </div>
        <p class="small muted">Walking into the square already did this once.
        Pressing it is for whatever you picked up standing here.</p>`,
        { accent: 'var(--green)' })}
      ${card('WHAT THE LOOP COSTS', `
        <p class="small">${esc(loop.tension || '')}</p>
        <p class="small muted">${esc(loop.escape_hatch || '')}</p>
        <p class="small muted">Free, always: ${esc(lines(loop.free).join(', ') || '—')}.
          ${(loop.mandatory || []).length
            ? `Never optional: ${esc(lines(loop.mandatory).join(', '))}.`
            : 'Nothing here is mandatory.'}</p>`)}
    </div>
    ${her.lines && her.lines.length
      ? card('SHE SAYS', prose(her.lines, 'small'), { accent: 'var(--violet)' }) : ''}`;

  drawFace($('#mender-face'), 'mender');
  const btn = $('#btn-heal');
  if (btn) btn.onclick = () => doHeal(btn);
}

async function doHeal(btn) {
  btn.disabled = true;
  const r = await api.heal().catch(e => ({ error: e.message }));
  btn.disabled = false;
  if (!r || r.error) {
    HOST.toast(isSealed(r) ? sealedTitle(r) : 'NOT TODAY', refusal(r), 'red');
    return;
  }
  HOST.sfx('unlock');
  if (!r.did_something) {
    HOST.toast('NOTHING TO DO', lines(r.lines)[0]
      || 'You are whole. Go and break something.', '');
  } else {
    /* gold_cost and free_because are shown TOGETHER and once. The player has
     * just been handed seventeen points of health and the interesting fact is
     * that the number next to it is a zero. */
    HOST.toast('THE MENDER', `+${num(r.restored)} health${
      r.cured_names && r.cured_names.length
        ? `, ${r.cured_names.join(' and ')} lifted` : ''}${
      r.revived && r.revived.length ? `, ${r.revived.join(' and ')} back up` : ''}
      — ${num(r.gold_cost)} gold.`, 'green');
    if (lines(r.lines).length) HOST.say(String((r.healer || {}).name || 'MARGIT ORR')
      .toUpperCase(), lines(r.lines), 'scholar');
  }
  SAID_BAND = '';
  await HOST.refresh();
  await paintTown();
}

/* ------------------------------------------------------------- the smith */

function paintSmith(body) {
  const t = TOWN || {};
  const quote = t.quote || {};
  const cond = t.condition || {};
  const rows = quote.rows || [];
  const purse = num(t.gold);

  body.innerHTML = `
    <div class="frame" style="padding:16px">
      <div class="pixel" style="font-size:13px;color:var(--gold-hi)">
        ${esc(String(quote.smith || 'THE SMITH').toUpperCase())}</div>
      ${prose(quote.lines, 'small')}
      <p class="small muted">Armour is mended with gold and never with a potion.
      A piece left alone floors at half effectiveness and stops — it does not
      break, and nothing here is mandatory.</p>
    </div>
    ${card('WHAT YOU ARE WEARING', (cond.pieces || []).map(p => `
      <div class="list-item" style="cursor:default">
        <span class="t" style="color:${p.degraded ? 'var(--red)'
          : p.advised ? 'var(--orange)' : 'var(--green)'}">
          ${esc(String(p.piece).toUpperCase())}
          <span class="tag">${esc(p.rarity || '')}</span>
          ${p.tier && p.tier.name ? `<span class="tag violet">${esc(p.tier.name)}</span>` : ''}
        </span>
        <span class="d">
          ${meter('INTEGRITY', p.integrity, 100,
            p.degraded ? 'var(--red)' : p.advised ? 'var(--orange)' : 'var(--green)')}
          <span class="muted small">effectiveness ${Math.round(num(p.effectiveness, 1) * 100)}%
          · toughness ${num(p.toughness, 1).toFixed(2)}${
            p.degraded ? ' · floored, and it will not get worse'
              : p.advised ? ' · he would do this one first' : ''}</span>
        </span>
      </div>`).join('') + `
      <p class="small muted">Whole kit at ${Math.round(num(cond.scale, 1) * 100)}% —
      ${esc(cond.label || '')}.</p>`)}
    ${card('THE QUOTE', rows.length ? `
      <div id="quote-rows"></div>
      <p class="small" style="margin-top:10px">
        ${num(quote.gold)} gold for the lot. You have ${purse}.
        ${quote.free_points ? `${num(quote.free_points)} point(s) he will not charge for.` : ''}
        <span style="color:${quote.affordable ? 'var(--green)' : 'var(--orange)'}">
        ${quote.affordable ? 'You can cover it.'
          : (quote.partial || []).length
            ? `You cannot cover all of it. He would do ${
                esc(lines(quote.partial).join(', '))} for what you have.`
            : 'You cannot cover any of it yet.'}</span></p>
      <div class="actions">
        <button class="btn good" id="btn-mend-all">MEND WHAT THE GOLD BUYS</button>
      </div>
      <p class="small muted">Cheapest-first until the gold runs out. That is the
      normal case for a poor player and it is not an error — he mends what he
      can and tells you what is left.</p>`
      : '<p class="small muted">Nothing on you needs him. Come back after a few '
        + 'fights.</p>', { accent: 'var(--gold)' })}`;

  const host = $('#quote-rows');
  if (host) {
    for (const row of rows) {
      const afford = purse >= num(row.gold);
      const item = el('div', 'list-item', `
        <span class="t">${esc(String(row.piece).toUpperCase())}
          <span class="tag ${afford ? 'green' : 'red'}">${num(row.gold)} gold</span>
          ${row.mercy ? '<span class="tag violet">HE IS BEING KIND</span>' : ''}</span>
        <span class="d">at ${num(row.integrity)}% · ${num(row.points)} point(s) of wear,
          ${num(row.charged_points)} charged at ${num(row.gold_per_point).toFixed(2)} each
          ${row.free_points ? `· ${num(row.free_points)} free` : ''}</span>`);
      item.onclick = () => doRepair(row.piece);
      host.appendChild(item);
    }
  }
  const all = $('#btn-mend-all');
  if (all) all.onclick = () => doRepair('');
}

async function doRepair(piece) {
  const r = await api.repair(piece).catch(e => ({ error: e.message }));
  if (!r || r.error) {
    HOST.toast(isSealed(r) ? sealedTitle(r) : 'THE BENCH IS COLD', refusal(r), 'red');
    return;
  }
  /* `ok` is not the whole story and reading only it is the bug this comment is
   * here to stop: a poor player mending nothing gets ok:false with a sentence,
   * and a poor player mending ONE of three pieces gets a real result that a
   * bare `ok` would throw away. Read `mended` and `gold_spent`. */
  if (!(r.mended || []).length) {
    HOST.toast('NOT YET', r.message || 'Come back with gold.', 'red');
  } else {
    HOST.sfx('unlock');
    /* `mended` is rows, not names — {piece, points, gold, ...} each — and
     * `message` is upkeep's own sentence about the same event. The sentence is
     * the better half; the rows are what says how many pieces, which matters
     * when the gold only covered some of them. */
    const pieces = (r.mended || []).map(m => (m && m.piece) || m);
    HOST.toast('MENDED', r.message
      || `${pieces.join(', ')} — ${num(r.gold_spent)} gold.`, 'green');
    if (r.remaining && r.remaining.length) {
      HOST.toast('STILL OUTSTANDING',
        `${r.remaining.map(x => x.piece).join(', ')} — the gold ran out first, `
        + 'which is the normal way this goes.', '');
    }
  }
  await HOST.refresh();
  await paintTown();
}

/* ------------------------------------------------------------- the shelf */

async function paintShelf(body) {
  body.innerHTML = '<p class="small muted">Reading the shelf…</p>';
  const r = await api.shop().catch(e => ({ error: e.message }));
  if (!body.isConnected) return;
  if (!r || r.error) { body.innerHTML = refusalCard(r, { title: 'NOBODY IS TRADING' }); return; }
  const v = r.vendor || {};
  const stock = r.stock || [];
  body.innerHTML = `
    <div class="frame" style="padding:16px">
      <div class="pixel" style="font-size:13px;color:var(--gold-hi)">
        ${esc(String(v.name || 'THE VENDOR').toUpperCase())}
        <span class="tag">${esc(v.trade || '')}</span>
        <span class="tag violet">${esc(r.band || '')}</span></div>
      ${prose(v.lines, 'small')}
      <p class="small muted">${num(r.gold)} gold in the purse${
        r.credit ? ` · ${num(r.credit)} in credit banked here by a quest`
                 : ''} · the shelf restocks in ${num(r.restock_in)} clear(s).</p>
    </div>
    ${card('THE SHELF', stock.length
      ? '<div id="shelf-rows"></div><p class="small muted" style="margin-top:10px">'
        + 'A price is not a hint, so this is readable during a measured run. '
        + 'Buying is not.</p>'
      : '<p class="small muted">Bare. Clear a few encounters and come back.</p>')}`;

  const host = $('#shelf-rows');
  if (!host) return;
  for (const p of stock) {
    const row = el('div', 'list-item', `
      <span class="t" style="color:${esc(p.colour || 'var(--gold)')}">
        ${esc(p.name)}
        <span class="tag ${p.affordable ? 'green' : 'red'}">${num(p.price)} gold</span>
        <span class="tag">${esc(p.kind_label || p.kind || '')}</span>
        <span class="tag violet">${num(p.stock)} left</span></span>
      <span class="d">${esc(p.blurb || '')}<br>
        <span class="muted small">${esc(p.flavour || '')}</span><br>
        <span class="muted small">roughly ${num(p.fights).toFixed(1)} fight(s)
          or ${num(p.minutes).toFixed(0)} minute(s) of survival
          · you can carry ${num(p.cap)}</span></span>`);
    const buy = el('button', 'btn small good', 'BUY ONE');
    buy.disabled = !p.affordable || !num(p.stock);
    buy.onclick = (e) => { e.stopPropagation(); doBuy(p.id, 1, buy); };
    row.appendChild(buy);
    host.appendChild(row);
  }
}

async function doBuy(id, quantity, btn) {
  btn.disabled = true;
  const r = await api.buyPotion(id, '', quantity).catch(e => ({ error: e.message }));
  if (!r || r.error) {
    btn.disabled = false;
    HOST.toast(isSealed(r) ? sealedTitle(r) : 'SHE KEEPS IT ON THE SHELF',
      refusal(r) || 'Not that one.', 'red');
    return;
  }
  HOST.sfx('unlock');
  /* Two purses come back and they are not the same. `credit_spent` was banked
   * here by a quest and was already gone; `gold_spent` has just left. `gold` is
   * the truth afterwards and is the only one worth putting in front of a
   * player as a balance. */
  HOST.toast('BOUGHT', `${r.quantity}× ${r.name} — ${num(r.gold_spent)} gold${
    r.credit_spent ? ` and ${num(r.credit_spent)} of credit` : ''}.${
    r.overflow ? ` ${r.overflow} would not fit in the pouch and were not charged for.` : ''}`,
    'green');
  await HOST.refresh();
  const body = $('#town-body');
  if (body) await paintShelf(body);
}

/* ------------------------------------------------------------ the broker */

async function paintBroker(body) {
  body.innerHTML = '<p class="small muted">The kettle is on…</p>';
  const r = await api.broker().catch(e => ({ error: e.message }));
  if (!body.isConnected) return;
  if (!r || r.error) { body.innerHTML = refusalCard(r, { title: 'SHE HAS MOVED ON' }); return; }
  const b = r.broker || {};
  const trial = r.trial && r.trial.form ? r.trial : null;

  body.innerHTML = `
    <div class="frame" style="padding:16px;display:flex;gap:16px;flex-wrap:wrap">
      <div id="broker-face" style="flex:0 0 96px"></div>
      <div style="flex:1 1 340px;min-width:260px">
        <div class="pixel" style="font-size:13px;color:${esc(b.colour || 'var(--gold-hi)')}">
          ${esc(String(b.name || 'THE BROKER').toUpperCase())}</div>
        <div class="small" style="color:var(--violet);margin:4px 0 8px">
          ${esc(b.epithet || '')}</div>
        <p class="small">${esc(b.blurb || '')}</p>
        <p class="small muted">Was ${esc(b.was || '')}. Carries ${esc(b.carries || '')}.</p>
        <p class="small" style="color:var(--gold)">“${esc(b.law || '')}”</p>
        <p class="small">${esc(r.greeting || '')}</p>
        <p class="small muted">${num(r.completed_here)} contract(s) settled in this
          region · ${num(r.gold)} gold in the purse.</p>
      </div>
    </div>
    <div id="broker-open"></div>
    <div id="broker-board"></div>`;
  drawFace($('#broker-face'), b.sprite || 'assayer');

  const open = $('#broker-open');
  if (trial) {
    open.innerHTML = card('THE CONTRACT THAT IS OPEN', `
      <div class="pixel" style="font-size:12px;color:var(--gold-hi)">
        ${esc(String(trial.name || trial.form).toUpperCase())}</div>
      ${meter('PROGRESS', trial.done, trial.need, 'var(--gold)',
        `${num(trial.done)}/${num(trial.need)}`)}
      <p class="small">Quoted at ${num(trial.quote)} gold, band ${esc(trial.band || '')}.
        ${(trial.demands || []).length
          ? `She wants: ${esc(lines(trial.demands).join('; '))}.` : 'No extra demands.'}</p>
      ${trial.failed ? '<p class="small" style="color:var(--red)">This one has already '
        + 'gone wrong. Settling it now is settling it for what it is worth.</p>' : ''}
      <p class="small muted">Every submission counts toward it, right or wrong.
        A trial that only saw the clears would be a trial you could fail for free.</p>
      <div class="actions">
        <button class="btn primary" id="btn-settle">WEIGH IT AND PAY</button>
        <button class="btn" id="btn-abandon">WALK AWAY</button>
      </div>
      <p class="small muted">Walking away is priced, not voided.</p>`,
      { accent: 'var(--gold)' });
    const settle = $('#btn-settle');
    const walk = $('#btn-abandon');
    if (settle) settle.onclick = () => doClose(false, settle);
    if (walk) walk.onclick = () => doClose(true, walk);
  } else {
    open.innerHTML = '';
  }

  const board = $('#broker-board');
  board.innerHTML = card('THE BOARD', `
    ${trial ? '<p class="small muted">One at a time, ever. Settle the open one '
      + 'before she will quote another.</p>' : ''}
    <div id="broker-offers"></div>
    ${(r.locked || []).length ? `<div class="section-title">NOT YET</div>
      ${(r.locked || []).map(l => `<div class="list-item locked" style="cursor:default">
        <span class="t">${esc(l.name)}</span>
        <span class="d">${num(l.have)} of ${num(l.needs)} problem(s) of history —
          she quotes on what she has weighed before.</span></div>`).join('')}` : ''}`);

  const offers = $('#broker-offers');
  for (const o of (r.offers || [])) {
    const row = el('div', `list-item${trial ? ' locked' : ''}`, `
      <span class="t">${esc(o.name)}
        <span class="tag gold">${num(o.total)} gold</span>
        <span class="tag">${num(o.problems)} problem(s)</span>
        <span class="tag violet">${esc(o.band || '')}</span></span>
      <span class="d">${esc(o.offer || '')}<br>
        <span class="muted small">${esc(o.blurb || '')}
        ${(o.demand_text || []).length ? ` · ${esc(lines(o.demand_text).join('; '))}` : ''}
        · ${num(o.problems_pay)} for the work, ${num(o.payout)} on top for the shape
        </span></span>`);
    if (!trial) row.onclick = () => doOpen(o.id);
    offers.appendChild(row);
  }
  if (!(r.offers || []).length) {
    offers.innerHTML = '<p class="small muted">Nothing on the board here today.</p>';
  }
}

async function doOpen(formId) {
  const r = await api.openTrial(formId).catch(e => ({ error: e.message }));
  if (!r || r.error) {
    HOST.toast(isSealed(r) ? sealedTitle(r) : 'SHE WILL NOT QUOTE THAT',
      refusal(r), 'red');
    return;
  }
  HOST.sfx('unlock');
  HOST.say('ORIN TALLOW', [r.line, r.quote_line,
    `${r.quote} gold, and I quote before the work. Always.`].filter(Boolean), 'oracle');
  await HOST.refresh();
  const body = $('#town-body');
  if (body) await paintBroker(body);
}

async function doClose(abandon, btn) {
  btn.disabled = true;
  const r = await api.closeTrial(abandon).catch(e => ({ error: e.message }));
  btn.disabled = false;
  if (!r || r.error) {
    HOST.toast(isSealed(r) ? sealedTitle(r) : 'NOT SETTLED', refusal(r), 'red');
    return;
  }
  const award = r.award || {};
  HOST.sfx(num(r.gold) ? 'unlock' : 'select');
  HOST.toast(abandon ? 'WALKED AWAY' : 'WEIGHED',
    `${num(r.gold)} gold. Purse ${num(r.purse)}.`, num(r.gold) ? 'green' : '');
  if (lines(award.lines).length) {
    HOST.say('ORIN TALLOW', lines(award.lines), 'oracle');
  }
  await HOST.refresh();
  const body = $('#town-body');
  if (body) await paintBroker(body);
}

/* ------------------------------------------------------------ the voices */

/* ONE CALL, not one per face. banter.py rotates the roster and reads the area
 * once; a speak() per person would have five townspeople disagreeing about the
 * weather in the same square. */
export async function paintVoices(body, regionId) {
  body.innerHTML = '<p class="small muted">Listening…</p>';
  const r = await api.townTalk(regionId || '').catch(e => ({ error: e.message }));
  if (!body.isConnected) return;
  if (!r || r.error) {
    body.innerHTML = refusalCard(r, { title: 'NOBODY IS TALKING' });
    return;
  }
  const speakers = r.speakers || [];
  body.innerHTML = `
    <div class="frame" style="padding:14px">
      <div class="pixel" style="font-size:12px;color:var(--gold-hi)">
        ${esc(String(r.region_name || '').toUpperCase())}</div>
      <p class="small muted">${speakers.length} ${speakers.length === 1 ? 'person' : 'people'}
        standing here.${r.sealed
          ? ' They will talk, but not about the weather or your boots — '
            + 'that reading is sealed for the run.'
          : ''}</p>
    </div>
    <div id="voice-rows"></div>`;
  const host = $('#voice-rows');
  for (const s of speakers) host.appendChild(voiceCard(s));
  if (!speakers.length) {
    host.innerHTML = '<p class="small muted">The square is empty today.</p>';
  }
}

/* IDENTITY FIRST. banter.py is specific about this and it is the difference
 * between a town and an advice kiosk: who this person is comes before what they
 * noticed, and the second half is drawn under the first rather than instead of
 * it. */
function voiceCard(s) {
  const node = el('div', 'frame', `
    <div style="display:flex;gap:14px;flex-wrap:wrap">
      <div class="voice-face" style="flex:0 0 72px"></div>
      <div style="flex:1 1 320px;min-width:240px">
        <div class="pixel" style="font-size:11px;color:var(--gold-hi)">
          ${esc(String(s.name || '').toUpperCase())}
          <span class="tag">${esc(s.role || '')}</span>
          ${s.register ? `<span class="tag violet">${esc(s.register)}</span>` : ''}</div>
        <p class="small" style="color:var(--ink);margin:8px 0 10px;font-style:italic">
          ${esc(s.identity || '')}</p>
        <div class="voice-lines">${prose(s.lines, 'small')}</div>
        <div class="row" style="margin-top:8px">
          <button class="btn small">ASK AGAIN</button>
          <span class="small muted">${esc(lines(s.beats).join(' · '))}</span>
        </div>
      </div>
    </div>`);
  node.style.padding = '14px';
  node.style.marginBottom = '10px';
  drawFace(node.querySelector('.voice-face'), s.sprite || 'villager');
  const again = node.querySelector('button');
  again.onclick = async () => {
    again.disabled = true;
    const r = await api.speakTo(s.id).catch(e => ({ error: e.message }));
    again.disabled = false;
    if (!r || r.error) {
      HOST.toast(isSealed(r) ? sealedTitle(r) : 'THEY HAVE SAID THEIR PIECE',
        refusal(r), 'red');
      return;
    }
    const box = node.querySelector('.voice-lines');
    if (box) box.innerHTML = prose(r.lines, 'small');
    HOST.sfx('tick');
  };
  return node;
}

/* One person, in the dialogue box, for the overworld NPC marker. Same call,
 * different frame: this is the "second remark from somebody already standing
 * there" that speak() is for. */
export async function speakInDialogue(npcId) {
  const r = await api.speakTo(npcId).catch(e => ({ error: e.message }));
  if (!r || r.error) {
    HOST.toast(isSealed(r) ? sealedTitle(r) : 'NOBODY ANSWERS', refusal(r), 'red');
    return null;
  }
  HOST.say(String(r.name || '').toUpperCase(),
    [r.identity, ...lines(r.lines)].filter(Boolean), r.sprite || 'villager');
  return r;
}

/* The square, in the dialogue box, for walking into the NPC marker or pressing
 * the button on the world side.
 *
 * THE FIRST PRESS IS townTalk() AND THE REST ARE speak(). That division is
 * banter.py's own: the square is read ONCE, so five people do not disagree with
 * each other about the weather, and every face after the first is a second
 * remark from somebody already standing there. Walking round the roster and
 * coming back to the start reads the square again, which is what makes the
 * rotation advance rather than loop on the same five sentences. */
let ROSTER = { region: '', ids: [], at: 0 };

export async function talkOnTheOverworld(regionId) {
  const region = regionId || '';
  if (ROSTER.region === region && ROSTER.ids.length) {
    ROSTER.at += 1;
    if (ROSTER.at < ROSTER.ids.length) return speakInDialogue(ROSTER.ids[ROSTER.at]);
    ROSTER = { region: '', ids: [], at: 0 };   // round the houses; read it again
  }
  const r = await api.townTalk(region).catch(e => ({ error: e.message }));
  if (!r || r.error) {
    HOST.toast(isSealed(r) ? sealedTitle(r) : 'NOBODY IS ABOUT', refusal(r), 'red');
    return null;
  }
  const speakers = r.speakers || [];
  ROSTER = { region, ids: speakers.map(s => s.id), at: 0 };
  const first = speakers[0];
  if (!first) {
    HOST.toast('QUIET TODAY', 'Nobody is standing in the square.', '');
    return r;
  }
  HOST.say(String(first.name || '').toUpperCase(),
    [first.identity, ...lines(first.lines)].filter(Boolean), first.sprite || 'villager');
  return r;
}

/* ------------------------------------------------------------------ faces */

/* sprites.portrait is the same twelve-pixel face the dialogue box uses, so a
 * person looks the same whether they are talking to you or standing in a list. */
function drawFace(host, kind) {
  if (!host) return;
  let img;
  try { img = sprites.portrait(faceFor(kind)); } catch (e) { return; }
  if (!img) return;
  const c = el('canvas');
  c.width = img.width; c.height = img.height;
  c.style.cssText = 'width:72px;height:72px;image-rendering:pixelated;display:block';
  c.getContext('2d').drawImage(img, 0, 0);
  host.innerHTML = '';
  host.appendChild(c);
}
