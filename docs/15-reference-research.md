# 16-bit RPG and animated metal fantasy: Gauntlet implementation map

Research and source audit, 13 September 2026. Target: Python Coding Gauntlet Legend.

## Scope and evidence

This map was written before implementation, while Fable's integration was still active. Its descriptions of the existing game refer to that research snapshot. Fable subsequently completed and pushed its integration at 22:59 UTC; implementation and independent verification of this map are recorded in [the delivery report](16-polish-delivery.md).

This public design map records the RPG, art and learning principles selected for Gauntlet. The detailed comparative source audit and supplied-archive inventory are preserved in the local research notes. The recommendations below describe decisions for this original game.

The current-game side is based on source inspection and repository screenshots. Existing means an implementation was found; it does not certify every live route. The initial 31 recommendations remain the delivery scope. This document refines their design and prevents duplicating systems Fable already built.

## The battle design principle

A readable encounter moves through intent, command choice, target selection, action resolution and rewards. Character abilities, equipment and companions should create understandable choices, with clear comparisons and feedback.

For Gauntlet, the transferable principle is a small number of legible decisions with expressive consequences. Preserve time to reason about Python. The player should understand what the enemy threatens, what their program accomplished, why a test failed, and what to try next. Animation should make that evidence memorable.

## Feature-to-feature map

Paths in this table are relative to the target repository. These are integration anchors, not instructions to create duplicate modules.

| RPG design feature | Current Gauntlet equivalent | Status and implementation direction |
|---|---|---|
| Readiness gauges and command-driven battle | `gauntlet/engine.py`, `incantation.py`, `web/js/fx.js`, `main.js` | **Partial match.** Keep the existing turn model. Add a clear intent → player action → resolution sequence. A readiness animation can communicate queued action; it must not tick down while the learner writes. Timed interview rehearsal remains opt-in. |
| Character-specific commands | `classes.py`, `movesets.py`, `arts.py` | **Strong match.** Six classes already emphasize different study habits. Give each a recognizable command presentation, posture, sound and tactical purpose. Extend their current moves rather than adding a second job system. |
| Input mastery and distinctive special skills | Real Python incantations and fading templates in `incantation.py`; moves in `movesets.py` | **Strong conceptual match.** Syntax and semantics should express the move. Show a traceable relationship between input, target and result. Avoid treating memorized text as evidence of general Python mastery. |
| Discoverable mentors teaching abilities | Sages and secret arts in `arts.py`; mastery and class progression | **Partial match.** Present tutors as discoverable teachers with learning progress. Unlock through demonstrated transfer on unseen problems. Do not replace correctness with accumulated combat points. |
| Summon spectacle | Existing spell engine, arts and companion presentation | **Presentation opportunity.** Reserve large sequences for first mastery, boss transitions and major assists. If adding limited-use assists, define the tactical function first and preserve the learner's work as the source of success. |
| A party with distinct roles | One active companion in `pets.py`; separate story escorts in `zonecompanions.py` | **Partial, not a four-character party.** Strengthen the current hero-plus-companion arrangement first. Companions can probe, explain or protect; they should not write the answer. Four independently controlled party members would be a new system requiring a separate complexity decision. |
| Party formation and positioning | Current target modes and multi-enemy moves | **No verified front/back-row equivalent.** Add positioning only if it creates a visible, teachable choice. Prefer meaningful target selection over a decorative formation menu. Revalidate actual balance before importing damage modifiers. |
| Elemental matchups | `elements.py`, `tactics.py` | **Strong match.** Surface affinities and resistances before commitment; show why a valid cast benefited. Existing multipliers act on earned results, so a wrong solution must remain wrong regardless of element. |
| Status effects and recovery | Existing elements/status rules, `potions.py`, companion recovery | **Existing foundation.** Use icons, duration text and readable feedback. Preserve the current principle that status does not prevent the learner thinking or typing. Do not transplant Silence or Stop as disabled editing. |
| Equipment and relic choices | `items.py`, `forge.py`, `regalia.py`, `main.js` character screen | **Strong foundation, presentation gap.** Add a full character preview, explicit before/after effects, understandable set benefits and cosmetic selection. Preserve gear balance; cosmetics should not change grading. |
| Item use and resource management | Potions, equipment integrity and existing town systems | **Existing foundation.** Explain resource costs before action and retain an accessible recovery route. No learner should become unable to practice because a failed attempt consumed their last resource. |
| Towns as recovery and narrative hubs | `villagelife.py`, quests, town tiers in `world.py` | **Strong match.** Make towns visibly inhabited: recurring residents, short scenes, useful services and changed dialogue after milestones. Reuse existing activity state. |
| World travel and destination discovery | Regions, portals, keys and unlocks in `world.py`; `web/js/overworld.js` | **Strong match.** Make each destination recognizable at a glance, show the next meaningful objective, and make unlocked shortcuts tangible. Do not add another travel progression currency. |
| Dungeon exploration and obstacles | `dungeons.py`: rooms, passages, locks, keys and multiple layout generators | **Strong match.** Author memorable puzzle sequences using these primitives. Use clues, spatial continuity and visible consequences. More random rooms alone will not create better exploration. |
| Bosses demanding a different approach | `tactics.py`, boss generation, `web/js/bosses.js`, tests and problem constraints | **Strong foundation.** Give each boss an explicit learning objective and phase rule. A phase should reveal a new constraint or counterexample, rather than merely increase HP. |
| Large narrative battle artwork | Existing boss and layered battle-scene renderers | **Strong rendering foundation.** Design silhouettes and compositions first, then assign animation. Reserve oversized or segmented compositions for exceptional encounters. Keep the code pane stable. |
| Character scenes and emotional stakes | Quests, expressive portraits, pets and zone companions | **Partial match.** Extend persistent character arcs with specific desires, changing relationships and reactions to recovery. Distinguish optional companion help from story escort state. |
| Scenario variation and dramatic set pieces | Quest system, Mini-Repos, existing story encounters | **Partial match.** Use rescue, investigation and preparation formats to vary cognitive tasks. A debugging investigation can play differently from an algorithm duel while sharing grading infrastructure. |
| Return visits that reveal changed circumstances | `quests.py` world changes, village life, finale | **Strong foundation.** Tie repaired bridges, restored lights, released residents and altered music to persisted quest flags. The player should see evidence of their effort after returning. |
| Optional discovery and late-game challenges | Secret arts, optional quests, hunters and dungeons | **Existing foundation.** Reward curiosity with alternate tactics, story and appearance. Add boss rematches that vary constraints and test transfer, avoiding repetition of the same answer. |
| Clear menus and player configuration | Settings in `main.js`, layered CSS, responsive battle layout | **Partial match.** Preserve recognizable framed panels, clear selection and compact status. Enlarge code and explanations, bundle the font, and keep CRT effects away from text. |
| Bestiary, gallery and music player | Enemy art, finale gallery and existing audio system | **Presentation opportunity.** A learning bestiary can connect enemy behavior to mistakes and counterexamples. Reuse the existing gallery, adding earned entries and soundtrack listening where available. |

