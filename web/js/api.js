/* Thin client over the local API. The token is injected into index.html by the
 * server so a page from anywhere else cannot drive the game. */
const TOKEN = window.__GAUNTLET_TOKEN__ || '';

async function call(path, options = {}) {
  const res = await fetch(path, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      'X-Gauntlet-Token': TOKEN,
      ...(options.headers || {}),
    },
  });
  if (!res.ok) {
    let body = null;
    let detail = res.statusText;
    try { body = await res.json(); detail = body.error || detail; } catch (e) { /* keep status */ }
    const err = new Error(detail);
    /* The server answers a refusal with a readable body: `error`, and for a
     * sealed endpoint `capability` and `message` too. Throwing away everything
     * but the sentence is how a screen ends up saying "409" at a player. */
    err.status = res.status;
    err.payload = body;
    throw err;
  }
  return res.json();
}

/* Same request, but a refusal is an answer rather than an exception. Used by
 * the world-layer calls where "no, and here is why" is a thing to render: a
 * sealed endpoint during the exam, an unknown id, a quest that is not finished
 * yet. Only a genuine server fault still throws. */
async function soft(path, options = {}) {
  try {
    return await call(path, options);
  } catch (err) {
    if (err.payload && err.status && err.status < 500) return err.payload;
    throw err;
  }
}

const softPost = (path, body) =>
  soft(path, { method: 'POST', body: JSON.stringify(body || {}) });
const q = encodeURIComponent;
// Guidance is optional: a stalled localhost request must not hold a lesson
// trigger forever. Gameplay calls retain their existing timeout policy.
const guidance = (path, body) => soft(path, {
  signal: AbortSignal.timeout(4000),
  ...(body === undefined ? {} : { method: 'POST', body: JSON.stringify(body) }),
});

