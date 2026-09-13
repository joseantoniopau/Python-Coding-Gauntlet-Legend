"""The people the bosses took, and what they do once they are out.

Every named boss in world.BOSSES is holding somebody. They are villagers from
that boss's own region — a key-cutter off the plateau, a reed-cutter out of the
marsh, a stair-mason who has been building the same tower stair since he was
nineteen — and they are held wherever the boss is, in its chamber, in the
dungeon that region owns. Beating it lets them out. Letting them out is how the
fight pays.

Four things this module insists on.

1. THEY ARE PEOPLE. Every one of them has a name, a trade, an opinion they held
   before you arrived, and something to say that is about their own life rather
   than about your arrival. Some are grateful. Sennet Crale is furious that it
   took nine weeks. Perrin Oake is embarrassed, because he has lived in that
   marsh for sixty years and he still walked towards a light in it. Hessa
   Dunmar and Torv Bael were mid-argument when they were taken, have been
   arguing about it in a cage ever since, and would like to finish. Nobody in
   this file exists in order to be a reward, and `validate()` enforces the part
   of that which can be enforced: a captive with no opinion and nothing to say
   about themselves is a defect, by name, at import.

2. THE RESCUE IS THE BOSS REWARD, AND IT IS PAID THE WAY QUESTS ARE PAID.
   There is no second reward path here. `reward_for(boss_id)` is
   quests.reward_for() with a tier read off the region's own difficulty band,
   and `free()` returns the same {"pay", "story", "world"} split that
   quests.complete() returns, so whatever settles a quest turn-in settles this
   without learning a new vocabulary. The material half — metal, potion,
   vendor credit — is derived from the region and the tier exactly as
   quests._pay_in_kind derives it, so this file cannot pay off-curve even if
   somebody edits it carelessly.

3. THEY CHANGE THE PLACE THEY GO HOME TO. Sixteen of the twenty-five carry a
   BOON: a smith who mends deeper and cheaper, an apothecary who restocks, a
   teacher who posts the morning drill, two riggers who finish their argument
   by building the span both ways at once and leave a road behind them. The
   effects vocabulary is items.EFFECT_LABELS, the same one the town upgrades
   use, restricted here to an allowlist of things that buy time, standing and
   somewhere to sit. None of it touches what a problem says, what a test
   asserts, or what a hint reveals. `_no_boon_supplies_an_answer()` is the
   proof and validate() runs it.

4. THE ROLL CALL IS PERSISTENT AND ORDERED. `roll_call(state)` is the list of
   everyone out, in the order they came out, with their village and their trade
   and what they are doing now. The finale needs that list, the player should
   watch it grow, and `final_release()` is the one call the last fight makes.

The rules of the house hold without exception. Nothing here supplies an answer
to a coding problem. None of it exists in a measured run — `available_in()` is
the same gate the quest board uses. No captive is written as a prize, there is
nothing romantic or sexual anywhere in this file, and the way somebody is
dressed is a fact about their trade and their weather and never about the
person looking at them.

Wiring is at the bottom, in WIRING, and the engine-side contract in CONTRACT.
"""
from __future__ import annotations

from dataclasses import dataclass

from . import config
from . import dungeons as dungeonmod
from . import forge
from . import items
from . import potions
from . import quests
from . import world

# ---------------------------------------------------------------------------
# What a rescue is worth
# ---------------------------------------------------------------------------
# Not authored. story.band_for() already says how hard a region is, by reading
# the rung of the metal that comes out of its ground, and quests.REWARD_TIERS
# already owns the XP and gold curve. A boss pays the tier its region's band
# maps to and there is no per-boss number anywhere in this file, which is the
# only way the curve stays the shape quests.py drew.

TIER_FOR_BAND = {
    "GUIDED": 2, "TUTORIAL": 2, "EASY": 3, "MEDIUM": 4, "HARD": 4,
    "ELITE": 5, "BOSS": 5,
}

# Strength of the potion a band may hand over, and how many. Both are checked
# against potions.found_at() and potions.CARRY_CAP by validate(), so a band
# that cannot brew a thing cannot pay it and a pouch cannot be overfilled.
POTION_STRENGTH = {"EASY": "small", "MEDIUM": "small", "HARD": "medium",
                   "ELITE": "hefty", "BOSS": "hefty"}
POTION_COUNT = {"small": 3, "medium": 2, "hefty": 2}

# How much a mentor thinks of you for getting their region's people back.
# story.FAVOR_TIERS is the scale; these are deliberately of a size with the
# quest grants rather than larger, because a rescue is already paying in four
# other currencies.
FAVOR_BY_TIER = {2: 2, 3: 3, 4: 4, 5: 5}


# ---------------------------------------------------------------------------
# Boons
# ---------------------------------------------------------------------------
# What a freed person is worth to the player afterwards, expressed in the same
# vocabulary items.EFFECT_LABELS gives the equipment and quests.TOWN_UPGRADES
# gives the rebuilt buildings, so the engine folds them in with the arithmetic
# it already has.
#
# The allowlist below is the whole of what a person is allowed to be worth. It
# holds rest, stock, repair, scheduling, a road and a second pair of hands. It
# holds nothing that reads a problem, names a weakness, reveals a value or
# deepens a hint, and it never will: a rescued villager who quietly starts
# solving encounters for you would undo the argument the entire game is making.

BOON_EFFECTS_ALLOWED = frozenset({
    "armor_repair", "mana_max", "mana_regen", "stamina_max", "stamina_regen",
    "hint_discount", "loot_luck", "rank_grace", "shrine_bonus",
    "retest_charges", "interval_stretch", "srs_preview", "retry_grace",
    "combo_shield", "edge_ward", "declare_slots", "bench_slots",
    "iteration_bonus", "first_try_bonus", "refactor_bonus",
})

# Effects that read the problem, the enemy or the answer. Named here so the
# refusal is explicit rather than implied by an allowlist somebody might one
# day "just add one thing" to.
BOON_EFFECTS_REFUSED = frozenset({
    "reveal_category", "probe_reveal_value", "perf_insight", "weakness_scan",
    "probe_charges", "probe_refund",
})


# ---------------------------------------------------------------------------
# Roads
# ---------------------------------------------------------------------------
# Two of the freed open a route, which is the oldest thing a rescued scout has
# ever been good for. Shape is deliberately quests.SHORTCUTS' shape so the
# overworld draws both from one loop, and the ids carry a `cap_` prefix so the
# two registries can never collide.

ROUTES = {
    "cap_rigged_span": {
        "name": "The Rigged Span", "from": "twin_pointer_pass",
        "to": "coding_coliseum",
        "line": "Hessa and Torv rigged the last span from both ends at once, "
                "purely to settle it, and the argument is now a road. Neither "
                "of them concedes that the other was right, and the road is "
                "there either way.",
    },
    "cap_marked_line": {
        "name": "The Marked Line", "from": "graph_wastes", "to": "dp_ruins",
        "line": "Jessamy Roke has cut her marks back into the Wastes as far as "
                "the Ruins. Every fork carries the shorter way on the left "
                "stone. She says the Wastes had roads all along and only ever "
                "lacked somebody willing to say which ones were any good.",
    },
}


# ---------------------------------------------------------------------------
# The shape of a person
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Captive:
    id: str
    name: str
    trade: str
    boss: str            # world.BOSS_BY_ID id — who took them
    home: str            # world.REGION_BY_ID id — the village they came out of
    bearing: str         # dress and carriage, which follow from trade and weather
    opinion: str         # something they held before you arrived
    lines: tuple         # what they say at the moment the cage opens
    afterwards: str      # what they say in their village, forever after
    change: str          # what is physically different at home because of them
    sprite: str = "villager"
    boon: str = ""       # BOONS id, or "" for the ones who simply go home
    gift: str = ""       # items.BY_ID id they hand over, or ""

    @property
    def held_in(self) -> str:
        """The region the cage is in — the boss's, which is not always home."""
        return world.BOSS_BY_ID[self.boss]["region"]


@dataclass(frozen=True)
class Holding:
    """A boss, and the room it keeps people in."""
    boss: str
    dungeon: str         # dungeons.DUNGEON_BY_ID id — the region's own delve
    chamber: str         # what you see on entering, before the fight
    release: tuple       # the narrator, at the moment it falls
    handover: str        # the line the reward is handed over under
    potion: str          # HEALTH / FOCUS / ANTIDOTE — what this region hands you


# ---------------------------------------------------------------------------
# The people
# ---------------------------------------------------------------------------
# Read down the regions and you should be able to tell, without the region
# field, where each of them is from: the plateau dresses for wind, the marsh
# dresses for water, the citadel dresses for inspection and the Wastes dress
# for walking. Nobody here is a villager-shaped noun with a name attached.
#
# Three of them mention a small green bead. They do not know what it is. Nobody
# in the Realms does yet, and none of them is told — see the story bible on the
# Green Index, which is the one thread in this file that is not resolved inside
# it.

