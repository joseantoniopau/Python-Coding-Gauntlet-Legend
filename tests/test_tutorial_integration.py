"""Tutor persistence and measured-run boundaries, through Game and real HTTP."""
from __future__ import annotations

import copy
import json
import shutil
import subprocess
import threading
import urllib.error
import urllib.request

from base import GameTest, REPO
from gauntlet import config, tutorial


class TutorialIntegration(GameTest):
    def setUp(self):
        super().setUp()
        self.g = self.game()
        self.addCleanup(self.g.conn.close)

    def test_old_save_gets_defaults_without_losing_progress(self):
        self.g.state.pop("lessons", None)
        self.g.state["settings"].pop("cues", None)
        self.g.state["player"]["gold"] = 173
        self.g.save()
        loaded = self.game()
        self.addCleanup(loaded.conn.close)
        self.assertEqual(loaded.state["lessons"], tutorial.new_lesson_state())
        self.assertIs(loaded.state["settings"]["cues"], True)
        self.assertEqual(loaded.state["player"]["gold"], 173)

    def test_preview_does_not_latch_and_acknowledgement_persists_once(self):
        before = copy.deepcopy(self.g.state)
        view = self.g.lessons()
        self.assertEqual(self.g.state, before)
        self.assertEqual(view["cue"]["controls"], tutorial.cue_registry())
        self.assertEqual(len(view["beats"]), len(tutorial.BEATS))
        self.assertFalse(view["run_open"])
        for row in tutorial.BEATS:
            shown = self.g.lesson(row.id)
            self.assertEqual(shown["id"], row.id)
            self.assertFalse(shown["blocks_input"])
            after = copy.deepcopy(self.g.state)
            self.assertEqual(self.g.lesson(row.id), {})
            self.assertEqual(self.g.state, after)
        loaded = self.game()
        self.addCleanup(loaded.conn.close)
        self.assertEqual(loaded.lessons()["counts"]["pending"], 0)
        # Tutor bookkeeping is not evidence of Python mastery or combat success.
        for key in ("skills", "schedule", "solved_ids", "player", "stats"):
            self.assertEqual(self.g.state[key], before[key], key)

    def test_cue_retirement_reset_and_unknown_ids(self):
        before = copy.deepcopy(self.g.state)
        for invalid in ("unknown", [], None):
            self.assertEqual(self.g.lesson(invalid), {})
            self.assertEqual(self.g.lesson_note("used", invalid), {})
        self.assertEqual(self.g.lesson_note("invalid", "run"), {})
        self.assertEqual(self.g.state, before)
        for index in range(3):
            note = self.g.lesson_note("used", "run")
            self.assertEqual(note["used"], index + 1)
        self.assertTrue(note["retired"])
        self.g.lesson("the_square")
        self.assertEqual(self.g.lessons_forget()["cleared"]["beats"], 1)
        self.assertEqual(self.g.state["lessons"], tutorial.new_lesson_state())

    def test_all_open_run_shapes_refuse_all_writers_and_hide_prose(self):
        for fields in ({"interview": {"id": "between-questions"}},
                       {"exam": {"id": "practical"}},
                       {"encounter": {"problem_id": "fixture", "mode": config.MODE_INTERVIEW}},
                       {"encounter": ["unreadable"]}):
            with self.subTest(fields=fields):
                self.g.state.update(interview=None, exam=None, encounter=None)
                self.g.state.update(fields)
                before = copy.deepcopy(self.g.state)
                self.assertTrue(self.g._run_is_open())
                self.assertEqual(self.g.lesson("the_trials"), {})
                self.assertEqual(self.g.lesson_note("shown", "run"), {})
                self.assertEqual(self.g.lessons_forget(), {})
                view = self.g.lessons()
                self.assertTrue(view["run_open"])
                self.assertFalse(view["available"])
                self.assertEqual(view["beats"], [])
                self.assertEqual(self.g.state, before)

    def _server(self):
        from gauntlet import server
        server.set_game(self.g)
        self.addCleanup(server.set_game, None)
        # Port zero gives this fixture its own socket; it cannot reuse the game.
        httpd = server.Server(("127.0.0.1", 0), server.Handler)
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(httpd.server_close)
        self.addCleanup(httpd.shutdown)
        return f"http://127.0.0.1:{httpd.server_address[1]}", server.TOKEN

    def _request(self, endpoint, path, body=None, token=None):
        url, auth = endpoint
        request = urllib.request.Request(url + path,
            data=None if body is None else json.dumps(body).encode(),
            headers={"X-Gauntlet-Token": auth if token is None else token,
                     "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                return response.status, json.loads(response.read())
        except urllib.error.HTTPError as error:
            with error:
                return error.code, json.loads(error.read())

    def test_real_http_preview_acknowledgement_and_validation(self):
        endpoint = self._server()
        before = copy.deepcopy(self.g.state)
        status, preview = self._request(endpoint, "/api/lessons")
        self.assertEqual(status, 200)
        self.assertEqual(preview["cue"]["controls"], tutorial.cue_registry())
        self.assertEqual(self.g.state, before)
        status, ack = self._request(endpoint, "/api/lesson", {"id": "the_square"})
        self.assertEqual(status, 200)
        self.assertTrue(ack["first_time"])
        self.assertEqual(self._request(endpoint, "/api/lesson", {"id": "the_square"}), (200, {}))
        status, note = self._request(endpoint, "/api/lesson/note", {"kind": "used", "id": "run"})
        self.assertEqual(status, 200)
        self.assertEqual(note["used"], 1)
        self.assertEqual(self._request(endpoint, "/api/lesson", {"id": []})[0], 400)
        self.assertEqual(self._request(endpoint, "/api/lesson/note", {"id": "run"})[0], 400)
        self.assertEqual(self._request(endpoint, "/api/lesson", {"id": "the_fight"}, token="wrong")[0], 403)
        status, forgotten = self._request(endpoint, "/api/lesson/forget", {})
        self.assertEqual(status, 200)
        self.assertEqual(forgotten["cleared"]["beats"], 1)

    def test_http_world_screen_during_actual_practical_is_closed(self):
        endpoint = self._server()
        status, started = self._request(endpoint, "/api/exam/start", {})
        self.assertEqual(status, 200, started)
        self.g.state["encounter"] = None  # between questions / world screen
        status, dashboard = self._request(endpoint, "/api/state")
        self.assertEqual(status, 200, dashboard)
        self.assertIs(dashboard["run_open"], True)
        before = copy.deepcopy(self.g.state)
        for path, body in (("/api/lesson", {"id": "the_trials"}),
                           ("/api/lesson/note", {"kind": "shown", "id": "run"}),
                           ("/api/lesson/forget", {})):
            self.assertEqual(self._request(endpoint, path, body), (200, {}), path)
        status, view = self._request(endpoint, "/api/lessons")
        self.assertEqual(status, 200)
        self.assertTrue(view["run_open"])
        self.assertEqual(view["beats"], [])
        self.assertEqual(self.g.state, before)


class TutorialClientContract(GameTest):
    @classmethod
    def setUpClass(cls):
        pass  # The JS fixture needs no corpus or database.

    @classmethod
    def tearDownClass(cls):
        pass

    def test_context_delivery_failure_and_cue_boundaries(self):
        if shutil.which("node") is None:
            self.skipTest("Node is unavailable")
        data = {"run_open": False, "available": True, "taught": [],
                "beats": [tutorial.view({}, row.id) for row in tutorial.BEATS],
                "cue": tutorial.cue_state({})}
        script = r'''
import assert from 'node:assert/strict';
globalThis.window = {__GAUNTLET_TOKEN__: ''};
const nodes = new Map(), listeners = new Map();
class Node {
  constructor(selector='') {this.selector=selector;this.isConnected=true;this.disabled=false;this.children=[];
    const names=new Set();this.classList={add:v=>names.add(v),remove:v=>names.delete(v),contains:v=>names.has(v),
      toggle:(v,on)=>on?names.add(v):names.delete(v)};}
  getAttribute(){return null} setAttribute(){}
  getClientRects(){return this.hidden?[]:[{}]}
  closest(s){return s===this.selector?this:null}
  appendChild(n){this.children.push(n);n.parent=this;n.isConnected=true}
  remove(){this.isConnected=false;if(this.parent)this.parent.children=this.parent.children.filter(n=>n!==this)}
}
globalThis.document={body:new Node(),querySelector:s=>nodes.get(s)||null,createElement:()=>new Node(),
  addEventListener:(name,fn)=>listeners.set(name,fn)};
globalThis.getComputedStyle=()=>({display:'block',visibility:'visible'});
const tutor=await import('./web/js/tutor.js');
let time=0,state={screen:'world',encounterId:'',run_open:false,settings:{cues:true},busy:false};
let view=JSON.parse(process.env.TUTOR_VIEW), read=async()=>structuredClone(view), shown=[], acknowledgements=[],notes=[];
const api={lessons:()=>read(),lesson:async id=>{acknowledgements.push(id);return {first_time:true}},
  lessonNote:async(kind,id)=>{notes.push([kind,id]);return {id,shown:1,used:1,retired:false}},
  lessonsForget:async()=>({cleared:{beats:1}})};
tutor.configure({state:()=>state,now:()=>time,api,show:row=>{shown.push(row.id);return true},hide:()=>{}});
tutor.sync({});
assert.equal(await tutor.beat('the_square'),false,'unknown run flag must close guidance');
tutor.sync(view);
let resolve; read=()=>new Promise(r=>resolve=r);
const late=tutor.beat('the_square');state.screen='party';resolve(structuredClone(view));
assert.equal(await late,false);assert.deepEqual(acknowledgements,[],'late preview spent latch');
state.screen='world';
const opening=tutor.beat('the_code_fight');time++;listeners.get('input')();resolve(structuredClone(view));
assert.equal(await opening,false,'opening lesson arrived after the player started typing');
const sealedLate=tutor.beat('the_trials');tutor.sync({run_open:true});resolve(structuredClone(view));
assert.equal(await sealedLate,false,'an old preview reopened a newly sealed run');
assert.equal(document.body.classList.contains('run-open'),true);
tutor.sync(view);
state.screen='world';read=async()=>structuredClone(view);
tutor.configure({show:()=>false});
assert.equal(await tutor.beat('the_square'),false);assert.deepEqual(acknowledgements,[],'rejected render spent latch');
tutor.configure({show:row=>{shown.push(row.id);return true}});
assert.equal(await tutor.beat('the_square'),true);assert.deepEqual(acknowledgements,['the_square']);
assert.equal(await tutor.beat('the_square'),false);tutor.dismiss();
state.run_open=true;tutor.sync({...view,run_open:true});
assert.equal(await tutor.beat('the_trials'),false,'world-screen measured run leaked a lesson');
assert.equal(document.body.classList.contains('run-open'),true);
state.run_open=false;tutor.sync(view);read=async()=>{throw Error('offline')};
assert.equal(await tutor.beat('the_trials'),false);assert.equal(acknowledgements.length,1);
read=async()=>structuredClone(view);state.screen='battle';state.encounterId='code-1';
for(const s of ['#screen-battle','#editor-caption','#btn-run','#btn-submit'])nodes.set(s,new Node(s));
tutor.enterEncounter();time+=9000;await tutor.cue();
assert.equal(nodes.get('#btn-run').children.length,1);assert.deepEqual(notes,[['shown','run']]);
await tutor.used('run');assert.equal(nodes.get('#btn-run').children.length,0);
nodes.get('#btn-submit').disabled=true;time+=9000;
assert.equal(await tutor.cue(),false,'disabled CAST received a cue');
nodes.get('#btn-submit').disabled=false;await tutor.cue();
assert.equal(nodes.get('#btn-submit').children.length,1);
tutor.sync({...view,run_open:true});assert.equal(nodes.get('#btn-submit').children.length,0,'seal left a cue visible');
tutor.leaveEncounter();state.encounterId='mcq-1';tutor.sync(view);
nodes.get('#editor-caption').hidden=true;nodes.get('#btn-run').hidden=true;nodes.get('#btn-submit').hidden=true;
nodes.set('#answer-here',new Node());nodes.set('#mcq-choices .answer-choice',new Node());
nodes.set(view.cue.controls.find(r=>r.id==='trials_tab').selector,new Node());
tutor.enterEncounter();time+=9000;
assert.equal(await tutor.cue(),false,'main-pane MCQ choices do not need a trials-tab cue');
tutor.leaveEncounter();assert.equal(document.body.classList.contains('run-open'),false);
console.log('PASS: preview, did-show latch, failure, seal, disabled controls, main-pane MCQ');
'''
        import os
        result = subprocess.run(["node", "--input-type=module", "-"], input=script,
            text=True, capture_output=True, cwd=REPO, timeout=20,
            env={**os.environ, "TUTOR_VIEW": json.dumps(data)})
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
