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
    let detail = res.statusText;
    try { detail = (await res.json()).error || detail; } catch (e) { /* keep status */ }
    throw new Error(detail);
  }
  return res.json();
}

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
};
