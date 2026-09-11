/* Animated algorithm visualisations.
 *
 * Every major pattern gets one. These are not decoration: the VISION spell shows
 * the algorithm running on a concrete input with its live state labelled, which
 * is the step that turns "I have heard of sliding window" into "I can see what
 * left, right and counts are doing".
 */
const FONT = '10px "Press Start 2P", monospace';

function cell(ctx, x, y, w, h, fill, stroke) {
  ctx.fillStyle = fill;
  ctx.fillRect(x, y, w, h);
  if (stroke) {
    ctx.strokeStyle = stroke;
    ctx.lineWidth = 1;
    ctx.strokeRect(x + 0.5, y + 0.5, w - 1, h - 1);
  }
}

function label(ctx, text, x, y, colour = '#e8e8f0', align = 'center') {
  ctx.fillStyle = colour;
  ctx.font = FONT;
  ctx.textAlign = align;
  ctx.textBaseline = 'middle';
  ctx.fillText(text, x, y);
}

/* Each visualiser is a generator of frames: { draw(ctx, w, h), caption, state }. */

function slidingWindow(data = 'abcabcbb', k = 3) {
  const items = typeof data === 'string' ? data.split('') : data;
  const frames = [];
  const counts = new Map();
  let left = 0, best = 0;
  for (let right = 0; right < items.length; right++) {
    counts.set(items[right], (counts.get(items[right]) || 0) + 1);
    let shrank = false;
    while (counts.get(items[right]) > 1) {
      counts.set(items[left], counts.get(items[left]) - 1);
      if (counts.get(items[left]) === 0) counts.delete(items[left]);
      left++;
      shrank = true;
    }
    best = Math.max(best, right - left + 1);
    frames.push({
      left, right, best, counts: new Map(counts),
      caption: shrank
        ? `'${items[right]}' repeated — left edge jumps to ${left}. Never backwards.`
        : `window [${left}..${right}] is valid, width ${right - left + 1}, best ${best}`,
    });
  }
  return {
    title: 'SLIDING WINDOW — longest substring without repeats',
    frames,
    draw(ctx, w, h, f) {
      const n = items.length;
      const cw = Math.min(44, (w - 40) / n);
      const x0 = (w - cw * n) / 2;
      const y = h * 0.34;
      // the window frame
      ctx.fillStyle = 'rgba(127,106,214,0.22)';
      ctx.fillRect(x0 + f.left * cw - 2, y - 12, (f.right - f.left + 1) * cw + 4, cw + 24);
      ctx.strokeStyle = '#a89aff';
      ctx.lineWidth = 2;
      ctx.strokeRect(x0 + f.left * cw - 2, y - 12, (f.right - f.left + 1) * cw + 4, cw + 24);
      for (let i = 0; i < n; i++) {
        const inside = i >= f.left && i <= f.right;
        cell(ctx, x0 + i * cw + 2, y, cw - 4, cw,
             inside ? '#3a3560' : '#1e1c2e', inside ? '#a89aff' : '#3a3550');
        label(ctx, String(items[i]), x0 + i * cw + cw / 2, y + cw / 2,
              inside ? '#ffffff' : '#6a6a80');
        const c = f.counts.get(items[i]);
        if (inside && c) label(ctx, String(c), x0 + i * cw + cw / 2, y - 20, '#e8c37d');
      }
      label(ctx, 'LEFT', x0 + f.left * cw + cw / 2, y + cw + 16, '#7ec8ff');
      label(ctx, 'RIGHT', x0 + f.right * cw + cw / 2, y + cw + 30, '#ff9d4a');
      label(ctx, `BEST ${f.best}`, w / 2, h - 26, '#8fd07a');
    },
  };
}