## Learning systems for real Python practice

These additions should use the game's existing educational structure rather than force every learning need into a combat mechanic.

1. **Personal grimoire.** Build on `srs.py`, `adaptive.py` and attempt history. Each entry should show the concept, a previous misconception, the player's corrected reasoning and evidence from a later unseen task. Include a direct route into relevant practice. Exclude sealed prompts and solutions.
2. **Scaffold fading.** Reconcile Fable's `scaffold.py` with the first-lesson work. Preserve one problem identity across supported presentations; repeated help on the same underlying problem should not count as independent mastery. Make the transition to writing from scratch explicit and reversible in practice.
3. **Actual-code tracing.** `web/js/viz.js` currently includes built-in demonstrations. Label those as demonstrations. A separate bounded trace must come from the player's executed program, with line, locals and data-state provenance. Impose execution and output limits; do not infer a trace from a canned animation.
4. **Communication drills.** `coach.py` includes keyword-based explanation scoring. Replace overly confident semantic judgments with problem-specific criteria: claimed invariant, complexity justified by operations, edge case and tradeoff. Distinguish evidence detected from a claim that the explanation is correct. Validate with correct paraphrases and plausible but wrong explanations.
5. **Mini-Repo investigations.** Expand existing investigations with a reproducible failure, files to inspect, a repair, tests and a short explanation. Reward a small correct repair and useful regression test. Keep success independent of exact patch text.
6. **Player-directed practice.** Build on the adaptive route: offer recommended next task with a reason, targeted review and exploration. The model should remain advisory; the player should understand whether they are learning, reviewing or being assessed.
7. **Short expeditions.** Offer approximately 10-, 20- and 40-minute routes with a natural stopping point and resumable state. Time estimates must not become failure timers. Mix one focal concept, retrieval of an older concept and a small narrative payoff.
8. **Interview rehearsal.** Keep repeatable practice distinct from sealed readiness assessment in `finalexam.py`. Rehearsal can include time, narration, debugging and debrief. Never train on sealed items or imply practice completion certifies interview readiness.
9. **Earned keepsakes.** Award cosmetics and remembered world details for transfer, explanation, thoughtful testing and recovery from a misconception. Avoid attendance punishments and forced streak maintenance. Measure voluntary return and learning, not minutes trapped in menus.