CAPTIVES = [

    # -- The Hash Titan, Hashmap Highlands ---------------------------------
    Captive(
        id="sennet_crale", name="Sennet Crale", trade="key-cutter",
        boss="hash_titan", home="hashmap_highlands", sprite="smith",
        bearing="Sixty, and built like the bench she works at. Leather apron "
                "gone shiny at the hip, a ring of forty blanks at her belt she "
                "has not stopped touching since the cage opened, and the "
                "wind-burn every Highlander over fifty wears across the nose.",
        opinion="Holds that a key which opens two doors is not a key, it is an "
                "accident, and that the Titan's whole method was the work of "
                "something that has never once had to finish a job by dark.",
        lines=("Nine weeks. I scratched them on the post, because it was not "
               "counting and one of us had to be.",
               "It had my blanks off me and it tried them. All of them. "
               "Against everything. I watched a thing the size of a granary "
               "spend four days learning what an apprentice knows by their "
               "first winter, which is that if you are reaching for the second "
               "key you cut the first one wrong.",
               "Right. Where is my apron."),
        afterwards="I am at the bench by the toll-house most days. Bring me the "
                   "shape of a lock and I will cut for it once, properly, "
                   "instead of nine times hopefully.",
        change="The key-cutter's bench is lit again beside the Highland "
               "toll-house, and the plateau's vaults open on the first try.",
        boon="cut_for_the_lock", gift="ward_lightning",
    ),
    Captive(
        id="ibb_tallow", name="Ibb Tallow", trade="goatherd of the high vaults",
        boss="hash_titan", home="hashmap_highlands", sprite="villager",
        bearing="Forty, sunburnt in bands where the scarf sat, in a felted coat "
                "that smells of goat and rain and has been mended in nine "
                "colours because nine colours were what was going spare.",
        opinion="Thinks the vault-wardens are precious about the vaults. Her "
                "goats have been finding the sealed ones for six generations, "
                "which is a survey, and nobody has written it down or paid her "
                "for it.",
        lines=("Are the goats up. Do not make that face at me. Twenty-one head "
               "is a year's living and I have had a long dark while to think "
               "about it and I have thought about very little else.",
               "It kept me because I can tell a real door from a hollow by the "
               "sound. I told it wrong twice. It noticed the second time, and "
               "I have a rib that clicks now, and I would like that written "
               "down somewhere as well."),
        afterwards="Nineteen of twenty-one came through the winter, which is "
                   "better than I had any business hoping for. Sit down and "
                   "eat something.",
        change="A herd works the high sealed vaults again, and a cheese-press "
               "and a bread oven stand at the head of the pass where there was "
               "nothing but wind.",
        boon="the_high_herd",
    ),

    # -- The Three-Sum Hydra, Array Caverns --------------------------------
    Captive(
        id="nessa_vey", name="Nessa Vey", trade="alcove-numberer",
        boss="three_sum_hydra", home="array_caverns", sprite="surveyor",
        bearing="Thirty, chalk to the elbow and lamp-black under both eyes, in "
                "the quilted cave coat everyone down there wears against the "
                "cold that comes up out of the floor rather than down from the "
                "sky.",
        opinion="A zero partisan, loudly. The renumbering after the east "
                "rockfall took her two years and she will tell you that the "
                "argument about where counting starts has killed more "
                "lamp-runners than the falls have.",
        lines=("I have numbered this cavern my whole working life and it took "
               "me somewhere with no numbers on it at all. That is the part I "
               "want to say out loud once and then never again.",
               "Four thousand alcoves out there and I know every one of them "
               "by its mark. In here I did not know which wall I was against. "
               "You can put that in your report."),
        afterwards="East range is renumbered and the marks are cut, not "
                   "painted, so the damp cannot argue with them. Ask me where "
                   "anything is. Go on, ask me.",
        change="The east range carries cut numbers again, and the Caverns stop "
               "losing a fortnight every time the damp takes a painted mark.",
    ),
    Captive(
        id="josa_fell", name="Josa Fell", trade="lamp-runner",
        boss="three_sum_hydra", home="array_caverns", sprite="runner",
        bearing="Twenty-four, whip-thin the way anyone is who runs a lamp line "
                "twice a shift, in a short cave coat cut off at the hip so it "
                "cannot catch, with a burn ladder up the inside of the right "
                "forearm from twelve years of reaching past a wick.",
        opinion="Her twin ran the other half of the same line. She holds that "
                "the Caverns should have known there were two of them, and "
                "that a place which cannot tell two people apart will lose "
                "one of them eventually.",
        lines=("There were two of us in here. Do not look like that — Sera "
               "Fell walked out on day four, she always did have the better "
               "sense of direction, and she will not let me forget it as long "
               "as I live.",
               "The thing had us down as one person. It is the only reason I "
               "am standing up. It stopped counting us and started guessing, "
               "and a guess is where you get out."),
        afterwards="Both ends of the line are lit again. She runs from the "
                   "sump, I run from the gate, and we meet in the middle "
                   "whether the shift wants us to or not.",
        change="The lamp line burns from both ends, and nothing in the Sunken "
               "Index sits dark for a whole shift any more.",
        boon="lamps_both_ends",
    ),

    # -- The Window Wraith, Sliding Window Marsh ---------------------------
    Captive(
        id="perrin_oake", name="Perrin Oake", trade="reed-cutter and thatcher",
        boss="window_wraith", home="sliding_window_marsh", sprite="forager",
        bearing="Sixty-odd, oilcloth to the knee and bare below it, arms "
                "stained to the elbow with marsh tannin that does not come off "
                "and has not for forty years, hook still through his belt "
                "because nothing was going to take it off him.",
        opinion="Cuts a reed bed in one pass. Has no patience at all with the "
                "young ones who lose their count and start the bed again from "
                "the near end, and says the bed does not reset just because "
                "they did.",
        lines=("I went towards a light. In the marsh. At night. Sixty years I "
               "have lived on that water and I went towards a light in it.",
               "Do not tell Fenn Ilder. I am aware Fenn will find out. I would "
               "simply like it not to be from you.",
               "The cut on the north bed is four days from spoiling. Are you "
               "coming, or are you going to stand in the water."),
        afterwards="North bed is cut and the huts are rethatched, and I have "
                   "told this story on myself eleven times now, which is the "
                   "only way to take the sting out of a thing.",
        change="Every crossing hut in the marsh has a dry roof on it again, "
               "and a bundle of reed by the door for whoever comes through "
               "cold.",
        boon="dry_crossings", gift="marsh_waders",
    ),
    Captive(
        id="ysold_quen", name="Ysold Quen", trade="marsh apothecary",
        boss="window_wraith", home="sliding_window_marsh", sprite="keeper",
        bearing="Fifties, barefoot and mud to the shin, work skirt hemmed "
                "clear of the water line, a bandolier of stoppered horn vials "
                "across the chest, and hands cracked from working cold water "
                "in every month with an R in it.",
        opinion="Furious, and specifically. The Wraith took her with the whole "
                "season's antidote on her back and then let it stand until it "
                "spoiled, and she has views about waste that predate the "
                "Wraith by about thirty years.",
        lines=("Eleven months of stillwork. Bog myrtle, cut at the turn, dried "
               "slow. It let the lot go over and it did not even want it.",
               "Two children on the reedways went without this winter because "
               "of that. I know their names. I will be saying them at it for "
               "some time yet, and it is dead, and I am still not finished.",
               "Give me a week and the shelf will be better than it was. It "
               "was going to be better than it was anyway. That is the job."),
        afterwards="Shelf is stocked and the season is in. If you are going "
                   "deep, take the medium antidote and do not be proud about "
                   "it — pride is how the last one came back on a hurdle.",
        change="The apothecary's shelf on the reedway is full again, and the "
               "marsh villages have antidote in the house before they need it "
               "rather than after.",
        boon="the_shelf_restocked",
    ),

    # -- The Rolling Titan, Sliding Window Marsh ---------------------------
    Captive(
        id="alek_rill", name="Alek Rill", trade="tide-caller",
        boss="rolling_titan", home="sliding_window_marsh", sprite="keeper",
        bearing="Thirty-five, rope-belted, one shoulder permanently higher "
                "than the other from twenty years on the same pole, and still "
                "holding the pole, which he has not let go of and does not "
                "intend to discuss.",
        opinion="Calls the high water from the pole at the reedway head every "
                "morning. Holds that the marsh is not dangerous, it is simply "
                "on a schedule that nobody bothers to learn.",
        lines=("It took the pole. I would like that understood properly. I was "
               "on the pole at the time, and it took the pole, and I came with "
               "the pole.",
               "Three weeks of high water uncalled. Somebody has drowned. I do "
               "not know who yet and I would rather find out standing on dry "
               "ground than in here."),
        afterwards="The water is called at dawn and at the turn, off the same "
                   "pole, and it is nailed up on the crossing post for anyone "
                   "who cannot be bothered to come and listen to me.",
        change="Tide boards stand at every marsh crossing, and nobody in the "
               "reedways starts a long carry an hour before the water comes "
               "up.",
    ),

    # -- The Twin Pointer Behemoth, Twin Pointer Pass ----------------------
    # The argument is the point. They were taken mid-sentence, they have had
    # three weeks of cage in which to sharpen it, and being rescued does not
    # rank anywhere near finishing it. Neither of them is angry at you. They
    # are not really angry at each other either; they have simply been at this
    # for nine years and would like a verdict.
    Captive(
        id="hessa_dunmar", name="Hessa Dunmar", trade="span-rigger",
        boss="twin_behemoth", home="twin_pointer_pass", sprite="climber",
        bearing="Forty, in a fleece-lined pass coat gone white at the seams "
                "with frost, harness still buckled over it because she was "
                "working when they came, and the flat mountain squint of "
                "somebody who has spent her life judging distances in bad "
                "light.",
        opinion="You rig a span from both ends and meet in the middle, because "
                "the middle is where the error collects and you want to be "
                "standing on it when it shows up.",
        lines=("— which you would know, Torv, if you had ever once walked back "
               "along your own work instead of admiring it from the far side.",
               "Yes. Thank you. We are both extremely grateful. Torv, the "
               "error lands in the middle. It always lands in the middle. That "
               "is what the middle is for.",
               "He has had three weeks to think of a better answer and he has "
               "used them very badly."),
        afterwards="Span is up. Both ends, met in the middle, four days. He "
                   "still says it was luck. I have stopped needing him to say "
                   "otherwise, which he tells me is a kind of winning.",
        change="The last span of the Pass is rigged and walkable, and the "
               "convoys stop unloading at the gap.",
        boon="the_rigged_span", gift="ward_cold",
    ),
    Captive(
        id="torv_bael", name="Torv Bael", trade="span-rigger",
        boss="twin_behemoth", home="twin_pointer_pass", sprite="climber",
        bearing="Fifty, shorter than his rope suggests, wool cap welded to his "
                "head, gloves cut off at the second knuckle so he can feel a "
                "bad lay in a cable, and a slow way of looking at a drop before "
                "he says anything at all.",
        opinion="You rig from one end and carry it the whole way across, "
                "because then one person owns every plank, and a span where "
                "everyone owns half is a span nobody owns.",
        lines=("One person, one span, end to end. If the error is in the "
               "middle, Hessa, it is because two people put it there.",
               "We are grateful. I want that said, and said properly, because "
               "she will talk over it. You came a long way into a bad place "
               "for two riggers nobody sent for.",
               "Now. About the middle."),
        afterwards="We rigged it her way and mine, at the same time, to settle "
                   "it. Came out four days early. Neither method won, which is "
                   "the most annoying possible result and I am told I must live "
                   "with it.",
        change="The Pass carries a second walkable line, built twice over "
               "because two people could not agree, which the convoy master "
               "describes as the most productive argument in the region's "
               "history.",
        boon="the_rigged_span",
    ),

    # -- The Matrix Golem, Matrix Citadel ----------------------------------
    Captive(
        id="ona_kesk", name="Ona Kesk", trade="floor-plan copyist",
        boss="matrix_golem", home="matrix_citadel", sprite="scribe",
        bearing="Late twenties, citadel livery with the squared collar, chalk "
                "to the second knuckle of both hands, and the citadel habit of "
                "walking corners rather than diagonals even out in open "
                "ground where it makes no sense whatever.",
        opinion="Thinks the Archivist keeps the only copy of too many things. "
                "Has been saying so for four years, in writing, in triplicate, "
                "which she notes is the correct way to make that particular "
                "complaint.",
        lines=("I was in the north hall when the floor turned. Not after. "
               "During.",
               "I can tell you what that is like and I have had to tell nine "
               "people already and it has made me a curiosity, which is worse "
               "than the turning was. The plan does not move. You move, and "
               "everything you knew about where you were is now about "
               "somewhere else.",
               "I would like to be a copyist again rather than an anecdote."),
        afterwards="Muster yard, first bell, every morning. Ten minutes of "
                   "turning drill and then everybody goes to work. It is not "
                   "interesting and that is the entire virtue of it.",
        change="The citadel runs a rotation drill at first bell, and nobody "
               "posted to the Turning Keep is surprised by a floor twice.",
        boon="the_morning_rotation", gift="ward_brute",
    ),
    Captive(
        id="wenna_ives", name="Wenna Ives", trade="squad runner",
        boss="matrix_golem", home="matrix_citadel", sprite="soldier",
        bearing="Nineteen, drill boots she has outgrown and will not replace, "
                "hair cut to the regulation length with a knife rather than by "
                "anyone competent, and the citadel's parade stillness, which "
                "she holds even in a cage because it was beaten into her at "
                "eleven.",
        opinion="Her father is the Drillmaster and she has decided, out loud, "
                "that his muster drill is wrong. Hold the line, close the gap, "
                "hold the line. The Golem took nine people out of a held line. "
                "She intends to rewrite it and is not much interested in "
                "whether that is allowed.",
        lines=("Do not tell him I was frightened. Tell him the drill failed. "
               "Those are different reports and only one of them is useful.",
               "We held. Everyone did exactly what we practise. It walked "
               "through the middle of a held line and took the four people in "
               "the middle of it, and then the line closed up behind them, "
               "because that is what we practise.",
               "I am going to write the new one. He can sign it or not."),
        afterwards="New muster stands: the line breaks and re-forms wide, "
                   "twice. He signed it. He made me read it out to the whole "
                   "yard first, which I think was the price.",
        change="The citadel musters in a line that is allowed to break, and "
               "the Drillmaster has stopped calling the old form at all.",
    ),

    # -- The Editor Automaton, Matrix Citadel ------------------------------
    Captive(
        id="calla_prowd", name="Calla Prowd", trade="amendment clerk",
        boss="editor_automaton", home="matrix_citadel", sprite="clerk",
        bearing="Forties, ink on the side of the left hand the way it goes on "
                "someone who writes across their own work, citadel grey worn "
                "soft, spectacles on a cord because she has lost four pairs "
                "and admits it freely.",
        opinion="A record that can be silently changed is not a record. She "
                "has said this in meetings for eleven years and been told it "
                "is a matter of tone.",
        lines=("It undid my day. Every night. I would write the amendments, "
               "and in the morning the page would be the page from the "
               "morning before, and my hands would be tired.",
               "By the eighth day I started writing them in a different order, "
               "with the important one last, because whatever it was doing, it "
               "was doing it from the end backwards and it was not very good "
               "at it. That is how I kept four days of work. Four days out of "
               "thirty.",
               "I would like the thirty back. I am aware that is not on offer."),
        afterwards="Every change to the citadel record goes in the change "
                   "book now, dated, signed, and never rubbed out. It cost me "
                   "eleven years and a month in a cell to win an argument "
                   "about stationery.",
        change="The citadel keeps a change book, and an amendment in the "
               "Matrix Citadel can no longer be quietly unmade.",
        boon="the_amendment_book",
    ),

    # -- The Tree Dragon, Binary Tree Canopy -------------------------------
    # The bible's rule: mitigate, do not prevent. This is the one place in the
    # file where somebody does not come back, it is stated once, plainly, by
    # the man it happened to, and it is never mentioned again or paid for with
    # a reward. He gets to be tired about it rather than tragic.
    Captive(
        id="oskar_lind", name="Oskar Lind", trade="rope-splicer of the canopy",
        boss="tree_dragon", home="binary_tree_canopy", sprite="climber",
        bearing="Fifty-five, small and long-armed, in a splicing belt with the "
                "fid and the marlinspike still in it, canvas trousers worn "
                "through at the inside knee where a climber grips, and a habit "
                "of testing anything he is handed with two sharp pulls before "
                "he looks at it.",
        opinion="Believes rope tells the truth earlier than people do, and "
                "that the canopy's whole safety problem is that a fork looks "
                "the same whether or not it will hold you.",
        lines=("Two of us went up. Myself and Tam Brisk, who was seventeen "
               "and better at it than I was at thirty. He is not coming down.",
               "I have said that now. I will say it once more to Wren and then "
               "I am going to want to do some work.",
               "Every line in this canopy is nine years old. I am going to rig "
               "it again from the trunk out, and this time there is a second "
               "line on every fork, and nobody argues with me about the weight "
               "of it."),
        afterwards="Second line on every fork from the trunk to the high "
                   "crown. It costs twice the rope and half again the time. "
                   "Alder asked me what it buys and I told him it buys the "
                   "afternoon when he is wrong about a branch.",
        change="Every fork in the Split Canopy carries a second line, and the "
               "climbers' ledger has gone a full season without a fall.",
        boon="the_second_line", gift="wayfarers",
    ),

    # -- The Path-Sum Ent, Binary Tree Canopy ------------------------------
    Captive(
        id="ferris_ames", name="Ferris Ames", trade="tithe-counter of the ends",
        boss="path_sum_ent", home="binary_tree_canopy", sprite="clerk",
        bearing="Sixty, birdlike, in a canopy coat with a counting board "
                "strung across it and a tally of notched sticks at the hip "
                "that the Ent apparently found interesting enough to leave him.",
        opinion="A branch with one twig on it is not an end. The tithe ledger "
                "has counted it as one for nine years, the canopy has been "
                "overcharged for nine years, and he has been ignored for "
                "nine years, which he mentions early and often.",
        lines=("It took me over an argument. I want you to understand what a "
               "good day that makes this, in the end. It cared what an end "
               "was. Nobody in the rookery has cared what an end was since "
               "before you were born.",
               "A branch that carries one twig is still a branch. It goes on. "
               "You do not stop counting at it and call the count finished. "
               "Nine years I have said that.",
               "It agreed with me. That is the worst sentence I have ever said "
               "out loud and I have now said it to you."),
        afterwards="Recount is done. Nine years of tithe, nine years of "
                   "overcharge, and the rookery owes four villages a great "
                   "deal of fruit. I am not popular. I am correct, and I have "
                   "been both before.",
        change="The canopy tithe is recounted end by end, and four villages "
               "under the Split Canopy are paid back a decade of fruit.",
    ),

    # -- The Graph Necromancer, Graph Wastes -------------------------------
    Captive(
        id="jessamy_roke", name="Jessamy Roke", trade="road-scout and sign-cutter",
        boss="graph_necromancer", home="graph_wastes", sprite="messenger",
        bearing="Thirty, in a long dust coat the colour of everything out "
                "there, chisel and hand-maul slung where a weapon would be, "
                "boots resoled so many times the uppers are the only original "
                "part, and a walker's way of standing that never quite settles.",
        opinion="The Wastes are not trackless. They are unmarked, which is a "
                "different problem and a solvable one, and she has been "
                "solving it alone for nine years because the couriers' guild "
                "will not fund a chisel.",
        lines=("It wanted the marks. Not me. It has no use for a person, but "
               "it very much wanted to know which of those roads were short "
               "and which merely went somewhere, and I am the only one who "
               "has walked all of them.",
               "So I gave it the long ways. Every time. For a month. It never "
               "once checked, because a thing that cannot learn cannot tell "
               "when it is being taught.",
               "There was a green bead in my coat seam the day they took me. "
               "Glass, about so big. I did not put it there and I have thought "
               "about it more than I would like."),
        afterwards="Marks are cut from the waystation out to the Ruins, "
                   "shorter way on the left stone at every fork. Corvin can "
                   "run it in the dark now. He has, twice, and complained "
                   "about it both times.",
        change="Cut marks run through the Wastes from the waystation to the "
               "Ruins, and the couriers stop guessing which of two roads is "
               "the short one.",
        boon="the_marked_line", gift="earthed_sabatons",
    ),
    Captive(
        id="abel_sarrow", name="Abel Sarrow", trade="grave-warden of the Wastes",
        boss="graph_necromancer", home="graph_wastes", sprite="warden",
        bearing="Seventy, in a coat that has been black long enough to be "
                "grey, with the list-case on a strap across his chest — brass, "
                "dented, and still shut — and the flat unhurried voice of "
                "somebody whose work has never once benefited from being "
                "rushed.",
        opinion="Keeps the list of who is buried where in the Wastes. Holds "
                "that this is the single most dangerous document in the region "
                "and that the guild's decision to keep it in one copy, on one "
                "old man, walking, is the most sensible thing they have ever "
                "done.",
        lines=("It asked me for the list. It asked politely, which I had not "
               "expected and did not care for.",
               "I said no. I would like to be remembered as having said no "
               "calmly. I did not say it calmly, and there is no point in "
               "anyone pretending otherwise, least of all me.",
               "The case is still shut. Four hundred and six names, and not "
               "one of them got up. That is the whole of my career and I will "
               "take it."),
        afterwards="Lists are back in the ground where the lists belong — one "
                   "copy in the waystation floor, one on me, and one buried, "
                   "which is a joke I have been making for forty years and "
                   "nobody has ever laughed at.",
        change="The Wastes' burial lists are kept in three places again, and "
               "the roads out of the Lattice have stopped producing things "
               "that used to have names.",
    ),

    # -- The Complexity Wyrm, Complexity Tower -----------------------------
    Captive(
        id="iolanthe_brask", name="Iolanthe Brask", trade="rent-assessor of the tower",
        boss="complexity_wyrm", home="complexity_tower", sprite="clerk",
        bearing="Forties, fur collar over tower livery, fingerless gloves, and "
                "a ledger she carried up nine floors and would not put down, "
                "with a stub of pencil tied to it because pencils walk.",
        opinion="Refuses to round. The tower's rents double with every floor "
                "and every assessor before her wrote 'approximately', which "
                "she regards as a species of lying that got a tenant evicted "
                "in her first year.",
        lines=("Ninth floor. It carried me up from the ninth, and I counted "
               "the flights, because that is what I do with my hands when I "
               "am frightened.",
               "Eleven flights. Each one longer than the last, and not a "
               "little longer — twice. You can feel it in the knee before you "
               "can prove it in a ledger.",
               "The cold was survivable. What I could not bear was that it "
               "kept asking me to estimate."),
        afterwards="Rents are posted at the foot of the stair now, floor by "
                   "floor, exactly, with no word like 'about' anywhere on the "
                   "board. Half the tower thinks I have made them poorer. I "
                   "have made them informed, which is cheaper.",
        change="The tower posts its true costs at the foot of the Doubling "
               "Stair, floor by floor, and nobody climbs it on a guess again.",
        boon="published_rents", gift="crampons",
    ),
    Captive(
        id="corin_ashe", name="Corin Ashe", trade="stair-mason",
        boss="complexity_wyrm", home="complexity_tower", sprite="villager",
        bearing="Sixty, stone dust in the creases of both hands and "
                "permanently in one eyebrow, a bad knee he does not mention "
                "and favours constantly, and the tower mason's leather cap "
                "with the ear flaps down from the first frost to the last.",
        opinion="The tower adds a floor. He builds the stair to it. It adds "
                "another. He has been building the same stair since he was "
                "nineteen and he has no intention of finishing, which he "
                "regards as job security rather than as a metaphor.",
        lines=("Forty-one years on one staircase. People say that to me like "
               "it is sad. I have a crew, and a plan, and a bad knee, and a "
               "ninth of the tower is stone I cut.",
               "It did not want me for anything. I want to be clear about "
               "that. I was simply on the stair when it came down the stair.",
               "There is a landing at the halfway that I have been asking for "
               "since I was thirty. I am going to build the landing now while "
               "everyone is still feeling generous about me."),
        afterwards="Landing is in, halfway up, with a bench and a water butt "
                   "and a roof on it. Ember says it will not make the climb "
                   "shorter. It does not have to. It has to make it "
                   "survivable.",
        change="A landing with a bench and a water butt stands halfway up the "
               "Doubling Stair, and the tower's porters stop arriving at the "
               "top unfit to work.",
    ),

    # -- The Serialization Lich, Recursive Forest --------------------------
    Captive(
        id="wilmot_tace", name="Wilmot Tace", trade="grove-scribe",
        boss="serialization_lich", home="recursive_forest", sprite="scribe",
        bearing="Forties, thin, in a waxed forest coat with a plan-case on the "
                "back and a hand that will not quite stop shaking, which he "
                "notices you noticing and does not apologise for.",
        opinion="His trade is writing down the exact shape of a grove — every "
                "trunk, every spacing, every angle — so that after a burn it "
                "can be put back exactly. He holds that a description which "
                "cannot be read back into the thing it described is not a "
                "description. It is a drawing.",
        lines=("It had me write the inner grove down. Then read it back. Then "
               "write it again, because the copy was missing something.",
               "Forty-one times. And here is what I cannot get past, and what "
               "I am going to be getting past for the rest of my life: it was "
               "right. Every copy was missing something and it knew which. The "
               "forty-second was correct.",
               "It took the forty-second away. There was a green bead on the "
               "table it took off me on the first day and it was very "
               "interested in that, and then it was not. I would like to know "
               "what it wanted. I expect I will not."),
        afterwards="I have replanted the east burn off my own record — trunk "
                   "for trunk, spacing for spacing. Halla says you cannot "
                   "replant a forest from a page. You can. It is slow and it "
                   "is exact and it is the only thing I know how to do.",
        change="The east burn of the Recursive Forest is replanted exactly "
               "from Wilmot's record, and the inner grove has a written shape "
               "again that survives the fire that takes it.",
        boon="the_replanted_grove", gift="lanternshoes",
    ),
    Captive(
        id="corr_vane", name="Corr Vane", trade="woodcutter",
        boss="serialization_lich", home="recursive_forest", sprite="forester",
        bearing="Thirty-eight, axe-shouldered, in the Vane family's canvas "
                "with the shoulder patch Halla sews on all of them, and a "
                "coil of rope on his belt that is new, and short, and that he "
                "bought the day after he got out.",
        opinion="Everybody knows you do not go into the inner grove after "
                "somebody alone. He knows it. He has said it to apprentices "
                "for twenty years. He went in alone anyway, for Wilmot, and he "
                "is not interested in being told that this was brave.",
        lines=("I went in on my own. My sister teaches people not to do that. "
               "I taught people not to do that.",
               "You get one clearing in and there is a smaller one inside it, "
               "and the same stone, and the same lightning-split ash, and you "
               "are certain you have been here and you are wrong and you are "
               "also right.",
               "Rope. That is the whole of what I have got out of this. A rope "
               "and a second person and neither of them is an insult to "
               "anybody's woodcraft."),
        afterwards="Nobody walks the inner grove alone out of this house. Rope "
                   "on the belt, second person on the other end of it, and I "
                   "have stopped pretending that is a thing only the nervous "
                   "do.",
        change="The Recursive Forest keeps a rope discipline: two on every "
               "entry into the inner grove, and a line paid out behind them "
               "the whole way down.",
    ),

    # -- The Bug Demon, Debugging Dungeon ----------------------------------
    Captive(
        id="hedda_ferrin", name="Hedda Ferrin", trade="plate-smith",
        boss="bug_demon", home="debugging_dungeon", sprite="smith",
        bearing="Forties, forearms like cable, leather apron scorched through "
                "in two places and patched with plate offcuts, and a burn scar "
                "across the back of one hand in the exact shape of a buckle "
                "she has never explained to anybody.",
        opinion="Every crack has an address. A smith who patches without "
                "reading the crack is not a smith, she is a person with a "
                "hammer, and the Armorer's forge has three of those on the "
                "books right now.",
        lines=("It kept me to mend what it broke. It broke them cleverly, I "
               "will give it that much and no more.",
               "It would hand me a plate and tell me the plate was sound. And "
               "it was. On the bench. Every plate it gave me was perfect on "
               "the bench and came back off the field in pieces, and it could "
               "not be made to see a difference between those two facts.",
               "Thirty-one days of mending armour for the thing that broke "
               "it. I have kept the tally. I am going to mend for free until "
               "the tally is clear and then we will see how I feel."),
        afterwards="Rate is down and the annealing runs deeper, and I read "
                   "every crack aloud before I touch it, the way Garrick does, "
                   "which I used to think was theatre and now do not.",
        change="The forge takes plate at a working rate again, the annealing "
               "runs deep, and no repair leaves the Debugging Dungeon without "
               "somebody having read the crack out loud first.",
        boon="the_forge_rate", gift="cinder_greaves",
    ),
    Captive(
        id="varna_strand", name="Varna Strand", trade="test-caller of the forge yard",
        boss="bug_demon", home="debugging_dungeon", sprite="warden",
        bearing="Fifties, cropped grey, a carrying voice she does not raise, "
                "forge leathers worn only on the left because she stands side "
                "on to the heat, and a list board on a cord that the Demon "
                "took off her and that she took back.",
        opinion="Her whole trade is standing in front of a finished plate and "
                "naming, out loud, every way it could fail, until the smith "
                "has an answer for each one. She holds that a yard where "
                "nobody is allowed to ask that question is a yard that ships "
                "beautiful rubbish.",
        lines=("It hated being asked. That is the entire reason I am down "
               "here. I asked it what happens to its work in the rain and it "
               "put me in a cell.",
               "I am not brave and this was not defiance. It is a list. I have "
               "read the same list out in that yard for twenty-six years and I "
               "was not going to stop reading it because the thing in front of "
               "me was large.",
               "Right. Somebody get me up. My knees have gone and I would "
               "rather that was not the first thing anyone sees."),
        afterwards="Yard call is back at the third bell. Bring your plate, "
                   "stand there, and answer me. If you cannot say how a thing "
                   "fails you do not know that it works, you only know that it "
                   "has not failed yet.",
        change="The forge yard calls its list again at the third bell, and "
               "nothing leaves the Debugging Dungeon without somebody having "
               "said out loud how it could break.",
    ),

    # -- The Interviewer, the Null King's Castle ---------------------------
    # The castle has no village of its own — nothing lives there, which is the
    # point of it. So the last boss took its three from the one place the
    # player cannot be neutral about: home. They are the only captives in this
    # file whose `home` is not the region they are held in, and the roll call
    # names them last on purpose.
    Captive(
        id="thessaly_brun", name="Thessaly Brun", trade="village schoolteacher",
        boss="the_interviewer", home="python_village", sprite="scholar",
        bearing="Sixties, village wool, a satchel of slates she was carrying "
                "when they came and is still carrying, and the schoolroom "
                "habit of waiting in complete silence until the person in "
                "front of her has finished talking, which she does to you as "
                "well.",
        opinion="Teaches the old words to eleven children in a half-roofed "
                "room, which makes her, by a considerable margin, the most "
                "dangerous person in the Realms to whatever is erasing them. "
                "She has always known that. It is why she does it at the same "
                "hour every day where everyone can see.",
        lines=("Did they keep it up. The drill. Every morning, first bell, ten "
               "minutes, out loud. Did they keep it up without me.",
               "That is not a polite question and I am not asking it politely. "
               "If they kept it up then it did not get what it came for, and "
               "everything else that has happened to me is administrative.",
               "It asked me to name things. It asked all day. I have been "
               "asking children to name things for forty years and I know "
               "exactly what that sounds like when the person asking already "
               "knows the answer and when they do not. It did not know."),
        afterwards="First bell, in the square, ten minutes, out loud, and the "
                   "board goes up the night before so nobody can claim they "
                   "did not know what was being asked. You may attend. "
                   "Everyone may attend. That has never been the difficult "
                   "part.",
        change="The village runs a naming drill in the square at first bell, "
               "and the next day's list is chalked on the board the night "
               "before.",
        boon="the_square_drill",
    ),
    Captive(
        id="yoren_halt", name="Yoren Halt", trade="letter-cutter in stone",
        boss="the_interviewer", home="python_village", sprite="villager",
        bearing="Seventy-eight, deaf on the left and turns his head to put his "
                "good ear at you, stone dust ground permanently into the "
                "knuckles, and a mallet in his belt that three guards "
                "apparently decided was not worth the argument.",
        opinion="Cuts names on doorposts and grave markers, which he will tell "
                "you is one trade and not two. Holds that a name you can wipe "
                "off is not a name, it is a label, and that the village went "
                "wrong when it started painting them.",
        lines=("It wanted its name cut. That is what it took me for. It had a "
               "stone ready and everything.",
               "So I asked it which name. Politely. Same as I would ask "
               "anybody, because a letter-cutter who guesses is a letter-cutter "
               "who has ruined a stone. And it stopped. It had no answer, and "
               "it stood there having no answer, and that was the first hour "
               "in six weeks I was not frightened of it.",
               "Half our village is still gone and I am not going to stand "
               "here and pretend today fixed that. Today got three of us out. "
               "I have been to enough funerals to know the difference and to "
               "take the three."),
        afterwards="I am cutting the doorposts back. Every house that still "
                   "has a door. It is slow work and I am old and I have "
                   "started at the far end of the street on purpose, so that "
                   "if I do not finish, the ones that get done are the ones "
                   "nobody was looking at.",
        change="The village doorposts carry cut names again, starting from the "
               "far end of the street, and the paint pots have been put away.",
    ),
    Captive(
        id="ivo_brannt", name="Ivo Brannt", trade="apprentice to nobody in particular",
        boss="the_interviewer", home="python_village", sprite="apprentice",
        bearing="Sixteen, too tall for last year's coat by a hand's width, "
                "ink on three fingers, and a bundle of copied slate-drills "
                "under his shirt that he has kept dry through six weeks of "
                "castle on the theory that somebody was going to want them.",
        opinion="Has two younger sisters and a lamp with a bad wick. He has "
                "been copying Thessaly's drills at night and running them for "
                "the pair of them, badly, for a year, because eleven places in "
                "that schoolroom were full and his sisters were not in two of "
                "them.",
        lines=("Are they all right. That is the only thing. That is the only "
               "thing I want said first.",
               "I had a green bead in my pocket. It took it out and looked at "
               "it and put it back. Everyone here had one. Nobody remembers "
               "getting it. I have asked eleven people now and I would like "
               "one adult to take that seriously.",
               "I am not frightened of it. I have thought about that for six "
               "weeks and I want to say it while I still mean it. It only "
               "knows what it was given. I am fifteen months into knowing "
               "things it was never given, and I am slow at it, and I am still "
               "gaining."),
        afterwards="Second drill, after the first one, for whoever is too "
                   "small or too late or too embarrassed for the square. We do "
                   "it wrong out loud. Thessaly says getting it wrong where "
                   "people can hear you is the whole lesson and the naming is "
                   "just the excuse.",
        change="A second, smaller drill runs after the village one, for "
               "children who are too late or too shy for the square, and it is "
               "run badly and out loud on purpose.",
        boon="the_lamplit_lesson",
    ),
]

