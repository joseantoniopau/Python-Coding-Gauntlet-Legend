# Art direction and rendering contracts

This is an original Python-learning RPG. Its visual references are 16-bit console RPGs and the painted science-fantasy, ink contours, limited animation and dramatic lighting of Heavy Metal (1981). Design research and the RPG-to-Gauntlet feature mapping are in [15-reference-research.md](15-reference-research.md). No reference archive was applied to the game. Artwork and scenes are original; recorded music and fonts retain the licenses and credits shipped with them.

## What the references contribute

The game combines readable side-view combat, compact expressive field actors, strong silhouettes, consistent framed menus, distinctive town geography, an ensemble cast and changes to a persistent world. Decisions need room: the learner must be able to reason before committing an action. Gauntlet's coding encounters resolve after Python execution and authoritative grading; they do not run an ATB clock while a beginner types. Sealed interviews retain their own explicit clocks.

Heavy Metal contributes broad shadow masses, warm highlights against cold ambient light, silhouettes framed by architecture, varied settings and held compositions punctuated by motion. It does not imply that every surface should glow red. Quiet inhabited places and dawn light provide contrast with the hostile citadel. See the [1981 production account](https://www.heavymetal.com/post/heavy-metal-the-making-of-the-movie-from-august-1981) and [Animation World Network's production history](https://www.awn.com/animationworld/here-s-skinny-heavy-metal).

The dimensions below are this game's contracts. They define the authored assets and layout, without requiring hardware-accurate console emulation.

## Palette, pixels and materials

- Authored creature, portrait, companion and hero rasters target at most 15 opaque colors plus transparency. `palette.js` supplies shared material ramps. Tests count resulting pixels rather than just palette declarations. The new equipped combat hero stays within 14; legacy field gear composites can exceed 15 (observed 19–21), so this is an asset contract rather than a claim of hardware emulation.
- Near-black outlines, cool shadow planes, a local material tone and a restrained warm edge establish volume. Metal gets a narrow hard highlight; cloth folds get broader planes. A new color must replace another color in the same sprite budget.
- Canvas art uses nearest-neighbor sampling and integer source-to-stage scales. Camera framing can change across cinematic shots; the scene is rasterized before final display. Narrow responsive windows may fit the final canvas to the available width.
- Code, prose, controls and results use ordinary readable DOM text. The offline Press Start 2P font is reserved for short display labels. Its OFL and credit ship beside the font.
- CRT texture is confined to the scene containers. It never covers the editor or problem text; high contrast disables it.

## Battle composition

| Contract | Source of truth | Value |
|---|---|---|
| Stage raster | `fx.STAGE`, checked against `battlescene.SCENE_STAGE` and `spellfx.STAGE_GEOM` | 256 × 224 |
| Safe frame | Same geometry | y=24 through 199, 176 rows |
| Ground | Same geometry | y=175 |
| Actor anchors | Same geometry | hero x=64; enemy x=184 |
| Combat hero | `battlehero.BATTLE_HERO` | 40 × 48; foot (18,47); stage scale 2 |
| Field hero | `sprites.HERO_W/HERO_H` | 16 × 24; separate walking rig |
| Ordinary monsters | `monsterart` | 24, 32 or 48 source pixels according to rank |
| Boss bodies | `bosses` / `bossart` | 64 × 64, 96 × 64; final body 96 × 128 |
| Cinematic plate | `cinema.js` | 480 × 270 |

The hero stands on the left and the enemy on the right. This preserves the game's established controls and motion. The hero is drawn after the enemy so a wide boss can occupy the space behind the party silhouette. Wide-boss scale, sink and horizontal bias belong to `bosses.BOSS_MOTION`; callers must use `drawBoss`, not duplicate offsets. Dissolve uses the last live boss blit to keep particles attached to the same body.

The combat rig has ready, cast, strike, guard, hurt and victory cels for the six classes and two body variants. Equipment attaches to the moving hand and follows armor integrity and forged-blade state. Field and combat actors share identity and color choices without stretching the field sprite into a battle actor. `combatFrame` caches at most 256 variants.

The main editor has 16px monospace text and 1.6 line height. Focus View hides scene furniture while preserving code and selection. Public RUN, graded CAST, MCQ selection and puzzle input retain distinct controls. Cinematic subtitles occupy their own space below artwork and have pause/skip controls.

## World and cast

`tiles.js` supplies 15 architecture families across 17 biome inputs, four building types and four reconstruction tiers. Building images are 40 × 36 with a consistent foot row; collision remains on the existing tile grid. Material, roofline, silhouette and windows establish regional identity. Ground variation is deliberately sparse so roads and landmarks survive at play size.

`monsterart.js` supplies the region rosters and the original creature cels. `bosses.js` owns boss identities, motion, map forms and phase changes. `sprites.js` supplies individual dialogue faces, including expressive mouth, brow and eye changes. `petart.js` supplies the twelve companion body plans and their facing, movement, faint and equipment states. Dialogue, field and battle callers use these production renderers.

World rebuilding, captured companions, released mentors, return routes and finale rosters come from saved game state. The renderer must never invent a rescue or insert an absent party member to fill a composition. The art-room fixtures are explicitly fictional demonstrations and cannot mark story beats seen.

## Motion and feedback

A cast has preparation, release, contact and recovery. Grading remains authoritative: impacts follow returned trials; resistance does not masquerade as a passing test; boss phase advance precedes a final victory. Trial playback is capped at 0.7 seconds of spacing while retaining every trial event and the full written report. Routine victory waits are shorter; boss arrivals and transformations remain deliberate. Enemy dissolves sample at most 384 particles.

Existing audio provides regional motifs, battle intensity, enemy cries, elemental casts and village recovery. Music is opt-in at browser startup and respects saved volume/motion preferences. A game should remain understandable with sound off and motion reduced.

## Verification

`web/art.html` is the read-only gallery of actual renderers: actors, portraits, monsters, bosses, towns, battle regions, companions and cinematic fixtures. Use its light background, silhouette, pause and beat-selection controls to inspect composition. A gallery pass is visual evidence, not evidence that gameplay or learning works.

Relevant checks live in `scripts/verify/`: `combathero`, `creaturepolish`, `regionalart`, `petpolish`, `stage`, `cinema`, `finale-player`, and the existing subsystem harnesses. `stage.mjs` compares the geometry declarations, safe-area readouts, integer scales and all boss phases. Its fit arithmetic is a synthetic check; browser measurements of the current layout are the acceptance evidence for reading space.

[16-polish-delivery.md](16-polish-delivery.md) records integrated checks and remaining work. Claims of usability or learning outcomes require observation of people using the game. Automated frame counts cannot establish visual appeal, enjoyment, or sufficient preparation for an interview.