## Visual research translated into production decisions

### Pixel art: economy, staging and identity

Prioritize deliberate silhouettes, restrained shading and character-specific gestures. Design large encounters as compositions with clear focal points. Additional pixels should improve readable anatomy and staging.

**Apply to Gauntlet:** author a dedicated battle hero sheet instead of enlarging the field walk cycle. The inspected renderer uses a 256×224 stage and a 16×24 hero enlarged four times. The initial 24×32 battle-sheet proposal was a design experiment; the delivered 40×48 contract is recorded in [the art direction](08-art-direction.md). Compare alternatives in the real stage before adopting one. Establish logical pixel size, anchors, ground contact and collision-independent visual bounds. Keep nearby actors at consistent apparent detail.

Start with idle, preparation, cast, strike, recoil, hurt, guard, exhausted, victory and defeat. Each pose needs a readable silhouette; each class needs recognizable movement. Animate anticipation and follow-through rather than stretching the whole sprite. Equipment overlays must stay attached across every pose. Existing portraits already have expressions, so extend their individuality and actual callers instead of rebuilding expression support.

### Heavy Metal: directed variety and tonal contrast

The original making-of and Potterton's later interview describe an anthology of different visual approaches, coordinated through art direction and storyboard work. Its identity includes science fantasy, architectural spectacle and a mixture of orchestral and rock music. It is not a single uniform palette or endless maximal intensity. [Production account][metal-production]; [director interview][potterton].

**Apply to Gauntlet:** create one shared drawing language—bold contour hierarchy, expressive anatomy, dramatic silhouettes, weathered materials—then give regions controlled variation. A forge may use black iron, ember light and angular architecture; a refuge can use warm lamps, blue evening and softer silhouettes. Preserve moments of humor, tenderness and quiet so threats have contrast. Original characters and architecture should carry the influence through original assets and compositions.

### Fire and Ice: atmosphere and separation

Bakshi's studio identifies rotoscoping as central to the film's movement. Background artist James Gurney describes limited sequence palettes, atmosphere, and foreground layers that let characters occupy a readable middle space. I directly inspected his published background examples; this is visual evidence for staging, not inspection of the full film. [Studio account][bakshi]; [background process][gurney-backgrounds]; [atmosphere studies][gurney-snow].

**Apply to Gauntlet:** use strong foreground framing, a quieter actor plane and softened distant shapes. Keep the highest contrast around threats and interactive landmarks. Reduce repeated terrain texture behind characters. Build gesture studies for weight shifts and attacks, then translate them into compact pixel poses. Apply warm/cool light in planes; additional blur and glow will not repair weak anatomy.

### Interface and sound

The inspected CSS applies substantial CRT treatment across the viewport and relies on a locally installed pixel font. Separate scene nostalgia from reading. Bundle a licensed display font, provide a highly legible code font, and scope optional scanlines to artwork. Test at default zoom, larger text, narrow windows and reduced motion. Keyboard focus must remain visible through every modal and combat transition.

The audio system already has tracks, synthesis, intensity and mixing. Compose recognizable motifs for places and characters; arrange them differently for peril and recovery. Align music transitions with scene or phase boundaries. Reserve major sound and screen effects for meaningful events. Provide independent music/effects controls and never communicate essential feedback through sound alone.

## A concrete opening-to-boss vertical slice

Use one existing region as the quality benchmark before propagating changes.

- **Arrival:** an authored establishing view, one clear landmark and a resident with a specific problem. Teach movement and interaction through a useful action.
- **First encounter:** one observable enemy behavior, a guided Python action and feedback connecting that action to the resulting state. Keep the editor fully readable.
- **Second encounter:** reduce one aid while retaining the same concept; avoid presenting that repetition as an independent mastery win.
- **Town return:** a resident reacts and a small world detail changes. Offer equipment comparison and an optional companion interaction.
- **Dungeon:** alternate a trace, a bug investigation and a short implementation. Reuse current room/lock logic. Let the player save and stop naturally.
- **Boss:** telegraph a rule, reveal a counterexample, then ask the player to adapt to a genuine constraint. Art and music respond to the phase; correctness drives combat evidence.
- **Debrief:** concise reward, one specific learning observation and a later review opportunity. Restore agency immediately after celebration.