function twoPointer(data = [2, 7, 11, 15, 19, 24], target = 26) {
  const frames = [];
  let lo = 0, hi = data.length - 1;
  while (lo < hi) {
    const sum = data[lo] + data[hi];
    frames.push({
      lo, hi, sum,
      caption: sum === target ? `${data[lo]} + ${data[hi]} = ${target}. Found.`
        : sum < target ? `sum ${sum} < ${target} — only the LEFT runner can help`
          : `sum ${sum} > ${target} — only the RIGHT runner can help`,
    });
    if (sum === target) break;
    if (sum < target) lo++; else hi--;
  }
  return {
    title: 'TWO POINTERS — converging on a target sum',
    frames,
    draw(ctx, w, h, f) {
      const n = data.length;
      const cw = Math.min(56, (w - 40) / n);
      const x0 = (w - cw * n) / 2;
      const y = h * 0.38;
      for (let i = 0; i < n; i++) {
        const active = i === f.lo || i === f.hi;
        cell(ctx, x0 + i * cw + 2, y, cw - 4, cw,
             active ? '#3f5f7a' : '#1e1c2e', active ? '#7ec8ff' : '#3a3550');
        label(ctx, String(data[i]), x0 + i * cw + cw / 2, y + cw / 2,
              active ? '#ffffff' : '#7a7a90');
      }
      label(ctx, '▶ LO', x0 + f.lo * cw + cw / 2, y - 18, '#7ec8ff');
      label(ctx, 'HI ◀', x0 + f.hi * cw + cw / 2, y + cw + 18, '#ff9d4a');
      label(ctx, `${data[f.lo]} + ${data[f.hi]} = ${f.sum}   target ${target}`,
            w / 2, h - 26, '#e8c37d');
    },
  };
}

function bfsWave(rows = 5, cols = 8) {
  const frames = [];
  const dist = Array.from({ length: rows }, () => Array(cols).fill(-1));
  const blocked = new Set(['1,2', '2,2', '3,2', '1,5', '2,5']);
  const q = [[0, 0]];
  dist[0][0] = 0;
  let head = 0;
  while (head < q.length) {
    const size = q.length - head;
    const ring = [];
    for (let s = 0; s < size; s++) {
      const [r, c] = q[head++];
      ring.push([r, c]);
      for (const [nr, nc] of [[r + 1, c], [r - 1, c], [r, c + 1], [r, c - 1]]) {
        if (nr < 0 || nc < 0 || nr >= rows || nc >= cols) continue;
        if (blocked.has(`${nr},${nc}`) || dist[nr][nc] !== -1) continue;
        dist[nr][nc] = dist[r][c] + 1;
        q.push([nr, nc]);
      }
    }
    frames.push({
      dist: dist.map(r => r.slice()), depth: dist[ring[0][0]][ring[0][1]],
      caption: `ring ${dist[ring[0][0]][ring[0][1]]} expands — every cell here is exactly `
        + `${dist[ring[0][0]][ring[0][1]]} steps from the start`,
    });
  }
  return {
    title: 'BFS — a wave of light, ring by ring',
    frames,
    draw(ctx, w, h, f) {
      const cw = Math.min(40, (w - 40) / cols, (h - 90) / rows);
      const x0 = (w - cw * cols) / 2, y0 = h * 0.2;
      for (let r = 0; r < rows; r++) {
        for (let c = 0; c < cols; c++) {
          const key = `${r},${c}`;
          const d = f.dist[r][c];
          let fill = '#1a1828';
          if (blocked.has(key)) fill = '#4a3040';
          else if (d >= 0) {
            const t = Math.min(1, d / 10);
            fill = `rgb(${40 + t * 40}, ${90 + (1 - t) * 120}, ${150 + (1 - t) * 80})`;
          }
          cell(ctx, x0 + c * cw + 1, y0 + r * cw + 1, cw - 2, cw - 2, fill, '#2a2840');
          if (d >= 0 && !blocked.has(key)) {
            label(ctx, String(d), x0 + c * cw + cw / 2, y0 + r * cw + cw / 2, '#0c1420');
          }
        }
      }
      label(ctx, 'first arrival IS the shortest path', w / 2, h - 24, '#8fd07a');
    },
  };
}

