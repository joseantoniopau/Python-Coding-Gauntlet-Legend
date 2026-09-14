/* Serialize snapshots so a slow save cannot overwrite a newer edit. */
export function createDraftWriter({snapshot, save, status}) {
  let timer=null, tail=Promise.resolve(), acknowledged='';
  const key=row=>JSON.stringify(row);
  const storageKey=row=>row?.encounter_started_at ? `gauntlet-draft-v1:${row.problem_id}:${row.encounter_started_at}` : null;
  function recover(row){
    try{const k=storageKey(row),saved=k&&JSON.parse(localStorage.getItem(k));
      return saved&&Date.now()-saved.at<7*86400000?saved.row:null;
    }catch(_){return null;}
  }
  function preserve(row){
    try{const k=storageKey(row);if(!k)return false;
      localStorage.setItem(k,JSON.stringify({row,at:Date.now()}));
      const old=Object.keys(localStorage).filter(k=>k.startsWith('gauntlet-draft-v1:')).map(k=>({k,at:JSON.parse(localStorage.getItem(k))?.at||0})).sort((a,b)=>b.at-a.at);
      for(const item of old.slice(10))localStorage.removeItem(item.k);
      return true;
    }catch(_){return false;}
  }
  function flush(){
    clearTimeout(timer);timer=null;
    const row=snapshot();if(!row)return tail;
    const stamp=key(row);if(stamp===acknowledged)return tail;
    if(row.code.length>20000||row.explanation.length>4000){status('Draft too long to save');return tail;}
    preserve(row);
    status('Saving draft…');
    tail=tail.catch(()=>{}).then(async()=>{
      const result=await save(row);
      if(!result?.saved)throw new Error(result?.message||result?.error||'Save was refused');
      acknowledged=stamp;
      try{if(key(recover(row))===stamp)localStorage.removeItem(storageKey(row));}catch(_){}
      if(key(snapshot())===stamp)status('Draft saved on this computer');
    }).catch(error=>{if(key(snapshot())===stamp)status('Draft not saved — '+error.message);});
    return tail;
  }
  return {
    changed(){const row=snapshot();if(!row)return;const copied=row.code.length<=20000&&row.explanation.length<=4000&&preserve(row);status(copied?'Recovery copy saved in this browser · syncing…':'Unsaved changes');clearTimeout(timer);timer=setTimeout(flush,600);},
    flush,
    recover,
    reset(saved=false){clearTimeout(timer);timer=null;acknowledged=saved?key(snapshot()):'';status(saved?'Draft restored from this computer':'');},
  };
}