CAPTIVE_BY_ID = {c.id: c for c in CAPTIVES}
BY_BOSS: dict = {}
for _captive in CAPTIVES:
    BY_BOSS.setdefault(_captive.boss, []).append(_captive)
del _captive
BY_HOME: dict = {}
for _captive in CAPTIVES:
    BY_HOME.setdefault(_captive.home, []).append(_captive)
del _captive


# ---------------------------------------------------------------------------
# The rooms they are kept in
# ---------------------------------------------------------------------------
# `chamber` is read when the player enters the boss room, BEFORE the fight. It
# is the whole reason the rest of this module has any weight: a cage you saw on
# the way in is a different fight from a cage you are told about afterwards.
#
# `potion` names which of the three kinds this region hands over. The strength
# and the count come from the band, never from here, so no region can quietly
# hand out a better vial than its own ground can brew.

HOLDINGS = {
    "hash_titan": Holding(
        boss="hash_titan", dungeon="hollow_of_keys",
        chamber="Forty blank keys hang on a nail above two barred alcoves at "
                "the back of the vault floor, sorted by nothing at all. One of "
                "the alcoves has nine weeks of marks scratched inside the "
                "door frame.",
        release=("The Titan comes apart the way a badly kept ledger does, all "
                 "at once and from the middle.",
                 "Somebody in the dark at the back of the chamber says, quite "
                 "clearly: about time."),
        handover="Sennet turns out what the Titan had taken off the toll-house "
                 "and counts it into your hands without once asking whether it "
                 "is yours.",
        potion="FOCUS"),
    "three_sum_hydra": Holding(
        boss="three_sum_hydra", dungeon="sunken_index",
        chamber="Two cages, hung from the ceiling at different heights, at the "
                "far end of a hall whose alcoves stop being numbered about "
                "forty paces in.",
        release=("The last head goes down and the chamber is suddenly only a "
                 "room with water in it.",
                 "Two lamps come on in the cages above you, struck by people "
                 "who kept the means to do it for a month and were saving it."),
        handover="Nessa hands over the Hydra's hoard by the alcove it was "
                 "stacked in, reciting the numbers as she goes, because she "
                 "has been waiting a month to say numbers to somebody.",
        potion="HEALTH"),
    "window_wraith": Holding(
        boss="window_wraith", dungeon="the_long_draw",
        chamber="A reed hurdle pen on a dry hummock, built properly, by "
                "somebody who knows how — which tells you the Wraith made one "
                "of the people in it build the thing.",
        release=("The Wraith thins out over the water and does not so much "
                 "die as fail to be there.",
                 "The hurdles come apart from the inside. They were tied with "
                 "a slip knot. They were always tied with a slip knot."),
        handover="Ysold makes you drink something bitter before she will let "
                 "you near the Wraith's cache, and then hands it over "
                 "itemised.",
        potion="ANTIDOTE"),
    "rolling_titan": Holding(
        boss="rolling_titan", dungeon="the_long_draw",
        chamber="A measuring pole is wedged across the mouth of the chamber at "
                "head height, with a man sitting on it, well out of the water, "
                "looking extremely put upon.",
        release=("The Titan rolls once more and stops, and the water it has "
                 "been pushing ahead of it for three weeks finally goes "
                 "somewhere.",
                 "The pole comes down. So does Alek Rill, who lands badly and "
                 "waves off help."),
        handover="Alek pays you out of the Titan's silt in handfuls, still "
                 "holding the pole under one arm.",
        potion="FOCUS"),
    "twin_behemoth": Holding(
        boss="twin_behemoth", dungeon="converging_span",
        chamber="Two cages at opposite ends of the span chamber, as far apart "
                "as the room allows. Both occupants are shouting. They are not "
                "shouting for help.",
        release=("The Behemoth goes off the span sideways and takes a long "
                 "time about arriving.",
                 "Neither cage notices for several seconds, because the "
                 "argument is at a delicate stage."),
        handover="Hessa and Torv divide the Behemoth's toll-hoard into two "
                 "piles, disagree about the division, recombine it, and hand "
                 "you the lot.",
        potion="HEALTH"),
    "matrix_golem": Holding(
        boss="matrix_golem", dungeon="turning_keep",
        chamber="Two cells set into the north wall, which is not where the "
                "north wall was on the plan you were given, because the plan "
                "you were given was drawn before the last turn.",
        release=("The Golem settles, and the floor plan settles with it, and "
                 "for the first time in nine years the Keep is the shape it "
                 "says it is.",
                 "A voice from the north cell says, flatly, that the cell is "
                 "now on the east wall and somebody should write that down."),
        handover="Ona signs the Golem's stores over to you in triplicate, "
                 "because she has no intention of being the reason a citadel "
                 "audit goes wrong.",
        potion="HEALTH"),
    "editor_automaton": Holding(
        boss="editor_automaton", dungeon="turning_keep",
        chamber="One cell, one desk, one lamp, and a stack of pages that is "
                "exactly as tall today as it was yesterday.",
        release=("The Automaton's last instruction fails to apply and it "
                 "stops, mid-stroke, holding a correction it can no longer "
                 "make.",
                 "The woman at the desk finishes the line she was writing "
                 "before she looks up."),
        handover="Calla enters the Automaton's holdings in the book, dates "
                 "it, signs it, and only then hands it across.",
        potion="FOCUS"),
    "tree_dragon": Holding(
        boss="tree_dragon", dungeon="split_canopy",
        chamber="A rope cage slung in the fork above the Dragon's roost, rigged "
                "with a splicer's neatness, nine years' worth of line and not "
                "one spare fathom of it wasted.",
        release=("The Dragon comes out of the fork and does not go back into "
                 "it.",
                 "Above you, somebody begins cutting himself down, slowly, and "
                 "correctly, testing every hold on the way."),
        handover="Oskar lowers the Dragon's hoard down to you on a line "
                 "rather than dropping it, because dropping things is how "
                 "people below get hurt.",
        potion="HEALTH"),
    "path_sum_ent": Holding(
        boss="path_sum_ent", dungeon="split_canopy",
        chamber="A hollow in the Ent's trunk, closed with living wood, with an "
                "old man inside it who has spent the whole time counting "
                "something aloud.",
        release=("The Ent puts its weight down for the last time and the "
                 "hollow in it opens.",
                 "The counting stops at a number and the number is said out "
                 "loud, twice, so that somebody else has heard it too."),
        handover="Ferris counts the Ent's mast and acorn-hoard into your pack "
                 "and makes you agree the total before he will let go of it.",
        potion="FOCUS"),
    "graph_necromancer": Holding(
        boss="graph_necromancer", dungeon="lattice_of_ruin",
        chamber="Two iron road-cages of the kind the couriers' guild retired "
                "forty years ago, set at the junction of six roads, facing "
                "different ways.",
        release=("The Necromancer's raised things go down all at once, which "
                 "is the only mercy on offer in the Wastes and is genuinely "
                 "one.",
                 "In the quiet afterwards, somebody starts working a chisel "
                 "against a lock, unhurried, as though they have been at it "
                 "for a while."),
        handover="Abel hands over what the Necromancer was keeping and tells "
                 "you which parts of it belonged to the dead, so that you can "
                 "decide with the facts in front of you.",
        potion="HEALTH"),
    "complexity_wyrm": Holding(
        boss="complexity_wyrm", dungeon="doubling_stair",
        chamber="Two cages on the landing, one flight above the Wyrm and "
                "therefore, in this tower, twice as far away as it looks.",
        release=("The Wyrm uncoils down the stairwell and the tower is "
                 "briefly, wonderfully quiet.",
                 "A ledger falls the last flight and lands open, which its "
                 "owner will mention."),
        handover="Iolanthe assesses the Wyrm's hoard, states the true figure, "
                 "declines to round it, and hands it over.",
        potion="FOCUS"),
    "serialization_lich": Holding(
        boss="serialization_lich", dungeon="inner_grove",
        chamber="Two cages in the innermost clearing, and between them a table "
                "with forty-one rejected copies of the grove on it, stacked "
                "neatly, and a forty-second gone.",
        release=("The Lich is written down, read back, and found to be "
                 "missing something.",
                 "Neither of the men in the cages says anything for some "
                 "time."),
        handover="Wilmot hands you the Lich's relics off the table one at a "
                 "time, naming each, because he cannot any longer hand "
                 "anything over without describing it exactly.",
        potion="HEALTH"),
    "bug_demon": Holding(
        boss="bug_demon", dungeon="cracked_ward",
        chamber="A forge cell with an anvil in it, a month of tally marks on "
                "the wall beside it, and a rack of mended plate that is, on "
                "inspection, mended perfectly.",
        release=("The Demon fails in the field rather than on the bench, "
                 "which is the only way it was ever going to.",
                 "Somebody puts a hammer down on an anvil, once, deliberately, "
                 "and the sound goes all the way up the ward."),
        handover="Hedda weighs out the Demon's stock of metal and stands over "
                 "you while you take it, on the grounds that she did not spend "
                 "thirty-one days on this for somebody to leave half of it.",
        potion="HEALTH"),
    "the_interviewer": Holding(
        boss="the_interviewer", dungeon="unlabelled_halls",
        chamber="Three chairs in an unmarked room, a long way in. Nobody is "
                "chained to them. There is no lock on the door and there has "
                "never needed to be, because none of the halls outside it is "
                "labelled and the three people sitting there are from a "
                "village nine days' walk away.",
        release=("The Interviewer stops asking. It is not a death and nobody "
                 "in the room pretends it is one. It simply runs out of "
                 "questions it already holds the answers to.",
                 "Three chairs scrape back at slightly different times."),
        handover="Thessaly makes the other two go out of the room first, then "
                 "collects what the castle owes them and gives you every last "
                 "piece of it without discussion.",
        potion="FOCUS"),
}