function dfsPath(rows = 5, cols = 7) {
  const frames = [];
  const visited = new Set();
  const stack = [[0, 0]];
  const blocked = new Set(['1,1', '2,1', '3,1', '1,4', '2,4', '3,4']);
  const path = [];
  while (stack.length && frames.length < 60) {
    const [r, c] = stack[stack.length - 1];
    const key = `${r},${c}`;
    if (!visited.has(key)) {
      visited.add(key);
      path.push([r, c]);
      frames.push({ visited: new Set(visited), path: path.slice(), back: false,
                    caption: `commit deeper into (${r}, ${c})` });
    }
    let moved = false;
    for (const [nr, nc] of [[r + 1, c], [r, c + 1], [r - 1, c], [r, c - 1]]) {
      if (nr < 0 || nc < 0 || nr >= rows || nc >= cols) continue;
      if (blocked.has(`${nr},${nc}`) || visited.has(`${nr},${nc}`)) continue;
      stack.push([nr, nc]);
      moved = true;
      break;
    }
    if (!moved) {
      stack.pop();
      path.pop();
      frames.push({ visited: new Set(visited), path: path.slice(), back: true,
                    caption: 'dead end — visibly backtrack and try the other branch' });
    }
  }
  return {
    title: 'DFS — one path deeply, then back out',
    frames,
    draw(ctx, w, h, f) {
      const cw = Math.min(40, (w - 40) / cols, (h - 90) / rows);
      const x0 = (w - cw * cols) / 2, y0 = h * 0.2;
      const onPath = new Set(f.path.map(([r, c]) => `${r},${c}`));
      for (let r = 0; r < rows; r++) {
        for (let c = 0; c < cols; c++) {
          const key = `${r},${c}`;
          let fill = '#1a1828';
          if (blocked.has(key)) fill = '#4a3040';
          else if (onPath.has(key)) fill = '#4f8f5a';
          else if (f.visited.has(key)) fill = '#2a4a34';
          cell(ctx, x0 + c * cw + 1, y0 + r * cw + 1, cw - 2, cw - 2, fill, '#2a2840');
        }
      }
      label(ctx, f.back ? 'BACKTRACKING' : 'DESCENDING', w / 2, h - 24,
            f.back ? '#ff9d4a' : '#8fd07a');
    },
  };
}

function stackViz(tokens = '( [ { } ] )'.split(' ')) {
  const frames = [];
  const stack = [];
  const pairs = { ')': '(', ']': '[', '}': '{' };
  for (const t of tokens) {
    if ('([{'.includes(t)) {
      stack.push(t);
      frames.push({ stack: stack.slice(), action: 'push', token: t,
                    caption: `'${t}' opens — push it` });
    } else {
      const top = stack.pop();
      frames.push({ stack: stack.slice(), action: 'pop', token: t,
                    caption: top === pairs[t]
                      ? `'${t}' matches the top '${top}' — pop`
                      : `'${t}' does NOT match '${top}' — the vault seals` });
    }
  }
  frames.push({ stack: [], action: 'done', token: '',
                caption: 'stack empty at the end — everything was closed' });
  return {
    title: 'STACK — the most recent thing matters most',
    frames,
    draw(ctx, w, h, f) {
      const bw = 70, bh = 34;
      const x = w / 2 - bw / 2;
      const baseY = h - 70;
      for (let i = 0; i < f.stack.length; i++) {
        cell(ctx, x, baseY - i * (bh + 4), bw, bh, '#5a4a2a', '#e8c37d');
        label(ctx, f.stack[i], x + bw / 2, baseY - i * (bh + 4) + bh / 2, '#ffe8a0');
      }
      ctx.fillStyle = '#3a3550';
      ctx.fillRect(x - 10, baseY + bh, bw + 20, 4);
      label(ctx, f.action === 'push' ? `PUSH ${f.token}`
        : f.action === 'pop' ? `POP for ${f.token}` : 'EMPTY', w / 2, 48, '#e8c37d');
    },
  };
}

