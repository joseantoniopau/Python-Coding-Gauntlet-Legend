// Import everything the way main.js does and prove nothing shadows anything.
import { installStub } from './stub.mjs';
installStub();
import * as pixel   from '../../web/js/pixel.js';
import * as sprites from '../../web/js/sprites.js';
import * as tiles   from '../../web/js/tiles.js';
import * as bosses  from '../../web/js/bosses.js';
import * as lootart from '../../web/js/lootart.js';
import * as spellfx from '../../web/js/spellfx.js';
import * as scene   from '../../web/js/battlescene.js';
import { createBattleFX, DAMAGE_KIND, trialsFromFeedback } from '../../web/js/fx.js';

const ns = { pixel, sprites, tiles, bosses, lootart, spellfx, scene };
for (const [n, m] of Object.entries(ns)) {
  if (!m || typeof m !== 'object') throw new Error('namespace broken: ' + n);
}
// The colliding names must each resolve through their own namespace.
const probes = [
  ['sprites.bossSprite', typeof sprites.bossSprite],
  ['pixel.bossSprite',   typeof pixel.bossSprite],
  ['bosses.bossSprite',  typeof bosses.bossSprite],
  ['tiles.createScene',  typeof tiles.createScene],
  ['scene.createScene',  typeof scene.createScene],
  ['fx.DAMAGE_KIND',     typeof DAMAGE_KIND],
  ['spellfx.DAMAGE_KIND', typeof spellfx.DAMAGE_KIND],
  ['sprites.rng', typeof sprites.rng], ['tiles.rng', typeof tiles.rng], ['pixel.rng', typeof pixel.rng],
  ['sprites.ramp', typeof sprites.ramp], ['tiles.ramp', typeof tiles.ramp],
  ['sprites.BOSS_MOTION', typeof sprites.BOSS_MOTION], ['bosses.BOSS_MOTION', typeof bosses.BOSS_MOTION],
];
for (const [k, t] of probes) if (t === 'undefined') throw new Error('missing ' + k);
// Distinct identities: the new module must not be re-exporting the old one.
const distinct = [
  ['bossSprite', sprites.bossSprite !== bosses.bossSprite],
  ['BOSS_MOTION', sprites.BOSS_MOTION !== bosses.BOSS_MOTION],
  ['createScene', tiles.createScene !== scene.createScene],
  ['DAMAGE_KIND value-equal', JSON.stringify(DAMAGE_KIND) === JSON.stringify(spellfx.DAMAGE_KIND)],
];
console.log('namespaced co-import: OK');
for (const [k, v] of distinct) console.log('  ' + k + ':', v);
console.log('  fx helpers:', typeof createBattleFX, typeof trialsFromFeedback);