# ---------------------------------------------------------------------------
# What they do afterwards
# ---------------------------------------------------------------------------
# Same shape as quests.TOWN_UPGRADES, deliberately: {"name", "region",
# "effect", "effects", "stocks", "route", "line"}. The engine already folds
# quests.upgrade_effects() into equipment; boon_effects() hands it a second
# dict of exactly that vocabulary and the fold is the same line of code.
#
# `effect` is prose for the panel. `effects` is arithmetic. `stocks` is what a
# vendor may now put on the shelf. `route` names a ROUTES id for the two who
# open a road. A boon must carry at least one of the three, or it is a
# sentence pretending to be a consequence, and validate() says so.

BOONS = {
    "cut_for_the_lock": {
        "name": "The Key-Cutter's Bench", "region": "hashmap_highlands",
        "captives": ("sennet_crale",),
        "effect": "Highland vaults open cleanly, so what is in them arrives "
                  "intact.",
        "effects": {"loot_luck": 0.08},
        "stocks": {"potions": ["focus_small"]},
        "line": "Sennet cuts for the lock rather than for the collection. One "
                "key, one door, first time, and she charges for the one key.",
    },
    "the_high_herd": {
        "name": "The High Herd", "region": "hashmap_highlands",
        "captives": ("ibb_tallow",),
        "effect": "Cheese, hard bread and a bench at the head of the pass.",
        "effects": {"stamina_regen": 1},
        "stocks": {"potions": ["health_small"]},
        "line": "Ibb has a press and an oven at the head of the pass and a "
                "standing rule that nobody walks past the two of them hungry.",
    },
    "lamps_both_ends": {
        "name": "Both Ends Of The Line", "region": "array_caverns",
        "captives": ("josa_fell",),
        "effect": "The Caverns are lit from both ends, so nothing waits in "
                  "the dark for a runner.",
        "effects": {"mana_regen": 1},
        "line": "The Fells run the lamp line from opposite ends and meet in "
                "the middle, and the Sunken Index has stopped having a dark "
                "half.",
    },
    "dry_crossings": {
        "name": "The Rethatched Crossings", "region": "sliding_window_marsh",
        "captives": ("perrin_oake",),
        "effect": "Every crossing hut in the marsh is dry and stocked with "
                  "reed.",
        "effects": {"stamina_max": 2},
        "line": "Perrin has rethatched every hut on the reedways and left a "
                "bundle by each door, which he describes as self-interest.",
    },
    "the_shelf_restocked": {
        "name": "Ysold's Shelf", "region": "sliding_window_marsh",
        "captives": ("ysold_quen",),
        "effect": "The marsh sells antidote a full band deeper than it could "
                  "before.",
        "effects": {},
        "stocks": {"potions": ["antidote_small", "antidote_medium"]},
        "line": "The shelf on the reedway is full, and the marsh has antidote "
                "in the house before it needs it rather than afterwards.",
    },
    "the_rigged_span": {
        "name": "The Rigged Span", "region": "twin_pointer_pass",
        "captives": ("hessa_dunmar", "torv_bael"),
        "effect": "A walkable span out of the Pass, built from both ends at "
                  "once out of pure stubbornness.",
        "effects": {},
        "route": "cap_rigged_span",
        "line": "Hessa and Torv built it both ways simultaneously to settle "
                "the argument. It came in four days early and settled nothing.",
    },
    "the_morning_rotation": {
        "name": "The Turning Drill", "region": "matrix_citadel",
        "captives": ("ona_kesk",),
        "effect": "The citadel drills rotation at first bell, so there is "
                  "always one more run at a thing you half know.",
        "effects": {"retest_charges": 1},
        "line": "Ten minutes in the muster yard at first bell. Ona runs it, "
                "it is deeply boring, and nobody has been lost in the Keep "
                "since it started.",
    },
    "the_amendment_book": {
        "name": "The Change Book", "region": "matrix_citadel",
        "captives": ("calla_prowd",),
        "effect": "Mistakes in the citadel are written down rather than "
                  "punished, and the first one costs nothing.",
        "effects": {"retry_grace": 1},
        "line": "Every change to the record is dated and signed and never "
                "rubbed out, which Calla won after eleven years of being told "
                "it was a matter of tone.",
    },
    "the_second_line": {
        "name": "The Second Line", "region": "binary_tree_canopy",
        "captives": ("oskar_lind",),
        "effect": "Every fork in the canopy carries a backup line: name the "
                  "danger before you step on it and it holds you once.",
        "effects": {"edge_ward": 1},
        "line": "Twice the rope and half again the time. Oskar says it buys "
                "the afternoon on which somebody is wrong about a branch.",
    },
    "the_marked_line": {
        "name": "The Marked Line", "region": "graph_wastes",
        "captives": ("jessamy_roke",),
        "effect": "Cut marks from the waystation to the Ruins, shorter way on "
                  "the left stone.",
        "effects": {},
        "route": "cap_marked_line",
        "line": "Jessamy has marked the Wastes as far as the Ruins, and the "
                "couriers have stopped flipping a coin at the six-road "
                "junction.",
    },
    "published_rents": {
        "name": "The Posted Rents", "region": "complexity_tower",
        "captives": ("iolanthe_brask",),
        "effect": "The tower posts what every floor truly costs, and a "
                  "published price is a cheaper price.",
        "effects": {"hint_discount": 0.08},
        "line": "Floor by floor, exact, with the word 'about' banned from the "
                "board. Half the tower thinks she has made them poorer.",
    },
    "the_replanted_grove": {
        "name": "The Replanted Grove", "region": "recursive_forest",
        "captives": ("wilmot_tace",),
        "effect": "A grove written down exactly enough to be put back, which "
                  "buys longer between recalls and pays for the distance.",
        "effects": {"interval_stretch": 0.1},
        "line": "Trunk for trunk and spacing for spacing, off a page. Halla "
                "said it could not be done from a page. It is being done from "
                "a page, slowly.",
    },
    "the_forge_rate": {
        "name": "The Working Rate", "region": "debugging_dungeon",
        "captives": ("hedda_ferrin",),
        "effect": "Hedda mends deeper and charges like a smith with a tally "
                  "to clear.",
        "effects": {"armor_repair": 0.15},
        "stocks": {"potions": ["health_medium"], "metal": "faultsteel"},
        "line": "Thirty-one days of mending for the thing that broke it, and "
                "she is working the tally off on everybody else's plate.",
    },
    "the_square_drill": {
        "name": "The Morning Drill", "region": "python_village",
        "captives": ("thessaly_brun",),
        "effect": "The next day's list goes up on the board the night before.",
        "effects": {"srs_preview": True},
        "line": "First bell, in the square, ten minutes, out loud, and the "
                "board up the night before so nobody can say they did not "
                "know what was being asked.",
    },
    "the_lamplit_lesson": {
        "name": "The Second Drill", "region": "python_village",
        "captives": ("ivo_brannt",),
        "effect": "A drill run badly and out loud, where getting it wrong in "
                  "front of people is the point and is worth something.",
        "effects": {"iteration_bonus": 0.05},
        "line": "After the square one, for whoever was too late or too small "
                "or too embarrassed. Ivo runs it off copied slates and a lamp "
                "with a bad wick.",
    },
}