function queueViz(items = ['a1', 'a2', 'a3', 'a4', 'a5'], capacity = 3) {
  const frames = [];
  const q = [];
  for (const item of items) {
    let dropped = null;
    if (q.length === capacity) dropped = q.shift();
    q.push(item);
    frames.push({ q: q.slice(), dropped,
                  caption: dropped ? `buffer full — '${dropped}' leaves the FRONT`
                    : `'${item}' joins the back` });
  }
  return {
    title: 'QUEUE — first in, first out',
    frames,
    draw(ctx, w, h, f) {
      const bw = 78, bh = 40;
      const total = f.q.length * (bw + 8);
      const x0 = (w - total) / 2;
      const y = h / 2 - bh / 2;
      f.q.forEach((item, i) => {
        cell(ctx, x0 + i * (bw + 8), y, bw, bh, '#2a4a5a', '#7ec8ff');
        label(ctx, item, x0 + i * (bw + 8) + bw / 2, y + bh / 2, '#d8f0ff');
      });
      label(ctx, 'FRONT ◀', x0 - 6, y + bh / 2, '#ff9d4a', 'right');
      label(ctx, '▶ BACK', x0 + total + 6, y + bh / 2, '#8fd07a', 'left');
      if (f.dropped) label(ctx, `dropped: ${f.dropped}`, w / 2, h - 30, '#ff7a7a');
    },
  };
}

function treeViz() {
  const nodes = [
    { id: 0, v: 5, x: 0.5, y: 0.18, l: 1, r: 2 },
    { id: 1, v: 3, x: 0.28, y: 0.42, l: 3, r: 4 },
    { id: 2, v: 8, x: 0.72, y: 0.42, l: 5, r: 6 },
    { id: 3, v: 1, x: 0.16, y: 0.68, l: null, r: null },
    { id: 4, v: 4, x: 0.40, y: 0.68, l: null, r: null },
    { id: 5, v: 7, x: 0.60, y: 0.68, l: null, r: null },
    { id: 6, v: 9, x: 0.84, y: 0.68, l: null, r: null },
  ];
  const frames = [];
  (function walk(id, lo, hi) {
    if (id === null) return;
    const n = nodes[id];
    frames.push({
      active: id, lo, hi,
      caption: `node ${n.v} must lie strictly inside (${lo}, ${hi})`
        + (n.v > lo && n.v < hi ? ' — valid' : ' — VIOLATION'),
    });
    walk(n.l, lo, n.v);
    walk(n.r, n.v, hi);
  })(0, '-∞', '+∞');
  return {
    title: 'TREE — every node inherits a range from its ancestors',
    frames,
    draw(ctx, w, h, f) {
      ctx.strokeStyle = '#3a5540';
      ctx.lineWidth = 2;
      for (const n of nodes) {
        for (const c of [n.l, n.r]) {
          if (c === null) continue;
          ctx.beginPath();
          ctx.moveTo(n.x * w, n.y * h);
          ctx.lineTo(nodes[c].x * w, nodes[c].y * h);
          ctx.stroke();
        }
      }
      for (const n of nodes) {
        const active = n.id === f.active;
        ctx.beginPath();
        ctx.arc(n.x * w, n.y * h, 18, 0, Math.PI * 2);
        ctx.fillStyle = active ? '#4f8f5a' : '#23302a';
        ctx.fill();
        ctx.strokeStyle = active ? '#8fd07a' : '#3a5540';
        ctx.stroke();
        label(ctx, String(n.v), n.x * w, n.y * h, active ? '#ffffff' : '#8faf95');
      }
      label(ctx, `allowed range: (${f.lo}, ${f.hi})`, w / 2, h - 26, '#8fd07a');
    },
  };
}

