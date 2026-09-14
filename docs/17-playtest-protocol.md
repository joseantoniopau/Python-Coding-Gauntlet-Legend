# Human playtest protocol

Status: protocol prepared; **no human participants have been tested and no human results are available**. Automated tests, screenshots and an agent operating the browser establish narrower engineering evidence. They do not establish enjoyment, learning, accessibility conformance or a production-ready experience. In particular, the automated “reason to continue” check in `06-acceptance.md` proves that progression mechanisms exist; it does not prove that a player wants to continue.

This protocol tests whether the original SNES-inspired, painted metal-fantasy presentation supports a comfortable Python learning loop. The desired outcome is voluntary return and durable understanding, with a clear stopping point. Long sessions alone are not a success measure.

## Preparation and recording

Run an initial moderated pilot with six beginners and six intermediate Python learners. This is a diagnostic sample, not a statistically representative study. Include participants who use keyboard navigation, enlarged text, reduced motion or screen readers; record access needs without treating any one participant as representative of a group. Recruit a separate accessibility review if those needs are not represented.

Use a disposable profile and isolated data directory for each person. Record commit, corpus build, browser/version, operating system, CPU/GPU, display refresh rate, viewport, pixel ratio, input method and settings. The production save and assessment holdout corpus must remain untouched. Use an ordinary fresh save for beginners. For intermediate tasks, prepare a documented training save with eligible code content and an existing due review, using normal unsealed progression. Do not fabricate an assessment score or show hidden tests.

Before the task, explain that we are testing the game, not judging the person; they can stop at any time. Obtain consent separately for screen/audio recording. Do not record unrelated windows, identifying account details or other people's code. Record only a participant ID in the results table. Agree on retention and deletion before collecting recordings.

Use two minutes before the timed task for a small baseline exercise and three minutes after it for questions. The gameplay task itself is ten minutes. Ask participants to say what they expect when they act, but do not explain controls or solve the problem for them. After 30 seconds of being stuck, ask “What are you trying to do?” If they still cannot proceed, offer one neutral navigation hint, mark it as moderator assistance and preserve the failure in the record. Do not speed them through learning steps to finish the script.

For every attempt record the actual problem ID, encounter kind, served rung, starter supplied, hints/coaching/reference access, RUN/CAST actions, result, code and explanation. Reading a correct option, filling a blank and writing a function are separate evidence categories. Existing records with unknown evidence remain unknown.

## Beginner: ten minutes from the title screen

Eligibility: can use a computer but has not independently written Python functions. Baseline: ask what a short arithmetic `print` expression displays and whether `print` and `return` mean the same thing. Record the answer without teaching it yet.

| Time | Participant task | Observe and record |
| --- | --- | --- |
| 0:00–2:00 | Start a game, find the next action and answer the first reading encounter. Explain what the buttons will do before selecting one. | Time to an actionable question; whether all choices are visible; whether a lesson is read, dismissed or obstructive; guesses caused by unclear layout; keyboard focus. A wrong Python answer is not automatically a UI failure. |
| 2:00–5:00 | Follow the game to its first code encounter. Read the supplied starter and make the requested change. Use RUN once, inspect the feedback, then decide when to CAST. | Whether starter instructions match the served rung; ability to distinguish running public examples from a graded submission; legibility of code and errors; whether the outcome accurately describes reading, scaffolding or independent code. If progression has not reached code, keep observing and report this step as not reached. |
| 5:00–7:00 | Use FOCUS VIEW, edit one line, return to the battle view, then repair an error or test an additional input. | Buffer and cursor survival, accidental character insertion, which feedback causes a useful edit, whether animation draws attention away from the task, assistance used. |
| 7:00–9:00 | Find MY GRIMOIRE and describe what was learned in one sentence. Save that sentence beside the relevant family; locate the recent attempt. | Whether the participant can find their own code and tell a personal note from a worked reference; whether a reading win is mistaken for proof of independent coding. |
| 9:00–10:00 | Stop at a point of their choice. Say what they would do next and how they would return to unfinished work. | Natural stopping point, perceived obligation to continue, confidence about saving. Do not require another encounter or penalize stopping. |

Ask afterwards: “What does RUN do? What does CAST do? What can you now do in Python? What made you want to continue or stop? Which screen was hardest to read?” Ask them to locate their unfinished encounter after a reload as a separate recovery check, without extending the ten-minute task result.

## Intermediate: ten-minute rehearsal and recovery