# ---------------------------------------------------------------------------
# What the rescue pays
# ---------------------------------------------------------------------------
# THERE IS NO SECOND REWARD PATH. Everything below is quests.py's own machinery
# with a boss id where a quest id would be:
#
#   tier          TIER_FOR_BAND[story.band_for(region)] — the region's own
#                 difficulty, which forge.py already decides by the rung of the
#                 metal in its ground. No boss carries an authored number.
#   xp/gold/floor quests.REWARD_TIERS, untouched
#   metal/potion  the ground you fought on, at that region's band
#   credit/favour the village that got its people back, which for thirteen of
#                 the fourteen is the same region and for the Interviewer is
#                 deliberately not
#   gear          the one named object a captive hands over, and it must be a
#                 real catalogue piece whose element is that region's affinity
#
# The split is the point of the last two: the ingot and the vial name the place
# you were, and the credit and the mentor's regard name the place the people
# went home to.

_POTION_KINDS = ("HEALTH", "FOCUS", "ANTIDOTE")


def band_for(boss_id: str) -> str:
    """The difficulty band of the region this boss holds its people in."""
    return quests.REGION_BAND[world.BOSS_BY_ID[boss_id]["region"]]


def tier_for(boss_id: str) -> int:
    """Which quests.REWARD_TIERS row a rescue from this boss pays at."""
    return TIER_FOR_BAND[band_for(boss_id)]


def home_of(boss_id: str) -> str:
    """The village these people go back to. Their home, not the cage's region."""
    people = BY_BOSS.get(boss_id, ())
    return people[0].home if people else world.BOSS_BY_ID[boss_id]["region"]


def _extras_for(boss_id: str) -> dict:
    """The material half of the reward, derived rather than authored."""
    holding = HOLDINGS[boss_id]
    region = world.BOSS_BY_ID[boss_id]["region"]
    home = home_of(boss_id)
    tier = tier_for(boss_id)
    band = band_for(boss_id)
    strength = POTION_STRENGTH[band]
    extras: dict = {
        "potion": {"id": f"{holding.potion.lower()}_{strength}",
                   "count": POTION_COUNT[strength]},
        "favor": {"mentor": world.REGION_BY_ID[home]["mentor"],
                  "amount": FAVOR_BY_TIER[tier]},
    }
    metal = quests.metal_for(region)
    if metal and tier in quests.METAL_COUNT:
        extras["metal"] = {"id": metal, "count": quests.METAL_COUNT[tier]}
    if tier in quests.VENDOR_CREDIT:
        extras["vendor_credit"] = {"region": home,
                                   "amount": quests.VENDOR_CREDIT[tier]}
    gifts = [c.gift for c in BY_BOSS.get(boss_id, ()) if c.gift]
    if gifts:
        extras["gear"] = gifts[0]
    return extras


EXTRAS = {boss_id: _extras_for(boss_id) for boss_id in HOLDINGS}


def reward_for(boss_id: str) -> dict:
    """The full reward for freeing everyone this boss holds. Same table, same
    shape and same keys as a quest turn-in, because it is the same function."""
    return quests.reward_for(tier_for(boss_id), EXTRAS[boss_id])


def reward_lines(boss_id: str) -> list:
    """Human lines for the panel, rendered by quests.reward_summary so a rescue
    and a quest read identically."""
    return quests.reward_summary(reward_for(boss_id))


# ---------------------------------------------------------------------------
# The save shape
# ---------------------------------------------------------------------------

STATE_KEY = "captives"


def new_captive_state() -> dict:
    """Add to engine.DEFAULT_STATE under STATE_KEY. _merge forward-fills, so an
    existing save gains the key on load with nobody freed, which is correct."""
    return {
        "freed": [],          # captive ids CARRIED OUT, in the order the cages opened
        "bosses": [],         # boss ids whose people are out
        "boons": [],          # BOONS ids in effect
        "routes": [],         # ROUTES ids now walkable
        "final_release": False,   # the last fight has happened
        # The two lists below belong to the ending and never merge with `freed`.
        # `released` is everyone the collapse of the index let out — the people
        # nobody came for. See `liberate()`, and the long note above it.
        "released": [],           # captive ids the index released, roster order
        "index_collapsed": False, # the practical was passed and the shelves emptied
    }


def _bucket(state: dict) -> dict:
    raw = state.get(STATE_KEY)
    if not raw:
        raw = new_captive_state()
        state[STATE_KEY] = raw
    for key, blank in new_captive_state().items():
        raw.setdefault(key, blank)
    return raw


def available_in(mode: str) -> bool:
    """Adventure Mode only, on the same gate as the quest board. A measured run
    does not hand anybody a villager, a vial and a road."""
    return mode != config.MODE_INTERVIEW


# ---------------------------------------------------------------------------
# Before the fight
# ---------------------------------------------------------------------------

def held_by(boss_id: str) -> list:
    """Who this boss is holding, in authored order."""
    return list(BY_BOSS.get(boss_id, ()))


def chamber(boss_id: str, state: dict | None = None) -> dict:
    """What the player sees on entering the boss chamber. Called BEFORE the
    fight; returns {} for a boss that holds nobody, and says `freed` once they
    are out so the room can be drawn empty on a rematch."""
    holding = HOLDINGS.get(boss_id)
    if holding is None:
        return {}
    raw = (state or {}).get(STATE_KEY) or {}
    out = boss_id in raw.get("bosses", [])
    return {
        "boss": boss_id, "boss_name": world.BOSS_BY_ID[boss_id]["name"],
        "region": world.BOSS_BY_ID[boss_id]["region"],
        "dungeon": holding.dungeon,
        "text": holding.chamber,
        "freed": out,
        "captives": [{"id": c.id, "name": c.name, "trade": c.trade,
                      "bearing": c.bearing, "home": c.home}
                     for c in held_by(boss_id)],
        "count": len(held_by(boss_id)),
    }


# ---------------------------------------------------------------------------
# The rescue
# ---------------------------------------------------------------------------

def free(state: dict, boss_id: str) -> dict:
    """The boss is down. Open the cages and pay.

    Returns {} when this boss holds nobody or has already been beaten, so a
    rematch pays nothing and the engine needs no `if` around the call.

    The returned dict is quests.complete()'s dict with people in it:
      pay     xp / gold / rarity_floor / metal / potion / gear / vendor_credit
      story   favor — the bucket story.apply already owns
      world   boons and routes, already banked here, for a re-render
    """
    holding = HOLDINGS.get(boss_id)
    if holding is None:
        return {}
    raw = _bucket(state)
    if boss_id in raw["bosses"]:
        return {}
    raw["bosses"].append(boss_id)

    people = held_by(boss_id)
    for person in people:
        if person.id not in raw["freed"]:
            raw["freed"].append(person.id)
        if person.boon and person.boon not in raw["boons"]:
            raw["boons"].append(person.boon)
            route = BOONS[person.boon].get("route")
            if route and route not in raw["routes"]:
                raw["routes"].append(route)

    reward = reward_for(boss_id)
    lines = list(holding.release)
    for person in people:
        lines.extend(person.lines)

    return {
        "boss": boss_id, "boss_name": world.BOSS_BY_ID[boss_id]["name"],
        "region": world.BOSS_BY_ID[boss_id]["region"],
        "home": home_of(boss_id),
        "dungeon": holding.dungeon,
        "tier": tier_for(boss_id),
        "lines": lines,
        "handover": holding.handover,
        "captives": [_view(person) for person in people],
        "reward": reward, "reward_lines": quests.reward_summary(reward),
        "pay": {k: reward[k] for k in ("xp", "gold", "rarity_floor",
                                       "consumable", "metal", "potion", "gear",
                                       "vendor_credit") if k in reward},
        "story": {k: reward[k] for k in ("card", "codex", "title", "favor")
                  if k in reward},
        "world": {"boons": [p.boon for p in people if p.boon],
                  "routes": [BOONS[p.boon]["route"] for p in people
                             if p.boon and BOONS[p.boon].get("route")],
                  "changes": [p.change for p in people]},
        "roll_call": {"freed": len(raw["freed"]), "total": len(CAPTIVES)},
    }