function hashMapViz(values = [2, 7, 11, 15], target = 9) {
  const frames = [];
  const seen = new Map();
  for (let i = 0; i < values.length; i++) {
    const need = target - values[i];
    const hit = seen.has(need);
    frames.push({
      i, need, hit, seen: new Map(seen),
      caption: hit ? `${need} is already in the vault — pair found at ${seen.get(need)} and ${i}`
        : `need ${need}; not seen yet — store ${values[i]} at index ${i}`,
    });
    if (hit) break;
    seen.set(values[i], i);
  }
  return {
    title: 'HASH MAP — each key opens exactly one vault',
    frames,
    draw(ctx, w, h, f) {
      const cw = Math.min(64, (w - 40) / values.length);
      const x0 = (w - cw * values.length) / 2;
      const y = h * 0.22;
      values.forEach((v, i) => {
        const active = i === f.i;
        cell(ctx, x0 + i * cw + 2, y, cw - 4, 40,
             active ? '#5a4a2a' : '#1e1c2e', active ? '#e8c37d' : '#3a3550');
        label(ctx, String(v), x0 + i * cw + cw / 2, y + 20,
              active ? '#ffe8a0' : '#7a7a90');
      });
      let vy = y + 76;
      label(ctx, 'VAULT (value → index)', w / 2, vy, '#e8c37d');
      vy += 26;
      for (const [k, idx] of f.seen) {
        const highlight = f.hit && k === f.need;
        cell(ctx, w / 2 - 80, vy - 12, 160, 24,
             highlight ? '#5a4a2a' : '#1e1c2e', highlight ? '#ffd97a' : '#3a3550');
        label(ctx, `${k} → ${idx}`, w / 2, vy, highlight ? '#ffe8a0' : '#9a9ab0');
        vy += 28;
      }
      label(ctx, `looking for ${f.need}`, w / 2, h - 24,
            f.hit ? '#8fd07a' : '#7ec8ff');
    },
  };
}

function recursionViz(depth = 4) {
  const frames = [];
  for (let d = 0; d <= depth; d++) {
    frames.push({ d, unwinding: false,
                  caption: d === depth ? `base case reached at depth ${d}`
                    : `enter a smaller copy of the same room (depth ${d})` });
  }
  for (let d = depth; d >= 0; d--) {
    frames.push({ d, unwinding: true, value: Math.pow(2, depth - d),
                  caption: `return to depth ${d} carrying ${Math.pow(2, depth - d)}` });
  }
  return {
    title: 'RECURSION — nested rooms, and what you carry back out',
    frames,
    draw(ctx, w, h, f) {
      const maxD = depth;
      for (let d = 0; d <= maxD; d++) {
        const inset = d * Math.min(w, h) * 0.075;
        const rw = w - inset * 2 - 40;
        const rh = h - inset * 2 - 80;
        if (rw <= 0 || rh <= 0) continue;
        const active = d === f.d;
        ctx.strokeStyle = active ? (f.unwinding ? '#8fd07a' : '#a89aff') : '#3a3550';
        ctx.lineWidth = active ? 3 : 1;
        ctx.strokeRect(20 + inset, 40 + inset, rw, rh);
        if (active) {
          ctx.fillStyle = f.unwinding ? 'rgba(143,208,122,0.12)' : 'rgba(168,154,255,0.12)';
          ctx.fillRect(20 + inset, 40 + inset, rw, rh);
          label(ctx, f.unwinding ? `↑ ${f.value}` : `depth ${d}`,
                20 + inset + rw / 2, 40 + inset + 16,
                f.unwinding ? '#8fd07a' : '#a89aff');
        }
      }
      label(ctx, f.unwinding ? 'UNWINDING' : 'DESCENDING', w / 2, h - 20,
            f.unwinding ? '#8fd07a' : '#a89aff');
    },
  };
}