Eligibility: can write a function with a loop or collection and has some interview preparation experience. Baseline: a small family-matched code problem and one edge-case explanation, without game assistance. Use a different surface example from the later recall tasks.

| Time | Participant task | Observe and record |
| --- | --- | --- |
| 0:00–1:00 | Open PRACTICE EXPEDITIONS. Choose a ten-minute rehearsal and a practice intent, then explain why the next task was selected. | Whether duration is understood as advisory; whether review/weakest/new choices and the selection reason are meaningful; whether rehearsal is understood to provide coaching and not award measured transfer credit. |
| 1:00–4:00 | Solve the selected code task. Before submitting, use TRACE CURRENT CODE with a public case and inspect a variable at a chosen line. | Whether the trace matches the participant's actual current code; visible case identity; line/stack/locals readability; whether truncation or runtime errors are understood. Distinguish this from a prepared algorithm demonstration. |
| 4:00–6:00 | Submit code and explain one invariant, one boundary case and the actual time/space costs. Read the communication feedback. | Useful revision caused by feedback; whether topic coverage is mistaken for semantic proof; whether Python allocations are counted honestly. Correct code and a weak explanation remain separate observations. |
| 6:00–8:00 | Begin the next eligible encounter, make an unfinished edit, wait for “saved,” pause, reload and resume. | Exact draft/explanation/rung restoration; no duplicated completion or reward; paused time excluded; an interrupted network request must not produce a false saved label. |
| 8:00–10:00 | Finish or pause the session and inspect MY GRIMOIRE. Explain the difference between this rehearsal, a due review and a sealed interview. Choose a sensible next session. | Summary accuracy, understandable completion count, retention language, confidence about stopping and returning. Record remaining time and unanswered work, not an artificial perfect finish. |

Use a separate five-minute follow-up on the prepared profile for a boss rematch or Mini-Repo; do not cram both into the ten-minute task. For a rematch, ask the participant to identify the changed input/output or resource constraint before coding and test one newly relevant case. For a Mini-Repo, ask them to state a hypothesis, cite a file/line, inspect a caller, make a focused change and explain one regression test. Record whether the game supported investigation rather than guessing a single edited line. Unlocked variants must remain practice evidence.

## Learning and engagement follow-up

Offer a short follow-up at 24–48 hours and again at seven days. Participation and reminders must be opt-in; missing sessions are missing data, not incorrect answers. Before allowing the journal, starter or hints, ask for a fresh function from a preauthored parallel exercise and a brief explanation of an edge case. Use equivalent family and difficulty with changed examples, not the memorized game prompt. The study packet must not copy the game's sealed assessment corpus.

Score three dimensions separately: code correctness against documented cases (0 incorrect, 1 partial, 2 correct), independent explanation (0 incorrect, 1 plausible but incomplete, 2 coherent with the code), and adaptation to the changed case (0 fails, 1 partial, 2 succeeds). A second reviewer should check disagreements and every claimed independent success. Preserve raw code, not just the score. Record assistance after the unaided attempt separately. Improvement from baseline with unassisted delayed success is evidence consistent with learning; this small uncontrolled pilot cannot establish that the game caused the improvement.

Record voluntary return, a one-to-five desire-to-return rating, session satisfaction, perceived pressure to continue, and the participant's own reason for returning. Ask whether they returned for learning, story, collection, habit or another reason. Report actual numerator/denominator and attrition for each measure. Never substitute XP, time spent, daily streaks or automatic SRS scheduling for demonstrated retention.

Proposed pilot decision thresholds: at least five of six people in each cohort can find the next action and a stopping/resume path without moderator help; at least five of six beginners distinguish RUN from CAST after play; at least five of six intermediate learners distinguish rehearsal from sealed assessment. Use every repeated failure to prioritize a fix. These small-sample thresholds guide iteration, not a marketing claim. No numerical learning-uplift target is set before a baseline and follow-up data exist.

## Accessibility and presentation checks

Run these checks separately from the timed learning sessions. A failed essential path blocks a general accessibility claim, regardless of the average participant rating.