def _view(person: Captive) -> dict:
    return {
        "id": person.id, "name": person.name, "trade": person.trade,
        "home": person.home, "home_name": world.REGION_BY_ID[person.home]["name"],
        "held_in": person.held_in, "boss": person.boss,
        "bearing": person.bearing, "opinion": person.opinion,
        "lines": list(person.lines), "afterwards": person.afterwards,
        "change": person.change, "sprite": person.sprite,
        "boon": person.boon, "gift": person.gift,
    }


def final_release(state: dict) -> dict:
    """The last fight, and the only call the finale has to make.

    Frees the three the Interviewer took out of the home village, marks the
    release, and hands back the whole roll call — everyone the player got out,
    in the order the cages opened, plus the honest remainder of people still
    held because a boss is still standing. The ending is a eucatastrophe, not
    a restoration, and a roll call that quietly rounded up to everybody would
    be the module telling a lie on the game's behalf.
    """
    rescue = free(state, "the_interviewer")
    raw = _bucket(state)
    raw["final_release"] = True
    return {
        "rescue": rescue,
        "roll_call": roll_call(state),
        "still_held": [_view(p) for p in still_held(state)],
        "counts": {"freed": len(raw["freed"]), "total": len(CAPTIVES),
                   "still_held": len(CAPTIVES) - len(raw["freed"]),
                   "bosses": len(raw["bosses"]), "villages":
                       len({CAPTIVE_BY_ID[c].home for c in raw["freed"]})},
    }


# ---------------------------------------------------------------------------
# The roll call
# ---------------------------------------------------------------------------

def is_freed(state: dict, captive_id: str) -> bool:
    raw = state.get(STATE_KEY) or {}
    return captive_id in raw.get("freed", [])


def freed(state: dict) -> list:
    """Captive records, in the order they came out."""
    raw = state.get(STATE_KEY) or {}
    return [CAPTIVE_BY_ID[cid] for cid in raw.get("freed", [])
            if cid in CAPTIVE_BY_ID]


def still_held(state: dict) -> list:
    """The honest other half of the list: everybody still in a niche.

    Out is out, by either road — carried out by the player or let out when the
    index stopped answering — so this subtracts both lists. Before the ending
    the second one is empty and this is exactly what it always was.
    """
    raw = state.get(STATE_KEY) or {}
    out = set(raw.get("freed", [])) | set(raw.get("released", []))
    return [c for c in CAPTIVES if c.id not in out]


def roll_call(state: dict) -> list:
    """Everyone out, in order, with what they are doing now. This is the list
    the finale stands behind the player, and the list the player can watch grow
    from the pause screen."""
    return [_view(person) for person in freed(state)]


def roll_call_by_region(state: dict) -> dict:
    """The same list, grouped by the village that got them back."""
    out: dict = {}
    for person in freed(state):
        out.setdefault(person.home, []).append(_view(person))
    return out


def captive_line(captive_id: str, state: dict) -> str:
    """What this person says now. Empty until they are out, which is the whole
    of the state machine: nobody in a cage has a village line."""
    person = CAPTIVE_BY_ID.get(captive_id)
    if person is None or not is_freed(state, captive_id):
        return ""
    return person.afterwards


def village_changes(state: dict, region_id: str = "") -> list:
    """What is physically different in the villages, for the overworld
    renderer. Same shape as quests.world_changes()."""
    out = []
    for person in freed(state):
        if region_id and person.home != region_id:
            continue
        out.append({"captive": person.id, "region": person.home,
                    "text": person.change, "released_here": False})
    # After the index falls, the people nobody came for go home as well, and
    # the street they go home to changes the same way. The flag is kept so a
    # client can tell the two apart; the change itself is the same change.
    for person in released(state):
        if region_id and person.home != region_id:
            continue
        out.append({"captive": person.id, "region": person.home,
                    "text": person.change, "released_here": True})
    return out


# ---------------------------------------------------------------------------
# What the freed are worth
# ---------------------------------------------------------------------------

def boons(state: dict, region_id: str = "") -> list:
    raw = state.get(STATE_KEY) or {}
    rows = [{"id": bid, **BOONS[bid]} for bid in raw.get("boons", [])
            if bid in BOONS]
    return [b for b in rows if not region_id or b["region"] == region_id]


def boon_effects(state: dict) -> dict:
    """The summed, permanent effects of everyone who went home and got back to
    work. items.EFFECT_LABELS vocabulary, so the engine folds this in exactly
    the way it folds quests.upgrade_effects()."""
    totals: dict = {}
    for boon in boons(state):
        for key, value in boon.get("effects", {}).items():
            if isinstance(value, bool):
                totals[key] = bool(totals.get(key, False) or value)
            else:
                totals[key] = totals.get(key, 0) + value
    return totals


def boon_stock(state: dict, region_id: str = "") -> dict:
    """What the freed have put on local shelves. region -> {"potions": [...],
    "metal": id}, the same shape quests.upgrade_stock() returns, so a vendor
    merges the two dicts and asks no further questions."""
    out: dict = {}
    for boon in boons(state, region_id):
        stocks = boon.get("stocks")
        if not stocks:
            continue
        room = out.setdefault(boon["region"], {"potions": [], "metal": ""})
        for pid in stocks.get("potions", ()):
            if pid not in room["potions"]:
                room["potions"].append(pid)
        if stocks.get("metal"):
            room["metal"] = stocks["metal"]
    return out


def open_routes(state: dict) -> list:
    """Roads that stay open because somebody who knew them is walking around
    free. Additive to quests.open_shortcuts(); the ids cannot collide."""
    raw = state.get(STATE_KEY) or {}
    return [{"id": rid, **ROUTES[rid]} for rid in raw.get("routes", [])
            if rid in ROUTES]


# ---------------------------------------------------------------------------
# The index stops answering
# ---------------------------------------------------------------------------
#
# THERE ARE TWO WAYS OUT OF A NICHE AND THEY ARE NOT THE SAME WAY.
#
# The first is `free()` above: a boss goes down, a player walks into the
# chamber, and somebody is carried out by hand. That is the rescue, it is the
# boss reward, and it is the only one the player did.
#
# The second is this section, and it happens exactly once, at the end, and only
# on a PASS of the final practical. An index exists to answer on your behalf.
# For the length of that exam, in the room above, nothing answered on the
# player's behalf and the answer still came back right — so the lookup has
# nothing on the other end of it and the pointing stops. Everyone still filed
# gets up.
#
# THE TWO LISTS NEVER MERGE, and that is the whole of the honesty in this
# module. `freed` is who you went and got. `released` is who walked out because
# the thing holding them failed. The finale stands the first group behind the
# player and stages the second group saying, in their own words, that nobody
# came. A player who rescued nobody still gets an ending; they get it in a room
# full of people who are very clear about how they got out.
#
# NOTHING HERE IS A CONSOLATION PRIZE AND NOTHING HERE IS A PUNISHMENT. The
# release is not smaller for a player who freed twenty-four and it is not
# larger for one who freed none. It is the same event. What differs is who is
# standing where, and that is decided by what the player actually did.

INDEX_COLLAPSE = (
    "Every sphere on every shelf goes out at once, in no particular order, "
    "which is the only thing that has ever happened in this room in no "
    "particular order.",
    "Nothing unlocks, because nothing was ever locked. What stops is the "
    "pointing.",
    "The ones nobody came for get up on their own. They are not grateful, they "
    "are not obliged to be, and most of them say so somewhere on the stair.",
)

# What each of them says on the way up, having been let out rather than fetched.
#
# THE RULE FOR THIS TABLE, and validate() enforces the parts of it a machine can
# reach: the line is about them. It is not thanks, it is not blame, and it is
# never addressed to the player as an accusation. Every one of them says the
# true thing — nobody came — in the voice they already have in this file, and
# then says what they are going to do about the rest of their life, because
# that is what these people are like and it is why they are written this way.
RELEASE_LINES = {
    "sennet_crale":
        "The scratches on the post stop at sixty-three. Nobody came down that "
        "stair, and I am not going to make it sound better than it was to be "
        "polite. The lock let go on its own and I walked out past a door I "
        "could have cut in an afternoon if anyone had thought to ask.",
    "ibb_tallow":
        "I came up on my own feet with nobody holding the other end of the "
        "rope. Twenty-one head have had a year without me. If any of them are "
        "still up there it is because goats are better at this than people, "
        "which I have been saying for six generations of them.",
    "nessa_vey":
        "Nobody came. Number it correctly, because a count that starts where "
        "it is convenient is how this place has always lost people. Start at "
        "nobody. Then write down that I walked out regardless.",
    "josa_fell":
        "Sera got out on day four. Nobody came for the second of us, which is "
        "the thing I have been saying about places that cannot tell two people "
        "apart, and I would much rather have been wrong.",
    "perrin_oake":
        "The shelf let go and I stood up, and that is the whole of it. Nobody "
        "came down that stair, and I spent nine weeks deciding what I would "
        "say to whoever did, and the deciding is the part I have wasted, which "
        "at my age is what stings.",
    "ysold_quen":
        "Nobody came and the season spoiled. Both of those are facts about "
        "waste and neither of them is about anyone in this room. I am going "
        "back to the shelf. It takes eleven months to fill and I started on it "
        "in my head on the way up.",
    "alek_rill":
        "I still have the pole. Nobody came, and the water still went out and "
        "came back twice a day the entire time, which I found steadying. I do "
        "not expect that to be steadying to anyone else.",
    "hessa_dunmar":
        "Nobody rigged a line down here, so I will not be standing about "
        "saying I was fetched. I got out the way the middle of a span gets "
        "found: the thing holding it up stopped, and there the error was.",
    "torv_bael":
        "Nobody came. One span, one person, end to end, and the person was "
        "nobody. I have had six weeks to think of a better way to put that and "
        "I have not found one, and Hessa is going to say that is because I "
        "worked from the wrong end.",
    "ona_kesk":
        "Let the record say it plainly, and in triplicate if it must: nobody "
        "came down for me, the shelf stopped, and I walked. I will write the "
        "other two copies myself, which is the correct way to make this "
        "particular complaint.",
    "wenna_ives":
        "Report it the way it happened. Nobody came, no relief was sent, the "
        "hold failed on its own and I came out under my own feet. That is a "
        "useful report. The other kind is what my father's drill is made of.",
    "calla_prowd":
        "Nobody came for me. Put that down in ink that cannot be gone over in "
        "the morning, because the version where somebody did is exactly the "
        "version this castle would have preferred to wake up to.",
    "oskar_lind":
        "Nobody came up the line. I am not owed it and I am not asking for it. "
        "Tam is still not coming down, and being let out does not touch that "
        "and was never going to.",
    "ferris_ames":
        "Count me where I belong, with the ones nobody came for. It is an end "
        "with one twig on it, the ledger has been miscounting that kind for "
        "nine years, and I notice it is still an end.",
    "jessamy_roke":
        "No one marked a road to this place. I walked out on an unmarked one, "
        "which is the only sort I have ever had, and I started notching the "
        "stair on the way up so the next person down does not have to guess.",
    "abel_sarrow":
        "Nobody came. At seventy that is not a complaint, it is a schedule. "
        "The list is still shut and still on me and I am going to go and add "
        "to it honestly, which means adding the ones nobody reached in time.",
    "iolanthe_brask":
        "Nobody came for me. I am not going to round that up to somebody "
        "nearly did. That is the species of lying that cost a tenant a roof in "
        "my first year and I have refused to do it since.",
    "corin_ashe":
        "Forty-one years on one staircase and nobody has ever once come to "
        "fetch me off it, so this was at least familiar. I walked up out of "
        "here. It is a poor stair. I could cut a better one in a season.",
    "wilmot_tace":
        "Nobody came. Write it exactly like that, because a description that "
        "cannot be read back into the thing it describes is the trade I lost "
        "two years of my hands to.",
    "corr_vane":
        "Nobody came in after me, and I would not have let them. I have spent "
        "twenty years telling apprentices not to go in alone and I am not "
        "going to be the reason one of them decided it was fine.",
    "hedda_ferrin":
        "No one came. The crack was in the thing holding me rather than in the "
        "door, and I would far rather know that than be thanked for it. Every "
        "crack has an address and I have just been given this one.",
    "varna_strand":
        "Nobody came, and I stood here asking out loud, every day, what "
        "happens to this place in the rain. Today I got the answer. I would "
        "still rather somebody had come, and I am going to keep asking.",
    "thessaly_brun":
        "Nobody came down for me. I have been on the other side of that — "
        "waiting in a schoolroom for a child who is not brought — and I know "
        "what it is worth to say it plainly instead of kindly.",
    "yoren_halt":
        "Nobody came. That is a name for what happened and I am going to use "
        "it rather than paint something more comfortable over the top of it, "
        "which is how this village went wrong in the first place.",
    "ivo_brannt":
        "Nobody came. I thought about whether to say it and I am going to, "
        "because everyone down here is going to be asked about this afterwards "
        "and the ones who were carried out should not be the only ones "
        "talking.",
}

# Said next to the release, so a client cannot draw it as a second rescue.
RELEASE_NOTE = ("These people were not rescued. The thing filing them stopped "
                "working and they got up. The roll call keeps the two apart on "
                "purpose and so should anything that draws it.")


def total() -> int:
    """Everybody in the world who is in a niche at the start of the game."""
    return len(CAPTIVES)


def release_line(captive_id: str) -> str:
    """What this person says on the way up, if nobody came for them."""
    return RELEASE_LINES.get(captive_id, "")


def is_released(state: dict, captive_id: str) -> bool:
    raw = state.get(STATE_KEY) or {}
    return captive_id in raw.get("released", [])


