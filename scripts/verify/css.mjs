import fs from 'fs';
const read = p => fs.readFileSync('/Users/japa/Documents/PythonCodingGauntletLegend/web/css/' + p, 'utf8');
const game = read('game.css'), metal = read('metal.css');

// Strip comments, then pull rule heads and their declaration blocks.
const strip = s => s.replace(/\/\*[\s\S]*?\*\//g, '');
function rules(src) {
  const out = [];
  const s = strip(src);
  const re = /([^{}]+)\{([^{}]*)\}/g;
  let m;
  while ((m = re.exec(s))) {
    const head = m[1].trim().replace(/\s+/g, ' ');
    if (!head || head.startsWith('@')) continue;
    out.push({ head, body: m[2] });
  }
  return out;
}
const gr = rules(game), mr = rules(metal);

// Individual selectors (split on commas), normalised.
const sels = rs => { const set = new Set(); for (const r of rs) for (const p of r.head.split(',')) { const t = p.trim(); if (t) set.add(t); } return set; };
const gameSel = sels(gr), metalSel = sels(mr);

// A selector "exists in game.css" if game.css has it, or has the same class/id
// token anywhere. Geometry only breaks when the TARGET is unknown to game.css.
const gameTokens = new Set();
for (const s of gameSel) for (const t of s.match(/[.#][A-Za-z0-9_-]+/g) || []) gameTokens.add(t);
const gameRaw = strip(game);

const unknown = [];
for (const s of metalSel) {
  if (gameSel.has(s)) continue;
  const toks = s.match(/[.#][A-Za-z0-9_-]+/g) || [];
  if (toks.length === 0) continue;                       // :root, body, element selectors
  const known = toks.filter(t => gameTokens.has(t));
  if (known.length === 0) unknown.push({ sel: s, toks });
}

// Layout properties metal.css must not introduce on a game.css-owned component.
const LAYOUT = ['display','position','top','right','bottom','left','width','height',
  'min-width','min-height','max-width','max-height','margin','margin-top','margin-right',
  'margin-bottom','margin-left','padding','padding-top','padding-right','padding-bottom',
  'padding-left','flex','flex-direction','flex-wrap','flex-grow','flex-shrink','flex-basis',
  'grid','grid-template-columns','grid-template-rows','grid-template-areas','grid-column',
  'grid-row','gap','row-gap','column-gap','align-items','justify-content','float','clear',
  'box-sizing','overflow','overflow-x','overflow-y'];

const layoutHits = [];
for (const r of mr) {
  for (const p of r.head.split(',')) {
    const sel = p.trim(); if (!sel) continue;
    const toks = sel.match(/[.#][A-Za-z0-9_-]+/g) || [];
    const ownedByGame = toks.some(t => gameTokens.has(t));
    if (!ownedByGame) continue;                          // metal.css's own component
    for (const decl of r.body.split(';')) {
      const i = decl.indexOf(':'); if (i < 0) continue;
      const prop = decl.slice(0, i).trim().toLowerCase();
      if (prop.startsWith('--')) continue;
      if (!LAYOUT.includes(prop)) continue;
      // Does game.css set this property on a rule mentioning the same token?
      const tok = toks.find(t => gameTokens.has(t));
      const gameRules = gr.filter(g => g.head.includes(tok));
      const gameSetsIt = gameRules.some(g => new RegExp('(^|;|\\{)\\s*' + prop + '\\s*:', 'i').test(g.body));
      layoutHits.push({ sel, prop, value: decl.slice(i + 1).trim().slice(0, 40), alsoInGame: gameSetsIt });
    }
  }
}

// Rarity custom properties
const rarities = ['common','uncommon','rare','epic','legendary','mythic'];
const varsDefined = new Set((strip(metal).match(/--[A-Za-z0-9_-]+(?=\s*:)/g) || []));
const varsUsed = new Set((strip(metal).match(/var\(\s*(--[A-Za-z0-9_-]+)/g) || []).map(s => s.replace(/var\(\s*/, '')));
const gameVars = new Set((gameRaw.match(/--[A-Za-z0-9_-]+(?=\s*:)/g) || []));
const rarityVars = {};
for (const r of rarities) rarityVars[r] = [...varsDefined].filter(v => v.toLowerCase().includes(r));
const undefinedVars = [...varsUsed].filter(v => !varsDefined.has(v) && !gameVars.has(v));

console.log(JSON.stringify({
  counts: { gameRules: gr.length, metalRules: mr.length, gameSelectors: gameSel.size, metalSelectors: metalSel.size },
  selectorsUnknownToGameCss: { n: unknown.length, detail: unknown.slice(0, 40) },
  layoutOnGameOwned: { n: layoutHits.length, newGeometry: layoutHits.filter(h => !h.alsoInGame).length,
    detailNew: layoutHits.filter(h => !h.alsoInGame).slice(0, 40) },
  rarityVars,
  undefinedVarRefs: { n: undefinedVars.length, detail: undefinedVars.slice(0, 30) },
}, null, 1));

/* --- refinement: pseudo-element decoration is not parent geometry --- */
const risky = [], pseudo = [], benign = [];
const BENIGN_ON_PARENT = { position: ['relative'], 'box-sizing': ['border-box'], overflow: ['hidden'] };
for (const h of layoutHits.filter(x => !x.alsoInGame)) {
  if (/::(after|before|marker|placeholder|selection|backdrop|-webkit-[a-z-]+)/.test(h.sel)) { pseudo.push(h); continue; }
  const ok = BENIGN_ON_PARENT[h.prop];
  if (ok && ok.includes(h.value.replace(/!important/, '').trim())) { benign.push(h); continue; }
  risky.push(h);
}
console.log('\n=== REFINED ===');
console.log('pseudo-element decoration (safe, own box):', pseudo.length);
console.log('benign containing-block/box-sizing on parent:', benign.length, JSON.stringify(benign.map(b=>b.sel+' '+b.prop+':'+b.value)));
console.log('RISKY real-element geometry changes:', risky.length);
for (const r of risky) console.log('   ', r.sel, '{', r.prop + ':', r.value, '}');
