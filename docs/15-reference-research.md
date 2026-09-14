# FFVI × animated metal fantasy: Gauntlet implementation map

Research and source audit, 13 September 2026. Target: Python Coding Gauntlet Legend.

## Scope and evidence

This map was written before implementation, while Fable's integration was still active. Its descriptions of the existing game refer to that research snapshot. Fable subsequently completed and pushed its integration at 22:59 UTC; implementation and independent verification of this map are recorded in [the delivery report](16-polish-delivery.md).

The FFVI reference is the original North American SNES release, named **Final Fantasy III** in its manual. I inspected the original manual's controls, equipment, skills, configuration and battle screenshots, plus official Square Enix art and developer commentary. This verifies mechanics and presentation; it is not a claim to have played through FFVI during this audit. Pixel Remaster improvements are identified separately. References appear at the end.

The current-game side is based on source inspection and repository screenshots. Existing means an implementation was found; it does not certify every live route. The initial 31 recommendations remain the delivery scope. This document refines their design and prevents duplicating systems Fable already built.

## What to borrow from FFVI

The original manual shows a battle loop of readiness gauges, command choice, target selection, action resolution and rewards. Fight, character skills, magic, items and once-per-encounter Esper attacks coexist. Equipment offers visible stat comparisons; Active and Wait modes change enemy timing, with Wait protecting Item/Magic menu browsing. Four-member party screenshots make character identity and readable state central to the interface. [1, printed pp.18,20–21,26–32]

For Gauntlet, the transferable principle is a small number of legible decisions with expressive consequences. Preserve time to reason about Python. The player should understand what the enemy threatens, what their program accomplished, why a test failed, and what to try next. Animation should make that evidence memorable.

## Feature-to-feature map

Paths in this table are relative to the target repository. These are integration anchors, not instructions to create duplicate modules.

| FFVI feature | Current Gauntlet equivalent | Status and implementation direction |
|---|---|---|
| Readiness gauges and command-driven battle | `gauntlet/engine.py`, `incantation.py`, `web/js/fx.js`, `main.js` | **Partial match.** Keep the existing turn model. Add a clear intent → player action → resolution sequence. A readiness animation can communicate queued action; it must not tick down while the learner writes. Timed interview rehearsal remains opt-in. |
| Character-specific commands | `classes.py`, `movesets.py`, `arts.py` | **Strong match.** Six classes already emphasize different study habits. Give each a recognizable command presentation, posture, sound and tactical purpose. Extend their current moves rather than adding a second job system. |
| Sabin-style input mastery and distinctive special skills | Real Python incantations and fading templates in `incantation.py`; moves in `movesets.py` | **Strong conceptual match.** Syntax and semantics should express the move. Show a traceable relationship between input, target and result. Avoid treating memorized text as evidence of general Python mastery. |
| Espers teaching magic | Sages and secret arts in `arts.py`; mastery and class progression | **Partial match.** Present tutors as discoverable teachers with learning progress. Unlock through demonstrated transfer on unseen problems. Do not replace correctness with accumulated combat points. |
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
| Clear menus and player configuration | Settings in `main.js`, layered CSS, responsive battle layout | **Partial match.** Preserve recognizable framed panels, clear selection and compact status. Enlarge code and explanations, bundle the font, and keep CRT effects away from text. Original FFVI itself offered substantial configuration. |
| Bestiary, gallery and music player | Enemy art, finale gallery and existing audio system | **Partial; remaster reference.** A learning bestiary can connect enemy behavior to mistakes and counterexamples. Reuse the existing gallery, adding earned entries and soundtrack listening where available. Pixel Remaster explicitly includes these extras. [4] |

## Learning systems that extend beyond FFVI

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

### FFVI: economy, staging and identity

Kazuko Shibuya's interview emphasizes drawing fundamentals, deliberate silhouettes and restrained shading. Her comments span several games; they are not evidence that every FFVI asset used one documented size or production pipeline. Nomura's official FFVI interview describes monster/battle visual work and an exceptional final-boss composition that drove battle presentation. These accounts support careful composition and character-specific design. [2][3]