def released(state: dict) -> list:
    """Captive records for the people the collapse let out, in roster order."""
    raw = state.get(STATE_KEY) or {}
    out = raw.get("released", [])
    return [CAPTIVE_BY_ID[cid] for cid in out if cid in CAPTIVE_BY_ID]


def everyone_out(state: dict) -> list:
    """Both lists, carried first, for anything that only needs a headcount.
    Nothing that draws the finale should use this: the scene needs the two
    groups apart, because the difference between them is what the player did."""
    return freed(state) + released(state)


def release_roll(state: dict) -> list:
    """Rows for the people the collapse let out, each carrying their own line
    about how they got out. Same row shape as roll_call(), plus two fields the
    renderer needs in order not to stage them as a rescue."""
    rows = []
    for person in released(state):
        rows.append({**_view(person),
                     "released_here": True,
                     "released_line": release_line(person.id),
                     "line": release_line(person.id)})
    return rows


def index_collapsed(state: dict) -> bool:
    raw = state.get(STATE_KEY) or {}
    return bool(raw.get("index_collapsed"))


def liberate(state: dict, *, passed: bool = True, bank_boons: bool = True) -> dict:
    """The shelves empty. The one call the PASS branch of the ending makes.

    `passed` is not decoration and it is not a mood. A failed practical leaves
    every person still in a niche exactly where they were, because the index
    goes on answering as long as there is anything to answer; that is E in the
    brief and it is the reason a rematch has anything at stake. Call this with
    `passed=False` and it does nothing at all and says why.

    Idempotent. A second call returns the same lists with `first_time` False,
    so a client that replays the ending cannot double-bank a boon or read a
    name out twice.
    """
    raw = _bucket(state)
    if not passed:
        return {
            "collapsed": False, "first_time": False, "reason": "not_passed",
            "lines": [], "released": [], "carried": roll_call(state),
            "still_held": [_view(p) for p in still_held(state)],
            "counts": {"carried": len(raw["freed"]), "released": 0,
                       "still_held": len(still_held(state)), "total": total()},
            "world": {"boons": [], "routes": [], "changes": []},
            "note": "The practical was not passed. Nothing in the index moved, "
                    "which is the only reason coming back is worth anything.",
        }

    first_time = not raw.get("index_collapsed")
    banked_boons: list = []
    banked_routes: list = []
    # WHO MOVED ON THIS CALL, which is not the same number as who is out.
    # `released` below is the cumulative roll, so a replayed cutscene reports
    # the same twenty-five and is right to; a caller asking "how many did THIS
    # do" needs the delta, and it is only knowable in here.
    moved: list = []
    if first_time:
        for person in still_held(state):
            raw["released"].append(person.id)
            moved.append(person.id)
            if bank_boons and person.boon and person.boon not in raw["boons"]:
                raw["boons"].append(person.boon)
                banked_boons.append(person.boon)
                route = BOONS[person.boon].get("route")
                if route and route not in raw["routes"]:
                    raw["routes"].append(route)
                    banked_routes.append(route)
        raw["index_collapsed"] = True

    rows = release_roll(state)
    return {
        "collapsed": True,
        "first_time": first_time,
        "reason": "the_index_stopped_answering",
        "lines": list(INDEX_COLLAPSE),
        "released": rows,
        "carried": roll_call(state),
        "still_held": [_view(p) for p in still_held(state)],
        "counts": {
            "carried": len(raw["freed"]),
            "released": len(raw["released"]),
            "released_now": len(moved),
            "still_held": len(still_held(state)),
            "total": total(),
            "villages": len({p.home for p in everyone_out(state)}),
        },
        "world": {
            "boons": banked_boons,
            "routes": banked_routes,
            "changes": [{"captive": p.id, "region": p.home, "text": p.change,
                         "released_here": True} for p in released(state)],
        },
        "note": RELEASE_NOTE,
    }


# ---------------------------------------------------------------------------
# Proofs
# ---------------------------------------------------------------------------

SPRITES_ALLOWED = frozenset({
    "villager", "child", "warden", "clerk", "scribe", "forager", "keeper",
    "quartermaster", "runner", "ferrier", "climber", "forester", "messenger",
    "surveyor", "smith", "scholar", "soldier", "apprentice", "miner",
    "engineer", "porter", "cook", "raker", "lamplighter", "captain", "steward",
})

# Prose fields that are read out to the player, for the checks that apply to
# all of them at once.
_PROSE_FIELDS = ("bearing", "opinion", "afterwards", "change")


def _no_boon_supplies_an_answer() -> list:
    """The one invariant in this file that is worth a named function.

    A rescued villager buys rest, stock, repair, scheduling, a road and a
    second pair of hands. None of them may buy a look at the problem, the
    enemy or the answer, and the refusal is enforced against a named list
    rather than against an allowlist somebody could widen without noticing
    what they were widening.
    """
    problems = []
    for bid, boon in BOONS.items():
        for key in boon.get("effects", {}):
            if key in BOON_EFFECTS_REFUSED:
                problems.append(f"{bid}: effect {key!r} reads the problem, the "
                                f"enemy or the answer, and no freed captive "
                                f"may ever be worth that")
            elif key not in BOON_EFFECTS_ALLOWED:
                problems.append(f"{bid}: effect {key!r} is not on the boon "
                                f"allowlist; add it deliberately or not at all")
            elif key not in items.EFFECT_LABELS:
                problems.append(f"{bid}: effect {key!r} is not an "
                                f"items.EFFECT_LABELS key, so nothing will "
                                f"ever apply it")
    return problems


def validate() -> list:
    """Everything that can be checked about twenty-five people and fourteen
    rooms. Returns a list of problems; empty is the pass condition."""
    problems = []

    # -- the people
    seen_ids: set = set()
    seen_names: set = set()
    for person in CAPTIVES:
        where = person.id
        if person.id in seen_ids:
            problems.append(f"duplicate captive id {person.id!r}")
        seen_ids.add(person.id)
        if person.name in seen_names:
            problems.append(f"{where}: two people called {person.name!r}")
        seen_names.add(person.name)
        if person.boss not in world.BOSS_BY_ID:
            problems.append(f"{where}: unknown boss {person.boss!r}")
            continue
        if person.home not in world.REGION_BY_ID:
            problems.append(f"{where}: unknown home {person.home!r}")
        if person.sprite not in SPRITES_ALLOWED:
            problems.append(f"{where}: sprite {person.sprite!r} is not one the "
                            f"renderer already draws")
        if not person.trade:
            problems.append(f"{where}: a person without a trade is a noun")
        if not 2 <= len(person.lines) <= 4:
            problems.append(f"{where}: two to four lines at the cage, not "
                            f"{len(person.lines)}")
        for field_name in _PROSE_FIELDS:
            if not getattr(person, field_name):
                problems.append(f"{where}: no {field_name} — this is the check "
                                f"that stops a captive becoming a prize")
        if len(person.opinion) < 40:
            problems.append(f"{where}: the opinion is too thin to be one")
        # The moment of rescue has to be about them. A captive whose every line
        # is addressed to the hero is a trophy with dialogue.
        about_you = sum(1 for line in person.lines
                        if "you" in line.lower().split()[:4])
        if about_you == len(person.lines):
            problems.append(f"{where}: every line opens at the player; at "
                            f"least one has to be about their own life")
        if person.gift and person.gift not in items.BY_ID:
            problems.append(f"{where}: gift {person.gift!r} is not a catalogue "
                            f"item")
        elif person.gift:
            region = world.BOSS_BY_ID[person.boss]["region"]
            if person.gift not in quests.gear_for(region):
                problems.append(f"{where}: gift {person.gift!r} does not "
                                f"belong to {region} — a gift names the place "
                                f"it came from")
        if person.boon:
            boon = BOONS.get(person.boon)
            if boon is None:
                problems.append(f"{where}: unknown boon {person.boon!r}")
            else:
                if person.id not in boon.get("captives", ()):
                    problems.append(f"{where}: not listed on boon "
                                    f"{person.boon!r}")
                if boon["region"] != person.home:
                    problems.append(f"{where}: boon {person.boon!r} lands in "
                                    f"{boon['region']}, not at home")

    # -- one to three per boss, every named boss covered, one home per cage
    for boss in world.BOSSES:
        people = BY_BOSS.get(boss["id"], [])
        if not 1 <= len(people) <= 3:
            problems.append(f"{boss['id']}: holds {len(people)} people, "
                            f"want one to three")
        homes = {p.home for p in people}
        if len(homes) > 1:
            problems.append(f"{boss['id']}: holds people from {sorted(homes)}; "
                            f"one cage, one village")
        gifts = [p.gift for p in people if p.gift]
        if len(gifts) > 1:
            problems.append(f"{boss['id']}: {len(gifts)} gear gifts, and a "
                            f"reward carries one piece of gear")
    for boss_id in BY_BOSS:
        if boss_id not in world.BOSS_BY_ID:
            problems.append(f"{boss_id}: captives held by a boss that is not "
                            f"in world.BOSSES")

    # -- the rooms
    for boss_id, holding in HOLDINGS.items():
        if boss_id not in world.BOSS_BY_ID:
            problems.append(f"{boss_id}: holding for an unknown boss")
            continue
        if not BY_BOSS.get(boss_id):
            problems.append(f"{boss_id}: a chamber with nobody in it")
        if holding.dungeon not in dungeonmod.DUNGEON_BY_ID:
            problems.append(f"{boss_id}: unknown dungeon {holding.dungeon!r}")
        else:
            plan = dungeonmod.DUNGEON_BY_ID[holding.dungeon]
            region = world.BOSS_BY_ID[boss_id]["region"]
            if plan.region != region:
                problems.append(f"{boss_id}: held in {holding.dungeon!r}, "
                                f"which is in {plan.region}, not {region}")
        if not holding.chamber:
            problems.append(f"{boss_id}: nothing to see on the way in, which "
                            f"is the whole point of the cage being there")
        if not 1 <= len(holding.release) <= 3:
            problems.append(f"{boss_id}: one to three release lines")
        if not holding.handover:
            problems.append(f"{boss_id}: nobody hands the reward over")
        if holding.potion not in _POTION_KINDS:
            problems.append(f"{boss_id}: potion kind {holding.potion!r}")
    for boss_id in BY_BOSS:
        if boss_id not in HOLDINGS:
            problems.append(f"{boss_id}: people, but no room to keep them in")

    # -- the boons
    for bid, boon in BOONS.items():
        if boon["region"] not in world.REGION_BY_ID:
            problems.append(f"{bid}: unknown region {boon['region']!r}")
        if not boon.get("captives"):
            problems.append(f"{bid}: a boon nobody earned")
        for cid in boon.get("captives", ()):
            person = CAPTIVE_BY_ID.get(cid)
            if person is None:
                problems.append(f"{bid}: unknown captive {cid!r}")
            elif person.boon != bid:
                problems.append(f"{bid}: {cid!r} does not claim this boon")
        if not (boon.get("effects") or boon.get("stocks") or boon.get("route")):
            problems.append(f"{bid}: changes nothing — a boon needs an effect, "
                            f"a shelf or a road")
        if not boon.get("effect") or not boon.get("line"):
            problems.append(f"{bid}: a boon has to be sayable as well as "
                            f"summable")
        band = quests.next_band(boon["region"])
        for pid in boon.get("stocks", {}).get("potions", ()):
            if pid not in potions.BY_ID:
                problems.append(f"{bid}: stocks unknown potion {pid!r}")
            elif not potions.found_at(pid, band):
                problems.append(f"{bid}: {boon['region']} cannot brew {pid!r} "
                                f"even one band deeper than itself")
        metal = boon.get("stocks", {}).get("metal", "")
        if metal and metal not in forge.METAL_BY_ID:
            problems.append(f"{bid}: stocks unknown metal {metal!r}")
        elif metal and metal != quests.metal_for(boon["region"]):
            problems.append(f"{bid}: {metal!r} does not come out of "
                            f"{boon['region']}")
        route = boon.get("route", "")
        if route and route not in ROUTES:
            problems.append(f"{bid}: unknown route {route!r}")
    problems.extend(_no_boon_supplies_an_answer())

    # -- the roads
    for rid, route in ROUTES.items():
        if not rid.startswith("cap_"):
            problems.append(f"{rid}: route ids carry the cap_ prefix so they "
                            f"can never collide with quests.SHORTCUTS")
        if rid in quests.SHORTCUTS:
            problems.append(f"{rid}: already a quest shortcut")
        for end in ("from", "to"):
            if route[end] not in world.REGION_BY_ID:
                problems.append(f"{rid}: {end} names no region")
        if route["from"] == route["to"]:
            problems.append(f"{rid}: a road to where it starts")
        owners = [bid for bid, b in BOONS.items() if b.get("route") == rid]
        if len(owners) != 1:
            problems.append(f"{rid}: opened by {len(owners)} boons, want one")

    # -- the pay
    for boss_id in HOLDINGS:
        tier = tier_for(boss_id)
        if tier not in quests.REWARD_TIERS:
            problems.append(f"{boss_id}: tier {tier} is not in quests' table")
            continue
        grants = set(quests.REWARD_TIERS[tier]["grants"])
        extras = EXTRAS[boss_id]
        for key in extras:
            if key not in quests.REWARD_KEYS:
                problems.append(f"{boss_id}: {key!r} is not a reward key")
            elif key not in grants:
                problems.append(f"{boss_id}: tier {tier} may not pay {key!r}")
        potion = extras["potion"]
        if potion["id"] not in potions.BY_ID:
            problems.append(f"{boss_id}: no such potion {potion['id']!r}")
        else:
            row = potions.BY_ID[potion["id"]]
            if not potions.found_at(potion["id"], band_for(boss_id)):
                problems.append(f"{boss_id}: {band_for(boss_id)} ground cannot "
                                f"brew {potion['id']!r}")
            cap = potions.CARRY_CAP.get(row.strength, 0)
            if potion["count"] > cap:
                problems.append(f"{boss_id}: {potion['count']} of "
                                f"{potion['id']!r} overfills a pouch that "
                                f"holds {cap}")
        metal = extras.get("metal")
        if metal and metal["id"] not in forge.METAL_BY_ID:
            problems.append(f"{boss_id}: no such metal {metal['id']!r}")
        favour = extras["favor"]
        if favour["mentor"] not in world.MENTORS:
            problems.append(f"{boss_id}: unknown mentor {favour['mentor']!r}")
        credit = extras.get("vendor_credit")
        if credit and credit["region"] not in world.REGION_BY_ID:
            problems.append(f"{boss_id}: credit against no region")
        # The reward has to survive the same summariser a quest goes through.
        if not reward_lines(boss_id):
            problems.append(f"{boss_id}: pays nothing a panel could print")

    # -- the telling
    # Rule 7 of the story bible, enforced rather than remembered.
    for person in CAPTIVES:
        for line in (person.bearing, person.opinion, person.afterwards,
                     person.change, *person.lines):
            if "!" in line:
                problems.append(f"{person.id}: exclamation mark")
                break
    for boss_id, holding in HOLDINGS.items():
        for line in (holding.chamber, holding.handover, *holding.release):
            if "!" in line:
                problems.append(f"{boss_id}: exclamation mark")
                break

    # -- coverage
    if len(CAPTIVES) != len(seen_ids):
        problems.append("the roster does not agree with itself")
    villages = {p.home for p in CAPTIVES}
    if len(villages) < 10:
        problems.append(f"only {len(villages)} villages lost anybody, which "
                        f"makes this a set piece rather than a world")
    with_boons = [p for p in CAPTIVES if p.boon]
    if len(with_boons) < 8:
        problems.append(f"only {len(with_boons)} of the freed are worth "
                        f"anything afterwards, and the brief asked for "
                        f"several")
    if len(with_boons) == len(CAPTIVES):
        problems.append("everybody pays out, which makes them rewards again; "
                        "some people just go home")

    # -- the release lines
    #
    # Everybody has one, because the ending has to be playable for a player who
    # rescued nobody, and in that playthrough all twenty-five of these are the
    # only thing anyone says. The three rules they are held to are the three
    # that stop this becoming either a guilt trip or a consolation prize.
    for person in CAPTIVES:
        line = RELEASE_LINES.get(person.id, "")
        if not line:
            problems.append(f"{person.id}: no release line — a player who "
                            f"freed nobody would stand in silence")
            continue
        if len(line) < 80:
            problems.append(f"{person.id}: the release line is too thin to be "
                            f"somebody's own words")
        low = line.lower()
        if not ("nobody came" in low or "no one came" in low
                or "nobody" in low or "no one" in low):
            problems.append(f"{person.id}: the release line does not say the "
                            f"true thing, which is that nobody came")
        for barb in ("you did not", "you never", "where were you",
                     "your fault", "thank you"):
            if barb in low:
                problems.append(f"{person.id}: the release line {barb!r}s at "
                                f"the player; it is about them, not about you")
    for captive_id in RELEASE_LINES:
        if captive_id not in CAPTIVE_BY_ID:
            problems.append(f"release line for unknown captive {captive_id!r}")
    return problems


