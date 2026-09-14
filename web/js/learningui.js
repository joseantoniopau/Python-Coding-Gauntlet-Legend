/* Practice planning and personal evidence. Selection and scoring stay on the server. */
import {api} from './api.js';
import {$, el, esc, HOST, refusalCard} from './uikit.js';

let epoch=0;
export function leave(){epoch++;}
const clock=s=>`${Math.floor(Math.max(0,Number(s)||0)/60)}:${String(Math.floor(Math.max(0,Number(s)||0)%60)).padStart(2,'0')}`;
export const evidenceLabel=kind=>({whole_function:'Whole-function coding',scaffolded:'Scaffolded coding',reading:'Code reading',puzzle:'Guided reasoning',debugging:'Debugging',test_writing:'Test writing',repository:'Repository work',unknown:'Assistance level not recorded'}[kind]||'Assistance level not recorded');
const failed=r=>!r||r.error||r.available===false;
function problem(r){if(failed(r)){HOST.toast('PRACTICE',r?.message||r?.error||'The request could not be completed.','red');return true;}return false;}
async function openNext(button){
  const ticket=epoch;
  button.disabled=true;
  try{const r=await api.practiceNext();if(ticket!==epoch||!button.isConnected||problem(r))return;await HOST.refresh();if(ticket!==epoch||!button.isConnected)return;HOST.onEncounter(r);}
  catch(e){HOST.toast('PRACTICE',e.message,'red');}
  finally{if(button.isConnected)button.disabled=false;}
}
function planSummary(plan){
  const s=plan.summary||{};
  return `<p class="practice-counts"><b>${plan.completed_count||0}</b> encounters · ${s.solved||0} solved · ${s.assisted||0} assisted · ${s.independent||0} independent coding · ${s.reading||0} reading</p>
    <p class="muted">${clock(plan.elapsed_seconds)} practiced of a ${plan.minutes}-minute intention. ${s.coach?esc(s.coach):'The time is a guide. Finish at a natural stopping point.'}</p>`;
}
export async function paintPractice(){
  HOST.panel('THE NEXT EXPEDITION','<div id="practice-page" class="learning-page"><p>Reading your practice plan…</p></div>');
  const ticket=++epoch, host=$('#practice-page');
  let r;try{r=await api.practice();}catch(e){if(host.isConnected)host.textContent=e.message;return;}
  if(ticket!==epoch||!host.isConnected)return;
  if(failed(r)){host.innerHTML=refusalCard(r);return;}
  const plan=r.plan;
  const active=plan&&plan.status!=='finished';
  host.innerHTML=`<p class="learning-lede">Choose a manageable session. Review an idea, work through a fresh challenge, and leave with a note about what changed.</p>
    ${active?`<section class="frame learning-card">
      <div class="section-title">${esc(plan.kind==='rehearsal'?'COACHED REHEARSAL':'YOUR EXPEDITION')} · ${esc(plan.status)}</div>
      ${planSummary(plan)}
      <p>Current phase: ${esc(plan.phase)}. ${plan.active_problem_id?'Your current encounter can be resumed.':''}</p>
      <div class="actions"><button class="btn primary" id="practice-continue">${plan.status==='paused'?'RESUME PRACTICE':plan.active_problem_id?'BACK TO MY ENCOUNTER':'NEXT ENCOUNTER'}</button>
      ${plan.status==='active'?'<button class="btn" data-practice-action="pause">PAUSE SESSION</button>':''}
      <button class="btn" data-practice-action="finish">FINISH HERE</button></div>
    </section>`:''}
    ${plan?.status==='finished'?`<section class="frame learning-card"><h3>SESSION COMPLETE</h3>${planSummary(plan)}<p>Take a moment to recall the idea without the code in front of you.</p><button class="btn" id="practice-reflect">WRITE IN MY GRIMOIRE</button></section>`:''}
    ${!active?`<form id="practice-form" class="frame learning-card">
      <div class="learning-fields">
      <label>Time intention<select name="minutes">${(r.options?.minutes||[10,20,40]).map(n=>`<option value="${n}" ${n===20?'selected':''}>${n} minutes</option>`).join('')}</select></label>
      <label>Session type<select name="kind">${(r.options?.kinds||[]).map(k=>`<option value="${esc(k.id)}">${esc(k.label)}</option>`).join('')}</select></label>
      <label>What would help today?<select name="intent">${(r.options?.intents||[]).map(k=>`<option value="${esc(k.id)}">${esc(k.label)}</option>`).join('')}</select></label></div>
      <p id="practice-intent" class="muted"></p>
      <p class="muted">Rehearsal includes coaching and uses practice material. Your sealed interview assessment has its own clock and report.</p>
      <button class="btn primary" type="submit">BEGIN MY SESSION</button>
    </form>`:''}
    <div class="actions"><button class="btn" id="practice-journal">PERSONAL GRIMOIRE</button><button class="btn" id="practice-world">RETURN TO THE WORLD</button></div>
    ${(r.history||[]).length?`<h3>RECENT EXPEDITIONS</h3>${r.history.slice(0,6).map(p=>`<details class="frame learning-card"><summary>${esc(p.kind)} · ${p.minutes} minutes · ${p.completed_count||0} encounters</summary>${planSummary(p)}</details>`).join('')}`:''}`;
  $('#practice-journal').onclick=()=>HOST.go('journal');
  $('#practice-world').onclick=()=>HOST.back();
  const reflect=$('#practice-reflect');if(reflect)reflect.onclick=()=>HOST.go('journal');
  const next=$('#practice-continue');if(next)next.onclick=async()=>{
    if(plan.status==='paused'){next.disabled=true;try{if(problem(await api.practiceAction('resume'))){next.disabled=false;return;}}catch(e){HOST.toast('PRACTICE',e.message,'red');next.disabled=false;return;}}
    if(ticket!==epoch||!next.isConnected)return;
    await openNext(next);
  };
  host.querySelectorAll('[data-practice-action]').forEach(button=>button.onclick=async()=>{
    button.disabled=true;try{const result=await api.practiceAction(button.dataset.practiceAction);if(ticket!==epoch||!button.isConnected||problem(result))return;await HOST.refresh();if(ticket!==epoch||!button.isConnected)return;await paintPractice();}catch(e){HOST.toast('PRACTICE',e.message,'red');}finally{if(button.isConnected)button.disabled=false;}
  });
  const form=$('#practice-form');if(form){
    const describe=()=>{$('#practice-intent').textContent=(r.options?.intents||[]).find(i=>i.id===form.elements.intent.value)?.description||'';};
    form.elements.intent.onchange=describe;describe();
    form.onsubmit=async event=>{
      event.preventDefault();const button=form.querySelector('button');button.disabled=true;
      try{const result=await api.practiceStart({minutes:Number(form.elements.minutes.value),kind:form.elements.kind.value,intent:form.elements.intent.value});if(ticket!==epoch||!button.isConnected||problem(result))return;await HOST.refresh();if(ticket!==epoch||!button.isConnected)return;await openNext(button);}catch(e){HOST.toast('PRACTICE',e.message,'red');}finally{if(button.isConnected)button.disabled=false;}
    };
  }
}

