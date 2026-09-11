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

export const api = {
  state: () => call('/api/state'),
  world: () => call('/api/world'),
  ping: () => call('/api/ping'),
  sandboxCheck: () => call('/api/sandbox/check'),
  history: (problemId) =>
    call('/api/history' + (problemId ? `?problem_id=${encodeURIComponent(problemId)}` : '')),
  problem: (id, mode) =>
    call(`/api/problem?id=${encodeURIComponent(id)}&mode=${mode || 'adventure'}`),
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
  chooseClass: (classId) => softPost('/api/class/choose', { class_id: classId }),
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

  /* -- the final exam -- */
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
};