**Apply to Gauntlet:** author a dedicated battle hero sheet instead of enlarging the field walk cycle. The inspected renderer uses a 256×224 stage and a 16×24 hero enlarged four times. A proposed 24×32 battle sheet is a design experiment, not a verified original FFVI specification. Compare alternatives in the real stage before adopting one. Establish logical pixel size, anchors, ground contact and collision-independent visual bounds. Keep nearby actors at consistent apparent detail.

Start with idle, preparation, cast, strike, recoil, hurt, guard, exhausted, victory and defeat. Each pose needs a readable silhouette; each class needs recognizable movement. Animate anticipation and follow-through rather than stretching the whole sprite. Equipment overlays must stay attached across every pose. Existing portraits already have expressions, so extend their individuality and actual callers instead of rebuilding expression support.

### Heavy Metal: directed variety and tonal contrast

The original making-of and Potterton's later interview describe an anthology of different visual approaches, coordinated through art direction and storyboard work. Its identity includes science fantasy, architectural spectacle and a mixture of orchestral and rock music. It is not a single uniform palette or endless maximal intensity. [5][6]

**Apply to Gauntlet:** create one shared drawing language—bold contour hierarchy, expressive anatomy, dramatic silhouettes, weathered materials—then give regions controlled variation. A forge may use black iron, ember light and angular architecture; a refuge can use warm lamps, blue evening and softer silhouettes. Preserve moments of humor, tenderness and quiet so threats have contrast. Original characters and architecture should carry the influence without copying recognizable film or FFVI assets.

### Fire and Ice: atmosphere and separation

Bakshi's studio identifies rotoscoping as central to the film's movement. Background artist James Gurney describes limited sequence palettes, atmosphere, and foreground layers that let characters occupy a readable middle space. I directly inspected his published background examples; this is visual evidence for staging, not inspection of the full film. [7][8][9]

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

## Sources