Acceptance requires the complete loop to work with fresh and existing saves, assisted and independent solutions, wrong answers, recovery, navigation away and reload. Compare actual traces and grader results against visible feedback.

## Integration and validation plan

### Pass 1: baseline and reading comfort

After explicit Fable completion, record the revision and working-tree state. Reconcile each of the original 31 recommendations against shipped code and rendered behavior. Use isolated save data. Establish representative screenshots for title, field, dialogue, coding, puzzle, equipment, boss and debrief. Fix font loading, text layout, CRT scope, focus and motion controls first.

### Pass 2: actors and scene composition

Implement the selected battle sprite contract, equipment attachment points, boss phase composition and region reference palette. Use the real renderer in a deterministic visual gallery. Include every class, representative gear, each boss phase, small and large windows, and reduced-motion settings. Headless execution alone does not verify clipping, silhouette or readability.

### Pass 3: actions, audio and world continuity

Define structured presentation events that carry the relevant existing combat result: actor, target, action, outcome, learning evidence and reduced-motion behavior. Adapt existing event infrastructure before introducing a new abstraction. Ensure misses, resistance, healing and critical effects have genuine callers; Fable's sound pass may already resolve this. Verify effects cannot change rewards or duplicate state transitions. Tie visible recovery to existing persisted quest state.

### Pass 4: learning depth and pacing

Deliver grimoire, trace provenance, communication criteria, practice controls, expeditions, rematches and rehearsal through existing learning modules. Validate unseen transfer and assisted-attempt handling. Preserve offline operation and sealed assessment boundaries. A beautiful solved example is not proof the player can solve an unfamiliar problem.

### Evidence required before calling this polished

- Automated checks for affected state transitions, save compatibility, execution bounds and grading invariants.
- Browser verification of the complete vertical slice, including keyboard operation, errors, reload and recovery.
- Visual inspection of actual frames, not only no-exception harnesses.
- Profiling during a representative busy scene and while typing; report measured hardware/browser and results rather than an unsupported universal FPS promise.
- A human playtest protocol covering first-session comprehension, reading effort, voluntary return and delayed unseen problems. Human playtesting remains outstanding until real participants take part.

A practical playtest asks a beginner and an intermediate learner to complete the slice without coaching, explain what happened, return to an unseen related task later, and identify confusing moments. Record assistance and failures. Engagement should be assessed alongside retention and transfer; longer play alone is not learning.

## Art-system acceptance checklist

The restoration-reference audit highlighted small omissions that weaken an otherwise coherent game: missing poses, clipped body parts, misleading map symbols and inconsistent transitions. The following checks apply to Gauntlet's original assets and existing systems. Package inventories, binary hashes and detailed historical comparisons remain in the local research archive.

| Production concern | Incorporate into Gauntlet | Integration and acceptance |
|---|---|---|
| Distinct multi-phase finale artwork | Author a distinctive original composition for each major boss phase. | Extend `web/js/bosses.js` and battle staging. Phase silhouettes must be recognizably different, remain within intended framing and preserve readable targets. |
| Missing poses and clipped sprite parts | Make sprite coverage and attachment checks part of the art gallery. | Exercise class, gear, action, facing and status combinations in `sprites.js`, `lootart.js` and `fx.js`. No fallback to an unrelated character, missing limb or clipped weapon. |
| Footfall and movement consistency | Keep footfall animation consistent with travel distance and speed. | Review `overworld.js` and sprite timing. Verify walking, sprinting, direction changes and frame-rate changes; detect skating or frozen walk cycles. |
| Terrain-aware minimap | Distinguish paths, blocked terrain, water, entrances and objectives. | Extend the current map representation, using symbols as well as color. Test that routes shown as traversable agree with actual movement rules. |
| Names alongside special-command inputs | Show the move name, Python concept, valid syntax guidance and target behavior together. | Extend incantation/moveset UI without exposing the answer to the encounter. Keep templates' assistance state explicit. |
| Reward preview before commitment | Show expedition duration estimate, learning objective and known reward before starting. | Use current quest/reward data. Do not promise a specific random drop or an undisclosed sealed assessment reward. |
| Direct equipment/relic shortcut | Allow quick comparison and navigation among equipment, regalia and appearance. | Keep selection/focus when switching panels and show actual character appearance changes. |
| Learnable-ability checklist | Mark grimoire entries as encountered, practicing, independently demonstrated or due for review. | Derive states from real learning evidence. Avoid converting a discovered spell or repeated assisted answer into certified mastery. |
| Expanded descriptions and overflow fixes | Prefer complete names and useful effect descriptions over cryptic abbreviations. | Check longest actual labels, text scaling, narrow windows, tooltips and keyboard access. Never truncate Python code to preserve decoration. |