function dpViz(n = 9) {
  const frames = [];
  const dp = [1, 1];
  for (let i = 2; i <= n; i++) {
    dp[i] = dp[i - 1] + dp[i - 2];
    frames.push({ i, dp: dp.slice(),
                  caption: `tile ${i} lights from tiles ${i - 1} and ${i - 2}: `
                    + `${dp[i - 1]} + ${dp[i - 2]} = ${dp[i]}` });
  }
  return {
    title: 'DYNAMIC PROGRAMMING — solved tiles stay lit and get reused',
    frames,
    draw(ctx, w, h, f) {
      const cw = Math.min(56, (w - 40) / (n + 1));
      const x0 = (w - cw * (n + 1)) / 2;
      const y = h / 2 - 26;
      for (let i = 0; i <= n; i++) {
        const lit = f.dp[i] !== undefined;
        const source = i === f.i - 1 || i === f.i - 2;
        const current = i === f.i;
        cell(ctx, x0 + i * cw + 2, y, cw - 4, 52,
             current ? '#7c6430' : source ? '#4a3f20' : lit ? '#2a2840' : '#161422',
             current ? '#ffd97a' : source ? '#c8a33d' : '#3a3550');
        label(ctx, lit ? String(f.dp[i]) : '?', x0 + i * cw + cw / 2, y + 20,
              lit ? '#ffe8a0' : '#5a5a70');
        label(ctx, String(i), x0 + i * cw + cw / 2, y + 66, '#6a6a80');
      }
    },
  };
}

function monotonicDeque(data = [1, 3, -1, -3, 5, 3, 6, 7], k = 3) {
  const frames = [];
  const dq = [];
  const out = [];
  for (let i = 0; i < data.length; i++) {
    const evicted = [];
    while (dq.length && data[dq[dq.length - 1]] <= data[i]) evicted.push(dq.pop());
    dq.push(i);
    if (dq[0] <= i - k) dq.shift();
    if (i >= k - 1) out.push(data[dq[0]]);
    frames.push({
      i, dq: dq.slice(), out: out.slice(), evicted,
      caption: evicted.length
        ? `${evicted.map(j => data[j]).join(', ')} can never be a future maximum — discard`
        : `index ${i} joins the candidates`,
    });
  }
  return {
    title: 'MONOTONIC DEQUE — only useful candidates survive',
    frames,
    draw(ctx, w, h, f) {
      const cw = Math.min(48, (w - 40) / data.length);
      const x0 = (w - cw * data.length) / 2;
      const y = h * 0.22;
      data.forEach((v, i) => {
        const inWindow = i > f.i - k && i <= f.i;
        const candidate = f.dq.includes(i);
        cell(ctx, x0 + i * cw + 2, y, cw - 4, 40,
             candidate ? '#2a4a5a' : inWindow ? '#262438' : '#161422',
             candidate ? '#7ec8ff' : '#3a3550');
        label(ctx, String(v), x0 + i * cw + cw / 2, y + 20,
              candidate ? '#d8f0ff' : inWindow ? '#9a9ab0' : '#55556a');
      });
      label(ctx, 'candidates: ' + f.dq.map(i => data[i]).join(' > '),
            w / 2, y + 74, '#7ec8ff');
      label(ctx, 'output: ' + f.out.join(', '), w / 2, y + 100, '#8fd07a');
    },
  };
}