| Check | Proposed acceptance and measurement |
| --- | --- |
| Text and state contrast | Measure actual foreground/background pairs, including disabled, error, selection, focus and code tokens. Ordinary text reaches 4.5:1; qualifying large text reaches 3:1. Meaningful UI boundaries and state indicators reach 3:1 where required. Do not infer compliance from palette names. See [WCAG contrast minimum](https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum) and [WCAG 2.2](https://www.w3.org/TR/WCAG22/). |
| Keyboard path | Complete title → reading answer → code edit → RUN → CAST → result → journal → pause/resume with only the keyboard. Focus is visible, never lost behind overlays, and returns to the invoking control. Test Tab indentation and the editor's escape-to-navigation behavior. No unintended keystroke enters code after a menu action. |
| Zoom and layout | At 1280×800 and 200% browser zoom, every essential instruction and action remains reachable. Check reflow at a 320 CSS-pixel equivalent width; code may scroll in its own pane, while prose and navigation remain readable. Repeat with a long traceback and long result. Document any supported-device limitation explicitly. |
| Targets | Measure pointer controls against the 24×24 CSS-pixel minimum or the standard's spacing exceptions; use larger targets for primary answers and actions where possible. See [WCAG target size minimum](https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum). |
| Reduced motion and sound off | Repeat travel, damage, victory, all cinematic controls and a boss introduction. No camera shake, mandatory flashes or motion-only explanation; effects and outcomes remain understandable with sound off. Pause/skip works by keyboard and reduced-motion preference survives reload. |
| Assistive technology | With a screen reader, read a problem, answer choices, code editor label, failure reason, save state and modal controls. Test reading order, announcements without repeated chatter, focus containment and recovery. Record what remains inaccessible; a decorative canvas label alone is not an accessible gameplay equivalent. |
| Visual direction | Review towns from all 17 regions, ordinary monsters, every boss, party classes/equipment and key cinematic beats at intended scale. Check silhouette differences, material/shadow consistency, legible paths, palette limits and warm/quiet contrast. Then ask players to identify a threat, service building and exit without narration. Screenshot approval alone is not proof of play readability. |

## Performance and durability measurements

Use the same named reference machine and browser for comparisons, with a separate lower-powered supported machine. Capture traces after a 30-second warm-up and label cold start separately. Do not equate a raster harness frame count with browser frames per second.

| Scenario | Measurement and proposed budget |
| --- | --- |
| Two-minute overworld route, busy battle and cinematic | Capture requestAnimationFrame intervals and long tasks separately per scenario. At 60 Hz aim for p95 frame interval ≤20 ms, p99 ≤33.4 ms and no unexplained main-thread stall over 100 ms during typing. Record refresh rate, settings, scene and sample count. These are project budgets, not measured results. |
| Typing, tab changes, focus toggle and MCQ answer | Measure event-to-next-paint latency; target ≤200 ms at the 75th percentile, with raw distribution retained. This follows the good INP threshold, but a small scripted local sample is not field Core Web Vitals evidence. See [Interaction to Next Paint](https://web.dev/articles/inp). |
| RUN, CAST and trace | Separate immediate pressed/busy feedback from Python execution, network time and final rendering. Aim for visible acknowledgement within 100 ms. The grader's timeout is not a UI performance budget. Show recoverable errors and trace truncation truthfully. |
| Navigation lifecycle | Repeat town → battle → world and ten cinematic start/pause/skip cycles. Compare post-cleanup heap, detached nodes, active animation loops and audio elements with a warmed baseline. Investigate retained growth over 10% across repeated equal batches; retain traces rather than claiming “no leak” from one sample. |
| Saving and interruption | After an acknowledged save, test reload, navigation and server restart: zero lost acknowledged code or explanation, zero duplicate grade/reward. Simulate a failed draft request: “saved” must not appear. Test stale encounter IDs and measured-run entry while a draft request is pending. |
| Session clock | Pause for 60 seconds, hide the page and simulate a closed/crashed browser. Paused time is excluded; abandoned activity is bounded by the documented idle lease. The display must describe an advisory activity estimate, not claim precise attention tracking. |

## Results and release decision

Create one results row per participant and task: ID, cohort, version, device/settings, task reached, completion time, moderator help, observed UI failures, code modality/rung, assistance, baseline/immediate/delayed scores, return/pressure ratings, and issue links. Store technical traces and anonymized code separately from consent records. Every finding needs reproducible steps, expected/actual behavior, severity and a retest result.

Block release for lost acknowledged work, incorrect grading/learning claims, assessment assistance leakage, inaccessible essential controls, crashes or a repeatable severe performance failure. Repeated navigation confusion and visual misreads require another pilot after repair. Report unknowns explicitly: no participants yet; no observed retention improvement yet; no measured human engagement yet; no general accessibility certification. Engineering checks and the human study should be reported as separate evidence.