1. [Nintendo-hosted original SNES manual, Final Fantasy III](https://www.nintendo.co.jp/clvs/manuals/common/pdf/CLV-P-SABTE.pdf). Printed pages cited above; inspected scans include equipment and battle examples.
2. [Kazuko Shibuya, 2013 interview, English translation](https://shmuplations.com/kazukoshibuya/). First-person production commentary; translation published later.
3. [Square Enix: Tetsuya Nomura on FFVI's 30th anniversary](https://na.finalfantasy.com/topics/528), 7 June 2024. Monster art, battle visuals and development recollections.
4. [Square Enix: Final Fantasy Pixel Remaster FAQ](https://finalfantasypixelremaster.square-enix-games.com/en_US/faq). Remaster changes and extras; separate from original SNES behavior.
5. [Heavy Metal: The Making of the Movie, August 1981](https://www.heavymetal.com/post/heavy-metal-the-making-of-the-movie-from-august-1981). Original production coverage republished by the magazine.
6. [Animation World Network: Here's the Skinny on Heavy Metal](https://www.awn.com/animationworld/here-s-skinny-heavy-metal), 20 April 2015. Direct Gerald Potterton interview.
7. [Bakshi Productions: Fire & Ice](https://www.bakshistudio.com/projects/fire-&-ice). Studio account of the production and animation approach.
8. [James Gurney: The Backgrounds for Fire and Ice](https://gurneyjourney.blogspot.com/2015/10/the-backgrounds-for-fire-and-ice.html), 12 October 2015. First-person background painting process and illustrated examples.
9. [James Gurney: Background Painting with Ice and Snow](https://gurneyjourney.blogspot.com/2023/12/background-painting-with-ice-and-snow.html), 26 December 2023. Depth, foreground layering and background treatment.

The feature adaptations, proposed art specifications and implementation acceptance criteria are this audit's recommendations. The cited sources explain their historical references; they do not establish that these changes will improve learning without evaluation.

## Addendum: user-supplied restoration references

Inspected on 13 September 2026. These packages were inspected as data; no patch or assembly source was executed, no base game was patched, and no Gauntlet code was changed. Their installation instructions are documentation, not a request to install them.

### What the archives actually contain

| Archive | Verified contents | Reference value |
|---|---|---|
| `Final_Fantasy_VI_(Ted_Woolsey_Uncensored_3.06).zip` | 16 IPS patches, six text documents and two assembly source files. No base ROM or standalone image assets. | SNES graphics restoration, animation correctness, legible menus, navigable maps and quality-of-life design. |
| `ff6a_color_restoration_v101.zip` | Three region-specific base IPS patches, three supplementary IPS patches and a readme. | Palette consistency and scene-specific color restoration for FFVI Advance. |
| `ff6a_sound_restore_v201.zip` | One IPS patch and a readme. | Music/SFX identity, mixing performance and synchronization. |

All 23 IPS files parsed successfully through their record streams and end markers. This establishes structural readability, not correctness, compatibility or successful gameplay. IPS files contain offset-based replacement data; these archives do not supply a complete game that can be rendered or auditioned on its own. No exact palette swatches or audio fidelity claims were independently verified through playback.

The earlier `SCMS_FF6PR` package is a separate Windows Pixel Remaster movement-speed modification. These SNES and GBA patches are different targets and are not components to combine in Gauntlet.

### Woolsey Uncensored: useful design references

The author's bundled readme and bug-fix compendium describe restoration of monster/Esper graphics, the original final-battle tiers, town signs and title presentation. They also document small defects: a portrait color streak, missing tail pixels, foreground overlap clipping a face, missing riding poses and running frames inconsistent with character state. These are references for completeness and coherent presentation; the ZIP is not a high-resolution graphics overhaul.

The optional Add-Ons variants contain particularly relevant interaction improvements: named special commands, reward previews, a direct equipment/relic shortcut, a minimap distinguishing mountains from traversable land, learnable-ability indicators and expanded descriptions. These are optional additions in this package, not features to attribute indiscriminately to every version of original FFVI.

| Package reference | Incorporate into Gauntlet | Integration and acceptance |
|---|---|---|
| Restored multi-tier finale graphics | Author a distinctive original composition for each major boss phase. | Extend `web/js/bosses.js` and battle staging. Phase silhouettes must be recognizably different, remain within intended framing and preserve readable targets. |
| Missing poses and clipped sprite parts | Make sprite coverage and attachment checks part of the art gallery. | Exercise class, gear, action, facing and status combinations in `sprites.js`, `lootart.js` and `fx.js`. No fallback to an unrelated character, missing limb or clipped weapon. |
| Sliding-dash correction | Keep footfall animation consistent with travel distance and speed. | Review `overworld.js` and sprite timing. Verify walking, sprinting, direction changes and frame-rate changes; detect skating or frozen walk cycles. |
| Terrain-aware minimap | Distinguish paths, blocked terrain, water, entrances and objectives. | Extend the current map representation, using symbols as well as color. Test that routes shown as traversable agree with actual movement rules. |
| Names alongside special-command inputs | Show the move name, Python concept, valid syntax guidance and target behavior together. | Extend incantation/moveset UI without exposing the answer to the encounter. Keep templates' assistance state explicit. |
| Reward preview before commitment | Show expedition duration estimate, learning objective and known reward before starting. | Use current quest/reward data. Do not promise a specific random drop or an undisclosed sealed assessment reward. |
| Direct equipment/relic shortcut | Allow quick comparison and navigation among equipment, regalia and appearance. | Keep selection/focus when switching panels and show actual character appearance changes. |
| Learnable-ability checklist | Mark grimoire entries as encountered, practicing, independently demonstrated or due for review. | Derive states from real learning evidence. Avoid converting a discovered spell or repeated assisted answer into certified mastery. |
| Expanded descriptions and overflow fixes | Prefer complete names and useful effect descriptions over cryptic abbreviations. | Check longest actual labels, text scaling, narrow windows, tooltips and keyboard access. Never truncate Python code to preserve decoration. |

The bundled music-player notes additionally describe ambient audio becoming too loud or briefly silent after leaving menus. Adapt that into a regression scenario: entering a gallery or soundtrack player and returning to the same scene should restore its intended track, ambience and mixer levels without duplicated loops.

### Color Restoration v1.01: art-system implications

Novalia Spirit's readme describes restoring color across opening snow, portraits, status icons, menu character sprites, maps, palette animations, world skies, monsters, Espers and battle backgrounds. It explicitly distinguishes those from categories that already retained suitable colors, including battle character sprites and many combat effects. Therefore, a global saturation or brightness filter would be a poor translation of this reference.

The useful production rule is **shared base colors plus deliberate scene lighting**. Give skin, cloth, hair, metal and faction accents consistent palette identities across field sprites, battle sprites, portraits, equipment previews and menus. Region lighting can modify their appearance through a controlled treatment. Compare all views side by side before approving a character.

Specific additions to the implementation checklist:

- Create a palette reference scene containing the same hero, companion and materials in field, battle, dialogue and equipment contexts. Validate intended differences rather than demanding every lit pixel be identical.
- Author shadows and atmosphere per region. Preserve a range of dark, middle and highlight values; do not increase saturation uniformly to imply improved graphics.
- Verify fades end at the intended palette and brightness. A fade that stops early must not leave the next scene permanently dimmed.
- Restore scene palette state after boss transformations, flashes, menus and scene changes. Avoid carrying one enemy's temporary colors into another encounter.
- Test palette cycling for water, fire and magical surfaces while preserving stable colors in portraits and UI.
- Keep text contrast independent of decorative palette animation. Do not copy historical low-contrast UI simply because the reference is authentic.
- Keep optional CRT/color treatments out of the base artwork so they can be disabled without losing the intended composition.

The readme identifies unresolved title-logo blending and gradient issues and labels supplementary colors for GBA-exclusive monsters/animations as approximations. Those are limits of this reference: it does not establish an exact historical SNES palette for artwork that did not exist in that version.

### Sound Restoration v2.01: audiovisual implications

Bregalad's readme says the second-generation restoration converts SNES sequence and sound-effect data for GBA, uses a faster mixer, and includes streamed orchestral/vocal opera material. It also documents remaining fade gaps, synchronization differences and an attack-SFX mapping problem. These are author-reported behaviors; the archive was not played here.

Apply the design lessons to Gauntlet's existing `web/js/audio.js` and combat events:

- Give attack families distinct sounds: impact, blade, casting, resistance, healing and failure should not collapse into the same generic cue.
- Schedule effects against the actual animation impact point, and music changes against meaningful scene/phase boundaries.
- Avoid blocking playback preparation in the typing or animation loop. Profile the existing audio and rendering paths together before choosing optimizations.
- Use an explicit transition policy for combat, town, dialogue, gallery and return navigation. Keep track and ambience ownership clear; verify no duplicated playback or stuck volume state.
- Support concise routine effects and fuller boss sequences with the same underlying outcome event. Reduced motion and skipped animation must leave sound and state in a consistent place.
- Use original themes with recognizable motifs and contrasting arrangements for safety, threat and recovery. Large orchestral or vocal moments should be reserved for an earned set piece.
- Test browser audio activation, mute/unmute, pause/resume, device changes and background-tab return. Check that a disabled sound path never blocks progression.

These packages provide design and engineering references. No reusable standalone art/audio license was established, and the color archive explicitly restricts redistribution. Implement original Gauntlet assets and behavior informed by the analysis; do not treat the patches as an asset library or import their music, sprites or source into the game.

### Evidence and provenance

Local sources are the files supplied by the user in `/Users/japa/Downloads/`. Readme claims are distinguished above from observed binary structure and proposed Gauntlet adaptations. The [FF6 Hacking release thread](https://www.ff6hacking.com/forums/thread-3620-post-40308.html) corroborates TWUE's restoration and interface-update context.

Archive SHA-256 values:

- TWUE 3.06: `e713cc8123108666d2621dc64d96a1420d4d67cf7e669e9a08b76c6a30694a61`
- Color v1.01: `781b702c909ab9374ca01751574680d98bc453372306ed0f9d2d5a51c54a4998`
- Sound v2.01: `c6617a2e27366d49450a7546a1d6643adac314f93c283f84c913a80e9dbe29f7`