export async function paintJournal(){
  HOST.panel('MY GRIMOIRE','<div id="journal-page" class="learning-page"><p>Opening your notes and learning evidence…</p></div>');
  const ticket=++epoch, host=$('#journal-page');let r;
  try{r=await api.journal();}catch(e){if(host.isConnected)host.textContent=e.message;return;}
  if(ticket!==epoch||!host.isConnected)return;
  if(failed(r)){host.innerHTML=refusalCard(r);return;}
  const families=[...(r.families||[])].sort((a,b)=>(b.attempt_count||0)-(a.attempt_count||0)||a.name.localeCompare(b.name));
  host.innerHTML=`<p class="learning-lede">Your own code, reflections, and delayed reviews. Familiarity, guided work, independent coding, and retention remain separate evidence.</p>
    <label class="journal-picker">Concept<select id="journal-family">${families.map(f=>`<option value="${esc(f.id)}">${esc(f.name)} · ${f.attempt_count||0} attempts</option>`).join('')}</select></label>
    <div id="journal-entry"></div>`;
  const picker=$('#journal-family');
  function paintFamily(){
    const f=families.find(f=>f.id===picker.value);const body=$('#journal-entry');if(!f){body.textContent='A concept page appears when the curriculum is available.';return;}
    const retention=f.retention||{},due=Number(f.due_at);
    body.innerHTML=`<section class="frame learning-card"><h3>${esc(f.name)}</h3>
      <p>Memory review: <b>${esc(String(retention.status||'not_started').replaceAll('_',' '))}</b>${Number.isFinite(due)&&due>0?` · next review ${esc(new Date(due*1000).toLocaleDateString())}`:''}.</p>
      <p class="muted">${retention.reviews||0} recorded reviews · ${retention.lapses||0} lapses. A lapse shows what to revisit; it does not erase your notes.</p>
      <label>What I understand now<textarea id="journal-note" maxlength="4000" rows="5" placeholder="Explain the idea. Which input surprised you? What will you try from memory next time?">${esc(f.notes||'')}</textarea></label>
      <div class="actions"><button class="btn" id="journal-save">SAVE MY NOTE</button><span id="journal-save-state" role="status"></span></div>
    </section><h3>MY ATTEMPTS</h3>${(f.attempts||[]).length?(f.attempts||[]).map(a=>`<details class="frame learning-card">
      <summary>${a.solved?'✓':'↻'} ${esc(a.title||a.problem_id)} · ${esc(evidenceLabel(a.evidence_kind))}</summary>
      <p>${a.solved?'Tests passed':'Still practicing'} · ${clock(a.seconds)} · ${a.hints_used||0} hints${a.served_rung?` · scaffold rung ${a.served_rung}`:''}${a.is_retest?' · delayed review':''}${a.practice_kind?` · ${esc(a.practice_kind)}`:''}.</p>
      ${a.root_cause?`<p>Next focus: ${esc(a.root_cause.replaceAll('_',' ').toLowerCase())}.</p>`:''}
      ${a.submitted_code?`<pre class="journal-code"><code>${esc(a.submitted_code)}</code></pre>`:'<p class="muted">No source code was recorded for this attempt.</p>'}
    </details>`).join(''):'<p>No attempt recorded for this concept yet.</p>'}`;
    const note=$('#journal-note'),save=$('#journal-save'),status=$('#journal-save-state');note.oninput=()=>{status.textContent='Unsaved changes';};
    save.onclick=async()=>{save.disabled=true;status.textContent='Saving…';try{const result=await api.journalNote(f.id,note.value);if(problem(result)){status.textContent='Not saved';return;}f.notes=result.notes;status.textContent='Saved locally';}catch(e){status.textContent='Not saved — '+e.message;}finally{save.disabled=false;}};
  }
  picker.onchange=paintFamily;paintFamily();
}