def counts() -> dict:
    """The numbers, for the self-check and for whoever writes the patch note."""
    freed_xp = sum(reward_for(b)["xp"] for b in HOLDINGS)
    freed_gold = sum(reward_for(b)["gold"] for b in HOLDINGS)
    return {
        "captives": len(CAPTIVES),
        "bosses": len(HOLDINGS),
        "bosses_in_world": len(world.BOSSES),
        "villages": len({p.home for p in CAPTIVES}),
        "by_boss": {b: len(BY_BOSS.get(b, ())) for b in HOLDINGS},
        "by_home": {r: len(v) for r, v in BY_HOME.items()},
        "boons": len(BOONS),
        "captives_with_boons": sum(1 for p in CAPTIVES if p.boon),
        "routes": len(ROUTES),
        "gifts": sum(1 for p in CAPTIVES if p.gift),
        "lines": sum(len(p.lines) for p in CAPTIVES),
        "release_lines": len(RELEASE_LINES),
        "release_words": sum(len(t.split()) for t in RELEASE_LINES.values()),
        "words": sum(len(" ".join([p.bearing, p.opinion, p.afterwards,
                                   p.change, *p.lines]).split())
                     for p in CAPTIVES),
        "xp_total": freed_xp,
        "gold_total": freed_gold,
        "tiers": {b: tier_for(b) for b in HOLDINGS},
    }


def self_check() -> dict:
    """Raises on the first thing that is wrong, and otherwise hands back the
    numbers. Tests call `assert captives.validate() == []`; this is the version
    a human runs from a shell."""
    problems = validate()
    if problems:
        raise AssertionError("captives.py: " + "; ".join(problems[:8]))
    return counts()


WIRING = """
How the engine picks this up. Six touch points, none of them invasive, and
five of them are one line.

1. STATE
   engine.DEFAULT_STATE["captives"] = captives.new_captive_state()
   _merge forward-fills, so an existing save gains the key on load with nobody
   freed, which is the correct starting position rather than a migration.

2. THE CAGE, BEFORE THE FIGHT
   In engine.start_boss(), after the boss dict is built:
       room = captives.chamber(boss_id, self.state)
   and put room["text"] into the chamber description and room["captives"] into
   whatever draws the room. It returns {} for a boss holding nobody and carries
   freed=True on a rematch so the cages can be drawn empty. This is the whole
   reason the module has any weight: a cage the player walked past is a
   different fight from a cage they hear about afterwards.

3. THE RESCUE, AFTER THE FIGHT
   In engine._resolve_boss(), inside `if solved:`, directly after
   `self.state["cleared_bosses"].append(enc.boss_id)`:

       rescue = captives.free(self.state, enc.boss_id)

   and put it in the dict that function already returns, under "rescue".
   It returns {} on a rematch, so there is no `if` to write and no way to pay
   twice. Then settle it exactly like a quest turn-in:

       pay    xp / gold / rarity_floor / metal / potion / gear / vendor_credit
              — identical shapes to quests.complete()["pay"], so the handler
              that settles a quest settles this unchanged
       story  favor — the bucket story.apply already owns
       world  boons, routes and changes; all three are already banked in this
              module's own state and the engine only has to re-render

   rescue["lines"] is the scene: the narrator's release lines, then every
   captive's own lines in authored order. rescue["handover"] is the line the
   reward is handed over under and belongs immediately above the reward panel.

4. THE WORLD AFTERWARDS
   captives.village_changes(state, region)  what is physically different
   captives.boons(state, region)            who is doing what, with prose
   captives.boon_effects(state)             fold in beside quests.upgrade_effects
   captives.boon_stock(state, region)       merge with quests.upgrade_stock
   captives.open_routes(state)              draw beside quests.open_shortcuts
   captives.captive_line(captive_id, state) what this person says now, or ""

   boon_effects() returns items.EFFECT_LABELS keys and nothing else, so it goes
   through the same fold as equipment and town upgrades. One of them is a bool
   (srs_preview); the summer already handles that.

5. THE ROLL CALL
   captives.roll_call(state)            everyone out, in the order they came out
   captives.roll_call_by_region(state)  the same list, grouped by village
   captives.still_held(state)           the honest remainder
   Put the first on the pause screen under the quest log. It is a list that
   grows, with faces and trades on it, and watching it grow is most of the
   point.

6. THE FINALE, AND THE TWO WAYS OUT OF A NICHE
   The last boss fight makes exactly one call, and it is the ordinary one:

       release = captives.final_release(self.state)

   It frees the three the Interviewer took out of the home village, marks the
   release, and hands back release["roll_call"] — everyone carried out, in
   order — plus release["still_held"], the people whose boss is still standing.

   THE ENDING MAKES A SECOND CALL, AND ONLY ON A PASS. gauntlet/ending.py owns
   the seam and calls it; nothing else should:

       out = captives.liberate(self.state, passed=(verdict == "READY"))

   On a pass the shelves empty: everyone still in a niche is appended to
   state["captives"]["released"], their boons and roads are banked, and every
   one of them carries their own RELEASE_LINES entry saying that nobody came
   for them. On a fail it does nothing and says why, because a failed practical
   leaves the index answering and that is what makes a rematch worth sitting.

   THE TWO LISTS NEVER MERGE. freed() is who the player went and got;
   released() is who the collapse let out. everyone_out() exists for headcounts
   and must not be used to draw the scene, because the difference between the
   two lists is the only record of what the player actually did. §5 of the
   story bible is explicit that the ending is a eucatastrophe and not a
   restoration, and a roll call that quietly rounded up would be this module
   telling a lie on the game's behalf.

   New helpers, all pure: total(), released(state), release_roll(state),
   release_line(id), is_released(state, id), everyone_out(state),
   index_collapsed(state).

7. INTERVIEW MODE
   captives.available_in(mode) is the same gate the quest board uses. Nothing
   in here happens in a measured run.

8. TESTS
   assert captives.validate() == []
   captives.self_check() raises with the first eight problems named, and
   otherwise returns counts(): 25 people, 14 rooms, 11 villages, 15 boons,
   2 roads.
"""


CONTRACT = """
What captives.py needs from files it does not own, stated precisely so nobody
has to guess.

NOTHING NEW. Every reward key this module emits is a key quests.py already
emits and engine.py already has to settle, with identical shapes:

  pay["xp"] / pay["gold"] / pay["rarity_floor"]   quests.REWARD_TIERS values
  pay["metal"]          {"id": forge.METAL_BY_ID key, "count": int}
  pay["potion"]         {"id": potions.BY_ID key, "count": int}
  pay["gear"]           items.BY_ID key, element == the region's affinity
  pay["vendor_credit"]  {"region": world.REGION_BY_ID key, "amount": int}
  story["favor"]        {"mentor": world.MENTORS key, "amount": int}

If the quest turn-in path is already written, this needs no new handler at
all — pass rescue["pay"] and rescue["story"] to the same two functions.

Two things are this module's own ledger and need nothing from the engine
beyond a re-render:

  world["boons"]   BOONS ids, banked in state["captives"]["boons"]
  world["routes"]  ROUTES ids, banked in state["captives"]["routes"]

TWO CALL SITES ARE LOAD-BEARING and are named exactly:

  engine.start_boss(boss_id)      -> captives.chamber(boss_id, self.state)
  engine._resolve_boss(...)       -> captives.free(self.state, enc.boss_id)
                                     inside `if solved:`, after the
                                     cleared_bosses append

  Both are idempotent. free() returns {} for a rematch and for a boss holding
  nobody, so neither call needs a guard.

THE STATE KEY is "captives", shape in new_captive_state(): freed (ordered
captive ids), bosses (ordered boss ids), boons, routes, final_release.

WHERE THE NUMBERS COME FROM, so nobody re-tunes them here by mistake:

  tier      TIER_FOR_BAND[story.band_for(region)]. story.band_for reads the
            rung of the region's metal in forge.py, which means the difficulty
            of a region is decided in exactly one place in this codebase and
            this file is not it. Fourteen rescues pay 4,640 XP and 3,500 gold
            in total, at tiers 3/4/5.
  potion    kind is authored per region (HEALTH / FOCUS / ANTIDOTE, which is
            the only per-region number in the file and is a flavour choice);
            strength and count come from the band and are checked against
            potions.found_at() and potions.CARRY_CAP.
  metal     quests.metal_for(region) and quests.METAL_COUNT[tier].
  credit    quests.VENDOR_CREDIT[tier], banked against the HOME region, which
            for the Interviewer is python_village and not the castle.

WHAT COULD NOT BE RESOLVED, said plainly rather than guessed at:

  progression.py  owns ROUTES, and several of them are already gated on a boss
                  (Needs.boss("matrix_golem") opens the Rotating Stair). The
                  two roads here — cap_rigged_span and cap_marked_line — are
                  therefore declared in this module in quests.SHORTCUTS' shape,
                  banked in this module's state, and exposed through
                  open_routes(). If the pass that owns progression.py would
                  rather have them as first-class Routes, the clean move is a
                  Route with Needs.boss("twin_behemoth") and
                  Needs.boss("graph_necromancer") and a one-line deletion here;
                  the prose and the ids are written to survive that move. The
                  ids carry a cap_ prefix so the two registries cannot collide
                  in the meantime, and validate() proves it.

  healers       the hidden-healer pass and this one both put something worth
                finding deep in a dungeon. They do not overlap: a healer is a
                place, a captive is a person, and nothing in this module reads
                or writes upkeep.py's state.

  missable      Everyone in this file is freed on the boss kill, and the
  rescues       Standing Portal wants all fourteen keys, so a player who
                reaches the ending has normally carried all twenty-five out
                and `released` is empty. That is the correct outcome for a
                player who did everything, and the release path still fires for
                the saves where the two lists genuinely disagree: a save made
                before this module existed, whose `cleared_bosses` is full and
                whose `captives` block is not; a save that lost the block; and
                anything future that is missable on purpose.

                IF MISSABLE RESCUES ARE WANTED — and the empty gallery in
                finale.py is written for exactly that player — the change is
                one call site and not this file: move `captives.free()` off the
                boss kill in engine._resolve_boss and onto the act of opening
                the cages in the chamber, so that walking out without doing it
                is a thing a player can do. Nothing in this module, in
                finale.py or in ending.py needs editing for that; all three
                already count the two lists separately and stage them apart.

  the finale    owns the cutscene. This module owns the list it stands behind
                the player, and final_release() is the only call it needs. The
                honest half of that list — still_held() — is handed over with
                it deliberately, because §5 of the bible says the world is not
                restored and a roll call that quietly rounds up would be this
                module telling a lie on the game's behalf.
"""