function binarySearchViz(n = 16, target = 11) {
  const data = Array.from({ length: n }, (_, i) => i);
  const frames = [];
  let lo = 0, hi = n - 1;
  while (lo <= hi) {
    const mid = (lo + hi) >> 1;
    frames.push({ lo, hi, mid,
                  caption: data[mid] === target ? `found at ${mid}`
                    : data[mid] < target ? `${data[mid]} < ${target} — discard the left half`
                      : `${data[mid]} > ${target} — discard the right half` });
    if (data[mid] === target) break;
    if (data[mid] < target) lo = mid + 1; else hi = mid - 1;
  }
  return {
    title: 'BINARY SEARCH — half the world disappears each step',
    frames,
    draw(ctx, w, h, f) {
      const cw = Math.min(36, (w - 40) / n);
      const x0 = (w - cw * n) / 2;
      const y = h / 2 - 20;
      data.forEach((v, i) => {
        const alive = i >= f.lo && i <= f.hi;
        const mid = i === f.mid;
        cell(ctx, x0 + i * cw + 1, y, cw - 2, 40,
             mid ? '#5a4a2a' : alive ? '#2a2840' : '#131120',
             mid ? '#ffd97a' : alive ? '#3a3550' : '#1c1a28');
        label(ctx, String(v), x0 + i * cw + cw / 2, y + 20,
              mid ? '#ffe8a0' : alive ? '#9a9ab0' : '#3a3a4a');
      });
      label(ctx, `lo ${f.lo}   mid ${f.mid}   hi ${f.hi}   target ${target}`,
            w / 2, h - 26, '#e8c37d');
    },
  };
}

function prefixSumViz(data = [3, 1, 4, 1, 5, 9, 2]) {
  const frames = [];
  const prefix = [0];
  for (let i = 0; i < data.length; i++) {
    prefix.push(prefix[i] + data[i]);
    frames.push({ i, prefix: prefix.slice(),
                  caption: `checkpoint ${i + 1}: running total ${prefix[i + 1]}` });
  }
  frames.push({ i: data.length - 1, prefix: prefix.slice(), query: [2, 5],
                caption: `sum(2..5) = prefix[6] - prefix[2] = ${prefix[6]} - ${prefix[2]} = ${prefix[6] - prefix[2]}` });
  return {
    title: 'PREFIX SUM — pay once, answer every range instantly',
    frames,
    draw(ctx, w, h, f) {
      const n = data.length;
      const cw = Math.min(56, (w - 40) / n);
      const x0 = (w - cw * n) / 2;
      const y = h * 0.28;
      data.forEach((v, i) => {
        const inQuery = f.query && i >= f.query[0] && i <= f.query[1];
        cell(ctx, x0 + i * cw + 2, y, cw - 4, 36,
             inQuery ? '#4a3f20' : i <= f.i ? '#2a2840' : '#161422',
             inQuery ? '#c8a33d' : '#3a3550');
        label(ctx, String(v), x0 + i * cw + cw / 2, y + 18, '#c8c8d8');
        if (f.prefix[i + 1] !== undefined) {
          label(ctx, String(f.prefix[i + 1]), x0 + i * cw + cw / 2, y + 60, '#e8c37d');
        }
      });
      label(ctx, 'values', x0 - 12, y + 18, '#6a6a80', 'right');
      label(ctx, 'prefix', x0 - 12, y + 60, '#6a6a80', 'right');
    },
  };
}

function matrixViz() {
  const base = [[1, 2, 3], [4, 5, 6], [7, 8, 9]];
  const transposed = base[0].map((_, c) => base.map(r => r[c]));
  const rotated = transposed.map(r => r.slice().reverse());
  return {
    title: 'MATRIX ROTATION — transpose, then mirror',
    frames: [
      { grid: base, caption: 'the original grid' },
      { grid: transposed, caption: 'transpose: flip across the main diagonal' },
      { grid: rotated, caption: 'reverse each row: the rotation is complete' },
    ],
    draw(ctx, w, h, f) {
      const n = f.grid.length;
      const cw = Math.min(60, (h - 110) / n, (w - 40) / n);
      const x0 = (w - cw * n) / 2, y0 = h * 0.25;
      for (let r = 0; r < n; r++) {
        for (let c = 0; c < n; c++) {
          cell(ctx, x0 + c * cw + 2, y0 + r * cw + 2, cw - 4, cw - 4,
               '#2a2840', '#5a5a80');
          label(ctx, String(f.grid[r][c]), x0 + c * cw + cw / 2, y0 + r * cw + cw / 2,
                '#d8d8e8');
        }
      }
    },
  };
}