export const api = {
  state: () => call('/api/state'),
  practice: () => soft('/api/practice'),
  practiceStart: body => softPost('/api/practice/start', body),
  practiceAction: action => soft('/api/practice/action', { method:'POST', body:JSON.stringify({action}), keepalive:true }),
  practiceNext: () => softPost('/api/practice/next', {}),
  practiceDraft: body => soft('/api/practice/draft', {
    method: 'POST', body: JSON.stringify(body), keepalive: true,
  }),
  appearance: () => soft('/api/appearance'),
  appearanceSelect: id => softPost('/api/appearance', {id}),
  journal: () => soft('/api/journal'),
  journalNote: (family, text) => softPost('/api/journal/note', { family, text }),
  trace: (code, caseIndex) => softPost('/api/trace', { code, case_index: caseIndex }),
  lessons: () => guidance('/api/lessons'),
  lesson: (id) => guidance('/api/lesson', { id }),
  lessonNote: (kind, id) => guidance('/api/lesson/note', { kind, id }),
  lessonsForget: () => guidance('/api/lesson/forget', {}),
  world: () => call('/api/world'),
  ping: () => call('/api/ping'),
  sandboxCheck: () => call('/api/sandbox/check'),
  history: (problemId) =>
    call('/api/history' + (problemId ? `?problem_id=${encodeURIComponent(problemId)}` : '')),
  problem: (id, mode) =>
    call(`/api/problem?id=${encodeURIComponent(id)}&mode=${mode || 'adventure'}`),
  resumeEncounter: id => soft('/api/encounter/resume'+(id?'?problem_id='+encodeURIComponent(id):'')),
  nextEncounter: (body) =>
    call('/api/encounter/next', { method: 'POST', body: JSON.stringify(body || {}) }),
  startEncounter: (problemId, mode) =>
    call('/api/encounter/start', {
      method: 'POST', body: JSON.stringify({ problem_id: problemId, mode }),
    }),
  run: (code) => call('/api/run', { method: 'POST', body: JSON.stringify({ code }) }),
  submit: (body) => call('/api/submit', { method: 'POST', body: JSON.stringify(body) }),
  mcq: (choice) => call('/api/mcq', { method: 'POST', body: JSON.stringify({ choice }) }),
  hint: (level) => call('/api/hint', { method: 'POST', body: JSON.stringify({ level }) }),
  explain: (text) => call('/api/explain', { method: 'POST', body: JSON.stringify({ text }) }),
  shrine: () => call('/api/shrine'),
  shrineAnswer: (text) =>
    call('/api/shrine/answer', { method: 'POST', body: JSON.stringify({ text }) }),
  startBoss: (bossId) =>
    call('/api/boss/start', { method: 'POST', body: JSON.stringify({ boss_id: bossId }) }),
  bossLadder: (bossId) =>
    call('/api/boss/ladder', { method: 'POST', body: JSON.stringify({ boss_id: bossId }) }),

  /* -- the keys, the roads they open, and the door that counts them --------
   *
   * Both GETs are WORLD by docs/10-sealed-views.md: a key is a boss you beat,
   * it does not move when the question on the screen does, no seal suspends
   * it, and it names no problem. So both are `call`, not `soft` — a refusal
   * here would be a bug rather than a rule.
   *
   * `enterPortal` is a POST because stepping through changes the world, and it
   * is `softPost` because "the wards are not answered" is an ANSWER the screen
   * has to render — it comes back with the fourteen keys, which ones are dark,
   * and which boss is still holding each. A 409 rendered as an exception would
   * throw away the only useful part of the refusal.
   *
   * NONE OF THESE THREE IS ON THE PATH TO THE PRACTICAL. `startInterview`
   * above does not consult them, and it never will: the exam is a measurement
   * and is reachable from the menu with no keys at all. Every payload here
   * carries `practical`, which says exactly that, so the screen that counts
   * the keys is also the screen that tells the player the exam is not behind
   * them. */
  keys: () => call('/api/keys'),
  portal: () => call('/api/portal'),
  enterPortal: () => softPost('/api/portal/enter', {}),

  /* THE LAST FIGHT, AND THE ONLY STAGED ROUTE IN THE GAME.
   *
   * `startExam` below and this are the SAME practical — same composer, same
   * seal, same clock, same six questions. The only difference is that this one
   * tells the server, by the id of the exam it just composed, that this sitting
   * is the last room of the story. Call it from the portal room and from
   * nowhere else; calling it from the menu would collapse the two exams into
   * one and delete the ending by making it fire for practice.
   *
   * It is NOT the door to the practical and it is not a second way in. A player
   * with no keys still presses SIT IT NOW and gets `startExam`, which is the
   * whole point of the game. If this ever returns `staging.staged === false`
   * — the wards went dark, somehow — the exam has still started and that is
   * NOT an error: render it as information, or not at all. */
  startFinalTrial: (profile) =>
    softPost('/api/portal/trial', { profile: profile || '' }),

  /* The Null King, reading one line out of your file. `soft` because a
   * measured run answers with no lines rather than an error, and because a
   * villain who fails to load must never be able to stop a screen drawing. */
  antagonist: () => soft('/api/antagonist'),
  unmaking: () => soft('/api/unmaking'),
  unmakingSeen: () => softPost('/api/unmaking/seen', {}),
  startInterview: (format, profile) =>
    call('/api/interview/start', {
      method: 'POST', body: JSON.stringify({ format, profile }),
    }),
  interviewCurrent: () => call('/api/interview/current'),
  finishInterview: () => call('/api/interview/finish', { method: 'POST', body: '{}' }),
  setting: (key, value) =>
    call('/api/settings', { method: 'POST', body: JSON.stringify({ key, value }) }),
  profile: (profile) =>
    call('/api/profile', { method: 'POST', body: JSON.stringify({ profile }) }),
  move: (region, x, y) =>
    call('/api/move', { method: 'POST', body: JSON.stringify({ region, x, y }) }),
  loadout: () => call('/api/loadout'),
  curriculum: () => call('/api/curriculum'),
  story: () => call('/api/story'),
  diagnostic: () => call('/api/diagnostic'),
  diagnosticCheck: (trial, answer) =>
    call('/api/diagnostic/check', { method: 'POST', body: JSON.stringify({ trial, answer }) }),
  diagnosticFinish: (answers, skipped) =>
    call('/api/diagnostic/finish', {
      method: 'POST', body: JSON.stringify({ answers, skipped }),
    }),
  puzzle: (answer) =>
    call('/api/puzzle', { method: 'POST', body: JSON.stringify({ answer }) }),
  storyAdvance: () => call('/api/story/advance', { method: 'POST', body: '{}' }),
  probes: () => call('/api/probes'),
  probe: (args, expected, ops) =>
    call('/api/probe', { method: 'POST', body: JSON.stringify({ args, expected, ops }) }),
  equip: (itemId) =>
    call('/api/equip', { method: 'POST', body: JSON.stringify({ item_id: itemId }) }),
  unequip: (slot) =>
    call('/api/unequip', { method: 'POST', body: JSON.stringify({ slot }) }),
  allocate: (attribute, points) =>
    call('/api/allocate', { method: 'POST', body: JSON.stringify({ attribute, points }) }),
  chooseBuild: (build) =>
    call('/api/build', { method: 'POST', body: JSON.stringify({ build }) }),
  respec: () => call('/api/respec', { method: 'POST', body: '{}' }),
  consumable: (id) =>
    call('/api/consumable', { method: 'POST', body: JSON.stringify({ id }) }),
  /* -- the belt --
   * Drinking is NOT a turn. The cast is still owed after this resolves, and
   * the result says so in two fields the interface must show rather than
   * paraphrase: `turn_spent` (false) and `must_still_cast` (true). One draught
   * per turn — a second before the next graded submission comes back
   * { ok: false, error: 'already' } with the sentence to print in `message`.
   * Soft, because every one of those refusals is a thing to render: sealed in
   * a measured run (409), nothing to cure, already at full health. Read `ok`
   * before you read anything else. */
  potion: (id) => softPost('/api/potion', { id }),
  search: (region, x, y) =>
    call('/api/search', { method: 'POST', body: JSON.stringify({ region, x, y }) }),
  exportSave: () => call('/api/export'),
  importSave: (payload) =>
    call('/api/import', { method: 'POST', body: JSON.stringify({ payload }) }),
  /* The scratch console. A working endpoint with no wrapper until now. */
  scratch: (code) => call('/api/scratch', { method: 'POST', body: JSON.stringify({ code }) }),

  /* ====================================================================
   * The world layer. Eleven modules that a browser could not reach until
   * these. Everything below goes through `soft`, because every one of them
   * can legitimately answer "no": sealed during the exam (409), unknown id
   * (404), or a refusal the module wrote itself ({ error } at 200). Read
   * `.error` before you read anything else.
   * ================================================================== */

  /* -- classes and the skill tree -- */
  classes: () => soft('/api/classes'),
  classTree: () => soft('/api/class/tree'),
  // `body` is the authored rig — 'a' or 'b', shown to the player as male or
  // female. Optional: the server defaults it rather than refusing.
  chooseClass: (classId, body) =>
    softPost('/api/class/choose', { class_id: classId, body: body || '' }),
  spendNode: (nodeId) => softPost('/api/class/spend', { node_id: nodeId }),
  respecTree: (scope, branchId) =>
    softPost('/api/class/respec', { scope: scope || 'all', branch_id: branchId || '' }),
  chooseDual: (classId) => softPost('/api/class/dual', { class_id: classId }),

  /* -- quests -- */
  quests: (region) => soft('/api/quests' + (region ? `?region=${q(region)}` : '')),
  quest: (id) => soft(`/api/quest?id=${q(id)}`),
  chains: () => soft('/api/chains'),
  acceptQuest: (id) => softPost('/api/quest/accept', { quest_id: id }),
  abandonQuest: (id) => softPost('/api/quest/abandon', { quest_id: id }),
  turnInQuest: (id) => softPost('/api/quest/turnin', { quest_id: id }),

  /* -- companions -- */
  pets: () => soft('/api/pets'),
  petDiscovery: (id) => soft('/api/pets/discovery' + (id ? `?id=${q(id)}` : '')),
  setPets: (ids) => softPost('/api/pets/active', { pet_ids: ids || [] }),
  /* A companion costs a hint and caps the rank; the server charges both. Call
   * it as the player works and play `result.pet` if it is not null. */
  petIntervene: (signals) => softPost('/api/pet/intervene', { signals: signals || {} }),
  /* The six-rung tier ladder with the roster under each rung. Read-only. */
  petTiers: () => soft('/api/pets/tiers'),
  /* One in the field at a time, and both directions are reversible. setPets()
   * already performs the implicit dismissal, because choosing a new companion
   * IS dismissing the old one; these two exist so the gesture can be named. */
  dismissPet: () => softPost('/api/pet/dismiss', {}),
  recallPet: (id) => softPost('/api/pet/recall', { pet_id: id }),
  /* The barrow scene has been played. Clears the undelivered scene only; the
   * fact it happened stays in the save for good. */
  ackFall: () => softPost('/api/pet/fall/ack', {}),
  /* Every road out of the encounter the player is standing in, whatever is or
   * is not walking with them. Spends nothing. This is what a tier refusal is
   * pointed at, and it is the reason a refusal is never a dead end. */
  hintRoute: () => soft('/api/hint/route'),

  /* -- dungeons -- */
  dungeons: (region) => soft('/api/dungeons' + (region ? `?region=${q(region)}` : '')),
  dungeon: () => soft('/api/dungeon'),
  enterDungeon: (id) => softPost('/api/dungeon/enter', { dungeon_id: id }),
  /* Drive the room view from `options` and nothing else — it is what
   * guarantees there is always something to press. */
  dungeonMove: (room) => softPost('/api/dungeon/move', { room }),
  dungeonEngage: () => softPost('/api/dungeon/engage', {}),
  dungeonRetreat: () => softPost('/api/dungeon/retreat', {}),
  leaveDungeon: () => softPost('/api/dungeon/leave', {}),

  /* -- progression -- */
  worldMap: () => soft('/api/world-map'),
  region: (id) => soft('/api/region' + (id ? `?id=${q(id)}` : '')),
  routes: (region) => soft('/api/routes' + (region ? `?region=${q(region)}` : '')),
  events: () => soft('/api/events'),
  /* Never empty. Render it unconditionally; that is the no-dead-end rule. */
  todo: () => soft('/api/todo'),
  travel: (routeId) => softPost('/api/travel', { route: routeId }),
  discoverRoute: (routeId) => softPost('/api/route/discover', { route: routeId }),

  /* -- saves -- */
  saves: () => soft('/api/saves'),
  saveSlot: (ordinal, name, note) =>
    softPost('/api/save', { ordinal, name: name || '', note: note || '' }),
  loadSlot: (slotId) => softPost('/api/load', { slot_id: slotId }),
  undoLoad: () => softPost('/api/undo', {}),
  renameSlot: (slotId, name) => softPost('/api/slot/rename', { slot_id: slotId, name }),
  deleteSlot: (slotId) => softPost('/api/slot/delete', { slot_id: slotId }),
  /* Returns the envelope itself; the browser writes the file. The server
   * never touches the player's disk. */
  exportSlot: (slotId) => softPost('/api/slot/export', { slot_id: slotId }),
  importSlot: (payload, ordinal, name) =>
    softPost('/api/slot/import', { payload, ordinal, name: name || '' }),

  /* -- legendaries -- */
  legendaries: () => soft('/api/legendaries'),
  legendary: (id) => soft(`/api/legendary?id=${q(id)}`),
  hand: () => soft('/api/hand'),
  /* Solves it, pays loot and XP in full, and lowers the skill's ceiling for
   * good. Show `notice` once, plainly, and do not editorialise. */
  useHand: () => softPost('/api/hand/use', {}),

  /* -- mini-repo battles --
   * Somebody else's codebase, a suite and a clock. `repoRun` is ungraded and
   * can be pressed as often as the player likes; `repoSubmit` is the attempt.
   * Both take the WHOLE working tree — every project file and every test file,
   * as they stand. The test bodies must be in there: the server tells an
   * untouched suite from a deleted one by their absence, so a tree without them
   * reads as a deletion and fails the attempt. Pass fullTree=false only for a
   * partial save, which this client does not do. */
  repos: (difficulty, tag) => soft('/api/repos'
    + (difficulty ? `?difficulty=${q(difficulty)}` : '')
    + (tag ? `${difficulty ? '&' : '?'}tag=${q(tag)}` : '')),
  repo: () => soft('/api/repo'),
  startRepo: (repoId, mode, difficulty) => softPost('/api/repo/start', {
    repo_id: repoId || '', mode: mode || 'adventure', difficulty: difficulty || '',
  }),
  repoRun: (files) => softPost('/api/repo/run', { files }),
  repoSubmit: (files, fullTree) =>
    softPost('/api/repo/submit', { files, full_tree: fullTree !== false }),
  leaveRepo: () => softPost('/api/repo/leave', {}),

  /* -- the forge --
   * Metals drop where you fight; Vess works them in Python Village. Reading is
   * never sealed — what you own is not a hint — and `forge()` answers with the
   * quote, the shortfall, where the shortfall drops, her lines, the technique
   * ladder and the swap comparison in one call. It also answers whether she is
   * actually in reach: `at_the_bench` is false everywhere but her own region,
   * and the reading is still worth having there, because knowing what you are
   * short of is what gets a player walking.
   *
   * `forgeUpgrade()` is BUILD and is refused during a measured run. It never
   * spends anything on a refusal — read `error` ('metal', 'gold', 'at_top',
   * 'unowned', 'away', 'sealed'), then `message` if there is one, then
   * `still_short` and `gold_short`, which say what is missing AFTER Vess's
   * substitution rather than before it. */
  forge: (blade) => soft('/api/forge' + (blade ? `?blade=${q(blade)}` : '')),
  forgeTechnique: (blade) =>
    soft('/api/forge/technique' + (blade ? `?blade=${q(blade)}` : '')),
  forgeSwap: (blade) => soft('/api/forge/swap' + (blade ? `?blade=${q(blade)}` : '')),
  /* Every metal, where it drops, and roughly how many fights a bar is. This is
   * the panel that stops a player deciding a rung is a wall. */
  forgeMetals: () => soft('/api/forge/metals'),
  forgeUpgrade: (blade) => softPost('/api/forge/upgrade', { blade: blade || '' }),
  /* Taking the blade off keeps its rung. A forge does not un-forge anything,
   * so trying a found weapon for a chapter costs nothing but the rungs you did
   * not forge while you were away. */
  forgeRack: (blade) => softPost('/api/forge/rack', { blade: blade || '' }),
  forgeUnrack: () => softPost('/api/forge/unrack', {}),

  /* -- the wheel --
   * The rulebook: six elements, six statuses, six hazards, eight boots, the
   * seventeen regions' affinities and the twelve potions, straight off
   * elements.py's and potions.py's own tables. Static for the life of the
   * process, so fetch it once and keep it — and never copy any of it into
   * JavaScript, because a status's duration having two homes is how the tooltip
   * and the fight end up disagreeing. Not sealed: this is the rulebook, not a
   * reading of the thing in front of you. */
  wheel: () => soft('/api/wheel'),

  /* -- the final exam -- */
  transfer: () => soft('/api/transfer'),
  examLadder: () => soft('/api/exam/ladder'),
  startExam: (profile) => softPost('/api/exam/start', { profile: profile || '' }),
  finishExam: (secondsBySegment) =>
    softPost('/api/exam/finish', { seconds_by_segment: secondsBySegment || {} }),

  /* -- worldgen -- */
  worldCard: () => soft('/api/world/card'),
  /* `seed` takes a world code, a number, or any phrase. The canonical code
   * comes back in `seed`; display that rather than what was typed. */
  newWorld: (seed) => softPost('/api/world/new', { seed: seed || 0 }),

  /* -- incantation combat -- */
  incantations: (region) =>
    soft('/api/incantation' + (region ? `?region=${q(region)}` : '')),
  incantState: () => soft('/api/incantation/state'),
  startIncant: (encounterId) => softPost('/api/incant/start', { encounter_id: encounterId }),
  /* Takes IncantationUI's cast payload whole — `move_id` plus `holes`, or
   * `answers`, or the assembled `line`. The server does the translation. */
  incantCast: (payload) => softPost('/api/incant/cast', payload),
  leaveIncant: () => softPost('/api/incant/leave', {}),

  /* ====================================================================
   * THE TEN SYSTEMS THAT HAD NO DOOR.
   *
   * Same contract as everything above: `soft`, so a refusal is an answer.
   * Read `.error` first. A sealed refusal is a 409 carrying `capability` and
   * `message` — render the message and name the capability, never the number.
   *
   * The seal is enforced server-side on every one of these, and for most of
   * them that is not belt-and-braces: the engine asks `finalexam.sealed()`
   * about the ENCOUNTER, and in a measured run there is no encounter between
   * problems. The door asks whether the run is open. Do not reimplement either
   * test here — a client-side seal is not a seal.
   * ================================================================== */

  /* -- the town: the healer, the smith, and the loop --
   * `town()` is the whole square in one call: the Mender's visit, the loop
   * report, your armour's condition, the low-health alarm, the smith's quote
   * and your purse. Reading is never sealed; healing and mending are.
   *
   * Health is free. Affliction removal is free. Reviving a fainted companion
   * is free. `heal()` returns `free_because` and it is worth showing once —
   * health gates ATTEMPTS, and charging for attempts steepens the curve
   * exactly where it should flatten. Gold goes to the smith instead.
   *
   * `repair(piece)` with no piece mends cheapest-first until the gold runs
   * out, which is the normal case for a poor player and is not an error: read
   * `mended` and `gold_spent`, not just `ok`. */
  town: () => soft('/api/town'),
  repairQuote: (piece) => soft('/api/town/quote' + (piece ? `?piece=${q(piece)}` : '')),
  heal: () => softPost('/api/town/heal', {}),
  repair: (piece) => softPost('/api/town/repair', { piece: piece || '' }),

  /* -- the shelf --
   * Seventeen vendors, one per region, each with its own shelf and its own
   * restock clock. `shop()` is read freely — a price is not a hint.
   *
   * `buyPotion` fills the pouch before it returns. Two purses come back and
   * they are not the same: `gold_spent` has already left your purse, and
   * `credit_spent` was banked at this vendor by a quest and was already gone.
   * Show `gold`, which is the truth afterwards. On a refusal read `error`
   * ('no_gold', 'no_stock', and the rest) and print `text`. */
  shop: (region) => soft('/api/shop' + (region ? `?region=${q(region)}` : '')),
  buyPotion: (potionId, region, quantity) => softPost('/api/shop/buy', {
    potion_id: potionId, region: region || '', quantity: quantity || 1,
  }),

  /* -- the rack, on the same shelf's east wall --
   * Eight pegs of generated armour and, some weeks, one blade blank. They ride
   * the SAME `/api/shop` payload the potions do — `rack`, `rack_left`,
   * `rack_index`, `rack_bounds` and `blank` — so there is no second read.
   *
   * THE WALL CANNOT BE REROLLED, and the panel should say so rather than
   * inviting the player to try: a peg is a pure function of (save seed,
   * region, restock index) and the restock index only moves on six CLEARED
   * encounters. Walking out, leaving the region, quitting to the title and
   * reloading the save appear in none of those.
   *
   * All three writes are sealed at BUILD during a measured run, because armour
   * is a loadout change — read `error` ('sealed', 'no_gold', 'sold',
   * 'not_bought', 'not_held', 'no_blank', 'owned') and print `text`.
   * `buyRack` takes a SLOT, not an id, because a peg is identified by where it
   * hangs. `sellRack` pays a quarter and refuses if the piece is not still in
   * the bag. */
  buyRack: (slot, region) => softPost('/api/shop/rack/buy', {
    slot, region: region || '',
  }),
  sellRack: (itemId, region) => softPost('/api/shop/rack/sell', {
    item_id: itemId, region: region || '',
  }),
  buyBlank: (region) => softPost('/api/shop/blank', { region: region || '' }),

  /* -- the challenge broker --
   * One trial open at a time, ever. `broker()` is the board plus whatever is
   * already open under `trial`. `openTrial` takes a form id off the board;
   * `closeTrial(abandon)` settles it — pass true to walk away, and the award
   * is priced accordingly rather than voided. Both are sealed in a measured
   * run, closing included: a contract that pays gold mid-exam is the world
   * advancing under a player who is sealed off from it. */
  broker: (region) => soft('/api/broker' + (region ? `?region=${q(region)}` : '')),
  openTrial: (formId, region) =>
    softPost('/api/broker/open', { form_id: formId, region: region || '' }),
  closeTrial: (abandon) => softPost('/api/broker/close', { abandon: !!abandon }),

  /* -- the hidden healers --
   * Seventeen of them, found by being hurt in the right place rather than by
   * searching. `sanctuaries()` is the journal plus `needed`, which says
   * whether one is urgent right now, plus `marks` for the dungeon floor you
   * are standing on. `rest()` is free for the same reason the Mender is free,
   * and it revives a fainted companion, which is the whole point of a healer
   * hidden where a fainted companion happens. It also pays a toll — the rest
   * counts as time spent away from town, and `toll_lines` says so. */
  sanctuaries: () => soft('/api/sanctuaries'),
  sanctuaryRest: (sanctuaryId) =>
    softPost('/api/sanctuary/rest', { sanctuary_id: sanctuaryId }),

  /* -- the town's forty-seven voices --
   * POST, not GET, and deliberately: both of these WRITE. The rotation
   * advances so the same person does not open with the same sentence twice.
   *
   * Render `identity` FIRST and the composed `lines` after it. A screen that
   * draws only the second has built an advice kiosk out of a town. Build one
   * screen from one `townTalk()` call rather than a `speak()` per face, or the
   * town disagrees with itself about the weather; `speak()` is for a second
   * remark from somebody already standing there.
   *
   * Sealed at WEAKNESS_MAP during a measured run: a townsperson reading the
   * local element and your boots back at you is the tactical read arriving
   * through a friendlier face. */
  townTalk: (region) => softPost('/api/town/talk', { region: region || '' }),
  speakTo: (npcId) => softPost('/api/npc/speak', { npc_id: npcId }),

  /* -- regalia --
   * Twenty-four objects, one per companion, that buy MORE help and never
   * DEEPER help: they move how OFTEN a companion may speak and how EARLY, and
   * they never move the depth of what it says. `regalia()` reports the numbers
   * ACTUALLY in force, which means the quest-awarded pieces are folded in
   * through the same single floor (`floor`) and single ceiling (`ceiling`) —
   * show those two, because they are what stop the two regalia systems
   * stacking past what either of them declares legal.
   *
   * `wearRegalia('')` takes the worn object off and is always allowed outside
   * a measured run. Sealed at PET inside one. */
  regalia: () => soft('/api/regalia'),
  wearRegalia: (regaliaId) => softPost('/api/regalia/wear', { regalia_id: regaliaId || '' }),

  /* -- the sixteen hidden sages and the ninety-six secret arts --
   * `sage(region)` shows whoever sits here: as a SILHOUETTE with the deed
   * spelled out if they have not been found, never as a grey wall. Read
   * `may_attempt` and `why` — `why` is a thing to go and do, which is the
   * no-dead-end rule wearing its working clothes. `art` names what is behind
   * the trial without rendering its line.
   *
   * `beginGauntlet()` binds five rungs to REAL problems and returns them in
   * `bound` ({stage_key: problem_id}). `gauntletEncounter(key)` opens that
   * rung's problem through the ordinary encounter door — same sandbox, same
   * grader, same mastery, same loot — so the player answers it the way they
   * answer anything. Then `gauntletStage(key)`.
   *
   * NOTE WHAT gauntletStage DOES NOT TAKE: whether the rung was passed. That
   * is read off the attempts table. Mastery moves only on graded evidence, and
   * a client cannot assert its way to a secret art.
   *
   * Failing costs the TOLL and never a door: three more encounters in this
   * region before the sage will see you again. No mastery, no gold, no gear.
   * A second attempt draws DIFFERENT problems from the same specifications. */
  sage: (region) => soft('/api/sage' + (region ? `?region=${q(region)}` : '')),
  beginGauntlet: (region) => softPost('/api/sage/begin', { region: region || '' }),
  gauntletEncounter: (stageKey) => softPost('/api/sage/encounter', { stage_key: stageKey }),
  gauntletStage: (stageKey) => softPost('/api/sage/stage', { stage_key: stageKey }),
  /* What this playthrough knows and how far the ladder still runs. Not sealed:
   * what you own is not a hint, same as the forge. */
  arts: () => soft('/api/arts'),

  /* -- the people the bosses took --
   * THREE lists, not two, and they come back in the same row shape
   * deliberately: `freed` is who was carried out by hand when a boss fell,
   * `released` is who got up on their own when the index stopped pointing
   * (each row carrying its own `released_line`, so it is never staged as a
   * rescue), and `still_held` is who is in a niche right now. The ending is a
   * eucatastrophe and not a restoration, and a roll call that quietly rounded
   * up — or that dropped the middle list, which is what `still_held` has
   * always subtracted — would be this game telling a lie about itself.
   * `released_count` and `index_collapsed` come with them. Large — seventeen
   * villages of faces and trades — so fetch it when the roll call opens, not
   * on every frame. */
  rollCall: () => soft('/api/rollcall'),

  /* -- the last scene --
   * Staged AFTER the practical is scored and never before. Pass the exam
   * report you were just handed. The direction of the gate, said once: the
   * practical gates the finale and the finale does not gate the practical — a
   * player who freed nobody sits the same sealed, timed, unassisted exam and
   * can pass it. Sealed at MENTOR during a run.
   *
   * `markCodaSeen()` fires on `the_prompt_stays`, NOT on the freeze frame.
   * The two halves of this ending are separate and a player who walked out at
   * the title card has seen half of it. */
  finale: (examReport) => softPost('/api/finale', { exam_report: examReport || {} }),
  markCodaSeen: () => softPost('/api/finale/coda', {}),

  /* -- the hunt --
   * Seventeen roaming apex monsters, scaled to PREPARATION and to nothing
   * else — not to level, not to mastery. `hunt(region)` is the readout, and
   * the readout is the point of the feature: `scaling.blurb` says at the door
   * how long this will take, so a player at readiness zero can look at
   * fifty-two casts and walk away rather than find out afterwards.
   *
   * `hunt()` carries `client`, which is hunters.client_payload(): static for
   * the life of the process and most of the forty kilobytes. Keep the first
   * one and ignore it thereafter.
   *
   * ENGAGE FREEZES THE SCALING, which is what stops a player stripping their
   * gear mid-fight to shrink the pool. FLEE ALWAYS SUCCEEDS — no roll, turn
   * one included, no gold, no items, no mastery — and it is the one door here
   * that is never sealed, because a door that could refuse it would trap a
   * player in a fight they were told they could always leave.
   *
   * `huntResolve({casts, killed})` pays the bounty, priced on readiness AT THE
   * MOMENT THE FIGHT STARTED: somebody who had no business winning is paid for
   * having had no business winning. The typing is still the attack — `casts`
   * is how many lines actually landed, and resolving grades nothing and grants
   * no mastery, because the casting was already paid for where casting is
   * paid for. */
  hunt: (region) => soft('/api/hunt' + (region ? `?region=${q(region)}` : '')),
  huntEngage: (region) => softPost('/api/hunt/engage', { region: region || '' }),
  huntFlee: () => softPost('/api/hunt/flee', {}),
  huntResolve: (casts, killed) =>
    softPost('/api/hunt/resolve', { casts: casts || 0, killed: !!killed }),
};