Returning from a gallery or soundtrack player should restore the scene's intended track, ambience and mixer levels without duplicated loops.

### Palette identity and scene lighting

The useful production rule is **shared base colors plus deliberate scene lighting**. Give skin, cloth, hair, metal and faction accents consistent palette identities across field sprites, battle sprites, portraits, equipment previews and menus. Region lighting can modify their appearance through a controlled treatment. Compare all views side by side before approving a character.

Specific additions to the implementation checklist:

- Create a palette reference scene containing the same hero, companion and materials in field, battle, dialogue and equipment contexts. Validate intended differences rather than demanding every lit pixel be identical.
- Author shadows and atmosphere per region. Preserve a range of dark, middle and highlight values; do not increase saturation uniformly to imply improved graphics.
- Verify fades end at the intended palette and brightness. A fade that stops early must not leave the next scene permanently dimmed.
- Restore scene palette state after boss transformations, flashes, menus and scene changes. Avoid carrying one enemy's temporary colors into another encounter.
- Test palette cycling for water, fire and magical surfaces while preserving stable colors in portraits and UI.
- Keep text contrast independent of decorative palette animation. Do not copy historical low-contrast UI simply because the reference is authentic.
- Keep optional CRT/color treatments out of the base artwork so they can be disabled without losing the intended composition.

### Audio and visual continuity

Apply the design lessons to Gauntlet's existing `web/js/audio.js` and combat events:

- Give attack families distinct sounds: impact, blade, casting, resistance, healing and failure should not collapse into the same generic cue.
- Schedule effects against the actual animation impact point, and music changes against meaningful scene/phase boundaries.
- Avoid blocking playback preparation in the typing or animation loop. Profile the existing audio and rendering paths together before choosing optimizations.
- Use an explicit transition policy for combat, town, dialogue, gallery and return navigation. Keep track and ambience ownership clear; verify no duplicated playback or stuck volume state.
- Support concise routine effects and fuller boss sequences with the same underlying outcome event. Reduced motion and skipped animation must leave sound and state in a consistent place.
- Use original themes with recognizable motifs and contrasting arrangements for safety, threat and recovery. Large orchestral or vocal moments should be reserved for an earned set piece.
- Test browser audio activation, mute/unmute, pause/resume, device changes and background-tab return. Check that a disabled sound path never blocks progression.

## Animation sources

- [Heavy Metal: The Making of the Movie, August 1981][metal-production]. Original production coverage republished by the magazine.
- [Animation World Network: Here's the Skinny on Heavy Metal][potterton], 20 April 2015. Direct Gerald Potterton interview.
- [Bakshi Productions: Fire & Ice][bakshi]. Studio account of the production and animation approach.
- [James Gurney: The Backgrounds for Fire and Ice][gurney-backgrounds], 12 October 2015. First-person background painting process and illustrated examples.
- [James Gurney: Background Painting with Ice and Snow][gurney-snow], 26 December 2023. Depth, foreground layering and background treatment.

[metal-production]: https://www.heavymetal.com/post/heavy-metal-the-making-of-the-movie-from-august-1981
[potterton]: https://www.awn.com/animationworld/here-s-skinny-heavy-metal
[bakshi]: https://www.bakshistudio.com/projects/fire-&-ice
[gurney-backgrounds]: https://gurneyjourney.blogspot.com/2015/10/the-backgrounds-for-fire-and-ice.html
[gurney-snow]: https://gurneyjourney.blogspot.com/2023/12/background-painting-with-ice-and-snow.html

The feature adaptations, proposed art specifications and acceptance criteria are this audit's recommendations. These sources explain animation references; they do not establish improved learning without evaluation.