function arrayScan(data = [4, 8, 15, 16, 23, 42]) {
  const frames = [];
  let total = 0;
  data.forEach((v, i) => {
    total += v;
    frames.push({ i, total, caption: `accumulator ${total - v} + ${v} = ${total}` });
  });
  return {
    title: 'ONE PASS — a single accumulator',
    frames,
    draw(ctx, w, h, f) {
      const cw = Math.min(60, (w - 40) / data.length);
      const x0 = (w - cw * data.length) / 2;
      const y = h / 2 - 20;
      data.forEach((v, i) => {
        const done = i <= f.i;
        cell(ctx, x0 + i * cw + 2, y, cw - 4, 40,
             i === f.i ? '#5a4a2a' : done ? '#2a2840' : '#161422',
             i === f.i ? '#ffd97a' : '#3a3550');
        label(ctx, String(v), x0 + i * cw + cw / 2, y + 20,
              done ? '#e8e8f0' : '#55556a');
      });
      label(ctx, `total ${f.total}`, w / 2, h - 26, '#8fd07a');
    },
  };
}

const BUILDERS = {
  sliding_window: slidingWindow,
  two_pointer: twoPointer,
  bfs: bfsWave,
  dfs: dfsPath,
  stack: stackViz,
  monotonic_stack: stackViz,
  queue: queueViz,
  tree: treeViz,
  hash_map: hashMapViz,
  recursion: recursionViz,
  dp: dpViz,
  monotonic_deque: monotonicDeque,
  binary_search: binarySearchViz,
  prefix_sum: prefixSumViz,
  matrix: matrixViz,
  array_scan: arrayScan,
};

export function hasViz(kind) { return Boolean(BUILDERS[kind]); }

export class Visualiser {
  constructor(canvas, captionEl) {
    this.canvas = canvas;
    this.ctx = canvas.getContext('2d');
    this.captionEl = captionEl;
    this.viz = null;
    this.frame = 0;
    this.timer = null;
    this.playing = false;
    this.speed = 1100;
  }

  load(kind) {
    const builder = BUILDERS[kind] || BUILDERS.array_scan;
    this.viz = builder();
    this.frame = 0;
    this.render();
    return this.viz.title;
  }

  render() {
    if (!this.viz) return;
    const dpr = window.devicePixelRatio || 1;
    const rect = this.canvas.getBoundingClientRect();
    const w = Math.max(320, rect.width), h = Math.max(220, rect.height);
    this.canvas.width = w * dpr;
    this.canvas.height = h * dpr;
    const ctx = this.ctx;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.imageSmoothingEnabled = false;
    ctx.fillStyle = '#0e0c18';
    ctx.fillRect(0, 0, w, h);
    label(ctx, this.viz.title, w / 2, 20, '#a89aff');
    const f = this.viz.frames[Math.min(this.frame, this.viz.frames.length - 1)];
    if (f) {
      this.viz.draw(ctx, w, h, f);
      if (this.captionEl) this.captionEl.textContent = f.caption || '';
    }
  }

  step(delta = 1) {
    if (!this.viz) return;
    this.frame = Math.max(0, Math.min(this.viz.frames.length - 1, this.frame + delta));
    this.render();
  }

  play() {
    if (!this.viz) return;
    this.stop();
    this.playing = true;
    const tick = () => {
      if (!this.playing) return;
      this.frame = (this.frame + 1) % this.viz.frames.length;
      this.render();
      this.timer = setTimeout(tick, this.speed);
    };
    this.timer = setTimeout(tick, this.speed);
  }

  stop() {
    this.playing = false;
    if (this.timer) clearTimeout(this.timer);
    this.timer = null;
  }
}
