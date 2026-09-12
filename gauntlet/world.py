"""The Algorithm Realms: regions, bosses, mentors, companions, equipment, quests.

Geography is pedagogy here. Each region physically embodies its pattern, and the
unlock graph is the learning graph.
"""
from __future__ import annotations

# ADDING A REGION COSTS ONE LINE IN ANOTHER FILE.
#
# `biome` is not decoration. elements.py builds the whole elemental map out of
# it — `elements.BIOME_AFFINITY` turns a biome into one of six elements, and
# every region's weather, its overworld hazard, the element its monsters fight
# with and which potions its loot table favours all fall out of that one word.
# A region whose biome is not on that map is simply neutral, which reads as a
# region nobody finished rather than as a region nobody gave weather to.
#
# So: a new region either reuses an existing biome, or it needs an entry in
# elements.BIOME_AFFINITY. `elements.self_check()` fails by name if it does not
# get one, which is the loud version of this comment.
REGIONS = [
    {"id": "python_village", "name": "Python Village", "numeral": "",
     "skill": "PYTHON", "biome": "village", "palette": "dawn",
     "blurb": "A half-ruined village where the ancient language is still spoken.",
     "physical": "Buildings rebuild themselves as your fluency returns.",
     "unlocks": [], "mentor": "byte", "music": "town"},
    {"id": "fields_of_syntax", "name": "Fields of Syntax", "numeral": "I",
     "skill": "PYTHON", "biome": "grass", "palette": "spring",
     "blurb": "Open fields where malformed statements grow like weeds.",
     "physical": "Sentences of code lie scattered across the grass, half-formed.",
     "unlocks": ["python_village"], "mentor": "byte", "music": "overworld"},
    {"id": "hashmap_highlands", "name": "Hashmap Highlands", "numeral": "II",
     "skill": "HASH_MAP", "biome": "highland", "palette": "amber",
     "blurb": "A plateau of keyed vaults, each opening to exactly one rune.",
     "physical": "Every key you carry glows near its own vault, and no other.",
     "unlocks": ["fields_of_syntax"], "mentor": "archivist", "music": "overworld"},
    {"id": "stringwood_labyrinth", "name": "Stringwood Labyrinth", "numeral": "III",
     "skill": "STRING", "biome": "forest", "palette": "verdant",
     "blurb": "A maze of letters where paths spell words that rearrange themselves.",
     "physical": "Trees reorder their letters; anagram groves lead to the same clearing.",
     "unlocks": ["hashmap_highlands"], "mentor": "scribe", "music": "dungeon"},
    {"id": "array_caverns", "name": "Array Caverns", "numeral": "IV",
     "skill": "ARRAY", "biome": "cave", "palette": "stone",
     "blurb": "Indexed halls where every alcove is numbered from zero.",
     "physical": "Alcoves are numbered from zero; the last is always one short of the count.",
     "unlocks": ["hashmap_highlands"], "mentor": "archivist", "music": "dungeon"},
    {"id": "sliding_window_marsh", "name": "Sliding Window Marsh", "numeral": "V",
     "skill": "SLIDING_WINDOW", "biome": "swamp", "palette": "moss",
     "blurb": "Wetlands crossed by a magical frame that expands and contracts.",
     "physical": "A glowing frame slides across the reeds, widening right, "
                 "shrinking left when the ward breaks.",
     "unlocks": ["hashmap_highlands", "array_caverns"], "mentor": "window_mage",
     "music": "overworld"},
    {"id": "twin_pointer_pass", "name": "Twin Pointer Pass", "numeral": "VI",
     "skill": "TWO_POINTER", "biome": "mountain", "palette": "slate",
     "blurb": "A pass where two travellers approach from opposite ends.",
     "physical": "Two lanterns start at either end of the bridge and converge.",
     "unlocks": ["array_caverns"], "mentor": "ranger", "music": "overworld"},
    {"id": "stack_queue_mines", "name": "Stack & Queue Mines", "numeral": "VII",
     "skill": "STACK", "biome": "mine", "palette": "ember",
     "blurb": "Mines where carts stack last-in-first-out and lifts run first-in-first-out.",
     "physical": "Ore carts must be unloaded from the top; the lift takes the oldest first.",
     "unlocks": ["array_caverns"], "mentor": "archivist", "music": "dungeon"},
    {"id": "matrix_citadel", "name": "Matrix Citadel", "numeral": "VIII",
     "skill": "MATRIX", "biome": "citadel", "palette": "royal",
     "blurb": "A fortress of perfect rows and columns that can be rotated whole.",
     "physical": "The whole floor plan turns ninety degrees when the Golem stirs.",
     "unlocks": ["array_caverns"], "mentor": "cartographer", "music": "dungeon"},
    {"id": "recursive_forest", "name": "Recursive Forest", "numeral": "IX",
     "skill": "RECURSION", "biome": "deepforest", "palette": "dusk",
     "blurb": "Paths that lead into smaller copies of themselves before unwinding.",
     "physical": "Each clearing contains a smaller copy of the forest. You return "
                 "carrying what the inner copy found.",
     "unlocks": ["stringwood_labyrinth"], "mentor": "druid", "music": "dungeon"},
    {"id": "binary_tree_canopy", "name": "Binary Tree Canopy", "numeral": "X",
     "skill": "TREE", "biome": "canopy", "palette": "verdant",
     "blurb": "A canopy where every branch splits exactly twice.",
     "physical": "The path forks left and right and never rejoins.",
     "unlocks": ["recursive_forest"], "mentor": "druid", "music": "overworld"},
    {"id": "graph_wastes", "name": "Graph Wastes", "numeral": "XI",
     "skill": "GRAPH", "biome": "wastes", "palette": "ash",
     "blurb": "A broken land where every ruin connects to several others.",
     "physical": "Roads form a lattice; some routes are shorter, some merely exist.",
     "unlocks": ["binary_tree_canopy", "stack_queue_mines"], "mentor": "cartographer",
     "music": "overworld"},
    {"id": "dp_ruins", "name": "Dynamic Programming Ruins", "numeral": "XII",
     "skill": "DP", "biome": "ruins", "palette": "gold",
     "blurb": "Ruins where every tile you have already solved stays lit.",
     "physical": "Solved tiles glow and can be walked again for free.",
     "unlocks": ["recursive_forest"], "mentor": "oracle", "music": "dungeon"},
    {"id": "debugging_dungeon", "name": "Debugging Dungeon", "numeral": "XIII",
     "skill": "DEBUGGING", "biome": "dungeon", "palette": "iron",
     "blurb": "The Armorer's forge, and the cells where broken programs are kept.",
     "physical": "Cracked armour hangs on every wall, each crack a defect in some program.",
     "unlocks": ["fields_of_syntax"], "mentor": "armorer", "music": "dungeon"},
    {"id": "complexity_tower", "name": "Complexity Tower", "numeral": "XIV",
     "skill": "BIG_O", "biome": "tower", "palette": "azure",
     "blurb": "A tower whose floors each cost more to climb than the last.",
     "physical": "Each floor holds twice the enemies of the one below; the top floor "
                 "is unreachable by brute force.",
     "unlocks": ["hashmap_highlands"], "mentor": "oracle", "music": "tower"},
    {"id": "coding_coliseum", "name": "The Coding Coliseum", "numeral": "XV",
     "skill": "SPEED", "biome": "arena", "palette": "sun",
     "blurb": "Where the Chronomancer turns knowledge into speed.",
     "physical": "A sand floor, a clock, and no hints.",
     "unlocks": ["sliding_window_marsh", "twin_pointer_pass"], "mentor": "chronomancer",
     "music": "battle"},
    {"id": "null_kings_castle", "name": "The Null King's Castle", "numeral": "XVI",
     "skill": "RECALL", "biome": "castle", "palette": "void",
     "blurb": "No signposts. No region labels. Nothing tells you what is being tested.",
     "physical": "Rooms give no indication of which pattern they demand.",
     "unlocks": ["graph_wastes", "dp_ruins", "complexity_tower", "coding_coliseum"],
     "mentor": "interviewer", "music": "final"},
]

REGION_BY_ID = {r["id"]: r for r in REGIONS}

BOSSES = [
    {"id": "hash_titan", "name": "The Hash Titan", "region": "hashmap_highlands",
     "skill": "HASH_MAP", "problem_id": "ah-group-anagrams",
     "taunt": "Compare every scroll against every other. I will wait. I have time.",
     "sprite": "titan", "colour": "#e8a33d"},
    {"id": "three_sum_hydra", "name": "The Three-Sum Hydra", "region": "array_caverns",
     "skill": "TWO_POINTER", "problem_id": "ah-three-sum",
     "taunt": "For every duplicate you fail to skip, I grow another head.",
     "sprite": "hydra", "colour": "#4fb783"},
    {"id": "window_wraith", "name": "The Window Wraith", "region": "sliding_window_marsh",
     "skill": "SLIDING_WINDOW", "problem_id": "sw-longest-no-repeat",
     "taunt": "Restart your scan. Please. I feed on restarts.",
     "sprite": "wraith", "colour": "#7f6ad6"},
    {"id": "twin_behemoth", "name": "The Twin Pointer Behemoth",
     "region": "twin_pointer_pass", "skill": "TWO_POINTER",
     "problem_id": "tp-container-water",
     "taunt": "Move the taller wall. Go on. Lose the width for nothing.",
     "sprite": "behemoth", "colour": "#c4553f"},
    {"id": "matrix_golem", "name": "The Matrix Golem", "region": "matrix_citadel",
     "skill": "MATRIX", "problem_id": "mx-rotate",
     "taunt": "Allocate a second matrix. I will simply take it from you.",
     "sprite": "golem", "colour": "#8a8f9c"},
    {"id": "tree_dragon", "name": "The Tree Dragon", "region": "binary_tree_canopy",
     "skill": "TREE", "problem_id": "tr-validate-bst",
     "taunt": "Compare me only to my children. I dare you.",
     "sprite": "dragon", "colour": "#3f9c5a"},
    {"id": "path_sum_ent", "name": "The Path-Sum Ent", "region": "binary_tree_canopy",
     "skill": "TREE", "problem_id": "tr-path-sum",
     "taunt": "A node with one child is not a leaf, little architect.",
     "sprite": "ent", "colour": "#6b8f3f"},
    {"id": "graph_necromancer", "name": "The Graph Necromancer", "region": "graph_wastes",
     "skill": "BFS", "problem_id": "gr-shortest-hops",
     "taunt": "Depth-first, was it? Enjoy the scenic route.",
     "sprite": "necromancer", "colour": "#6a4f8f"},
    {"id": "rolling_titan", "name": "The Rolling Titan", "region": "sliding_window_marsh",
     "skill": "QUEUE", "problem_id": "sw-max-sliding-window",
     "taunt": "Call max() again. I have all day. You have three seconds.",
     "sprite": "titan", "colour": "#3f7f9c"},
    {"id": "editor_automaton", "name": "The Editor Automaton", "region": "matrix_citadel",
     "skill": "DESIGN", "problem_id": "ds-text-editor",
     "taunt": "Undo that. No — the *other* undo. The one you did not implement.",
     "sprite": "automaton", "colour": "#b0763f"},
    {"id": "complexity_wyrm", "name": "The Complexity Wyrm", "region": "complexity_tower",
     "skill": "BIG_O", "problem_id": "sw-min-window",
     "taunt": "Correct is not the same as fast. I am the difference.",
     "sprite": "wyrm", "colour": "#3f6f9c"},
    {"id": "serialization_lich", "name": "The Serialization Lich",
     "region": "recursive_forest", "skill": "TREE", "problem_id": "tr-serialize",
     "taunt": "Write the tree down. Now read it back. Exactly.",
     "sprite": "lich", "colour": "#8f3f6f"},
    {"id": "bug_demon", "name": "The Bug Demon", "region": "debugging_dungeon",
     "skill": "DEBUGGING", "problem_id": "db-bfs-visited",
     "taunt": "It works on your machine.",
     "sprite": "demon", "colour": "#c43f4f"},
    {"id": "the_interviewer", "name": "The Interviewer", "region": "null_kings_castle",
     "skill": "RECALL", "problem_id": "ds-lru-cache", "final": True,
     "taunt": "Walk me through your approach before you write anything.",
     "sprite": "interviewer", "colour": "#d8d8e0"},
]

BOSS_BY_ID = {b["id"]: b for b in BOSSES}

# ---------------------------------------------------------------------------
# The last trial
# ---------------------------------------------------------------------------
#
# It is deliberately NOT in BOSSES. finalexam.BOSS_LADDER is built from that
# list's ORDER — rung N is the Nth entry — so appending to it would renumber
# every crutch in the game, and nothing about the practical is fought, ranked,
# rematched or dropped loot by anyway. The Interviewer above is still the
# fourteenth boss and still takes the last crutch.
#
# What this is, is the geography: a place, below the castle, with something in
# it. gauntlet.finalexam owns the character standing there — its voice, its law
# and the three lines it has about you — because the exam owns the room.
FINAL_TRIAL = {
    "id": "the_last_interpreter",
    "name": "THE LAST INTERPRETER",
    "epithet": "of the Standing Prompt",
    "region": "null_kings_castle",
    "where": "Underneath the castle, in the room the castle was built on top of "
             "in order to stop being able to see it.",
    "sprite": "interpreter", "colour": "#3f7f5a", "accent": "#e8c37d",
    "blurb": "A python at the scale where the room is a consequence of the "
             "animal rather than the other way round. It is also, and without "
             "any apparent contradiction, a wizard. It speaks one language and "
             "will not be drawn into a second.",
}

# Boss phases: recognition, explanation, implementation, edge cases, complexity,
# then a disguised variant. HP falls as phases clear.
BOSS_PHASES = [
    {"key": "recognize", "label": "Name the family", "kind": "PATTERN_ENCOUNTER"},
    {"key": "explain", "label": "State your approach", "kind": "COMMUNICATION"},
    {"key": "implement", "label": "Cast the spell", "kind": "CODE_BATTLE"},
    {"key": "edges", "label": "Survive the hidden trials", "kind": "EDGE_CASE_TRAP"},
    {"key": "complexity", "label": "Name its cost", "kind": "COMPLEXITY_DUEL"},
    {"key": "variant", "label": "The disguised rematch", "kind": "MEMORY_AMBUSH"},
]

MENTORS = {
    "byte": {"name": "BYTE", "role": "Python syntax", "sprite": "automaton_small",
             "greeting": "You know what you want to say. Let us make the saying automatic."},
    "archivist": {"name": "THE ARCHIVIST", "role": "data structures", "sprite": "scholar",
                  "greeting": "Choose the structure before you write the loop. "
                              "The loop will then write itself."},
    "ranger": {"name": "THE RANGER", "role": "two pointers", "sprite": "ranger",
               "greeting": "Two hands. One from each end. Neither ever turns back."},
    "window_mage": {"name": "THE WINDOW MAGE", "role": "sliding window", "sprite": "mage",
                    "greeting": "Expand right. When the ward breaks, shrink left. "
                                "Never start over."},
    "druid": {"name": "THE RECURSIVE DRUID", "role": "recursion and trees",
              "sprite": "druid",
              "greeting": "Trust the smaller call to be correct. Then say what you do "
                          "with its answer."},
    "cartographer": {"name": "THE CARTOGRAPHER", "role": "graphs", "sprite": "cartographer",
                     "greeting": "Rings of light for the shortest road. A single "
                                 "committed path for every road."},
    "armorer": {"name": "THE ARMORER", "role": "debugging", "sprite": "armorer",
                "greeting": "Bring me your broken plate. We fix it the only way "
                            "anything gets fixed — by reading it."},
    "oracle": {"name": "THE ORACLE", "role": "complexity", "sprite": "oracle",
               "greeting": "Count the work per element. Multiply by the elements. "
                           "That is the whole art."},
    "testsmith": {"name": "THE TESTSMITH", "role": "testing", "sprite": "smith",
                  "greeting": "A suite every wrong answer passes is not a suite."},
    "chronomancer": {"name": "THE CHRONOMANCER", "role": "speed", "sprite": "chronomancer",
                     "greeting": "You know this one. Now know it faster than you can "
                                 "doubt yourself."},
    "scribe": {"name": "THE SCRIBE", "role": "explanation", "sprite": "scribe",
               "greeting": "Say the approach aloud before the first keystroke. "
                           "If you cannot, you do not have one yet."},
    "interviewer": {"name": "THE INTERVIEWER", "role": "pressure and ambiguity",
                    "sprite": "interviewer",
                    "greeting": "There is no trick here. Just you, the problem, "
                                "and the clock."},
}

COMPANIONS = [
    {"id": "byte", "name": "BYTE", "skill": "PYTHON", "sprite": "automaton_small",
     "unlock": "Complete the Trial of the Architect",
     "line": "Your syntax is faster than it was yesterday. I measured."},
    {"id": "hash", "name": "HASH", "skill": "HASH_MAP", "sprite": "spirit",
     "unlock": "Defeat the Hash Titan",
     "line": "Membership question. Set. Every time. Do not overthink it."},
    {"id": "lyra", "name": "LYRA", "skill": "SLIDING_WINDOW", "sprite": "mage",
     "unlock": "Defeat the Window Wraith",
     "line": "Delete the key at zero, or len() will lie to you forever."},
    {"id": "talon", "name": "TALON", "skill": "TWO_POINTER", "sprite": "ranger",
     "unlock": "Defeat the Twin Pointer Behemoth",
     "line": "The shorter wall is the one that is holding you back. Move it."},
    {"id": "root", "name": "ROOT", "skill": "RECURSION", "sprite": "druid",
     "unlock": "Clear the Recursive Forest",
     "line": "Base case first. Then trust the smaller call."},
    {"id": "queue", "name": "QUEUE", "skill": "BFS", "sprite": "messenger",
     "unlock": "Defeat the Graph Necromancer",
     "line": "Mark it seen when you enqueue it. Not when you pop it."},
    {"id": "trace", "name": "TRACE", "skill": "DEBUGGING", "sprite": "familiar",
     "unlock": "Repair ten broken programs",
     "line": "Read the failing input. Then trace it by hand. That is the whole method."},
    {"id": "oracle", "name": "ORACLE", "skill": "BIG_O", "sprite": "oracle",
     "unlock": "Clear the fifth floor of Complexity Tower",
     "line": "Sequential work adds. Nested work multiplies. That is the difference."},
]

WEAPONS = [
    {"id": "hashblade", "name": "Hashblade", "skill": "HASH_MAP", "icon": "sword",
     "tiers": ["Solve 3 easy hash problems", "Solve 5 medium hash problems",
               "Clear a hash retest after 3 days",
               "Defeat the Hash Titan unaided, under target time"]},
    {"id": "twin_sabers", "name": "Twin Sabers", "skill": "TWO_POINTER", "icon": "sabers",
     "tiers": ["Solve 3 two-pointer problems", "Solve 5 medium two-pointer problems",
               "Clear a two-pointer retest", "Defeat the Behemoth unaided"]},
    {"id": "window_staff", "name": "Window Staff", "skill": "SLIDING_WINDOW", "icon": "staff",
     "tiers": ["Solve 3 window problems", "Solve 5 medium window problems",
               "Clear a disguised window retest", "Defeat the Window Wraith unaided"]},
    {"id": "recursion_spear", "name": "Recursion Spear", "skill": "RECURSION", "icon": "spear",
     "tiers": ["Solve 3 recursive problems", "Solve 5 medium recursive problems",
               "Clear a recursion retest", "Defeat the Serialization Lich"]},
    {"id": "queue_lance", "name": "Queue Lance", "skill": "BFS", "icon": "lance",
     "tiers": ["Solve 3 BFS problems", "Solve 5 medium BFS problems",
               "Clear a BFS retest", "Defeat the Graph Necromancer"]},
    {"id": "depthblade", "name": "Depthblade", "skill": "DFS", "icon": "dagger",
     "tiers": ["Solve 3 DFS problems", "Solve 5 medium DFS problems",
               "Clear a DFS retest", "Trace every lateral path unaided"]},
    {"id": "tree_axe", "name": "Tree Axe", "skill": "TREE", "icon": "axe",
     "tiers": ["Solve 3 tree problems", "Solve 5 medium tree problems",
               "Clear a tree retest", "Defeat the Tree Dragon unaided"]},
    {"id": "heap_hammer", "name": "Heap Hammer", "skill": "HEAP", "icon": "hammer",
     "tiers": ["Solve 3 heap problems", "Solve 5 medium heap problems",
               "Clear a heap retest", "Defeat the Rolling Titan"]},
    {"id": "matrix_bow", "name": "Matrix Bow", "skill": "MATRIX", "icon": "bow",
     "tiers": ["Solve 3 matrix problems", "Solve 5 medium matrix problems",
               "Clear a matrix retest", "Defeat the Matrix Golem unaided"]},
    {"id": "dynamic_relic", "name": "Dynamic Relic", "skill": "DP", "icon": "relic",
     "tiers": ["Solve 3 DP problems", "Solve 5 medium DP problems",
               "Clear a DP retest", "Clear the Ruins without hints"]},
]

ARMOR = [
    {"id": "helmet", "name": "Helm", "repairs": "syntax defects", "icon": "helm"},
    {"id": "chestplate", "name": "Chestplate", "repairs": "logic defects", "icon": "chest"},
    {"id": "gauntlets", "name": "Gauntlets", "repairs": "dictionary and state defects",
     "icon": "gauntlets"},
    {"id": "boots", "name": "Boots", "repairs": "off-by-one defects", "icon": "boots"},
    {"id": "shield", "name": "Shield", "repairs": "performance defects", "icon": "shield"},
    {"id": "legendary", "name": "Legendary Plate",
     "repairs": "multi-function programs", "icon": "plate"},
]

TITLES = [
    (0, "Python Apprentice"), (3, "Script Squire"), (7, "Hash Adept"),
    (12, "Algorithm Ranger"), (18, "Data Mage"), (25, "Complexity Knight"),
    (33, "Code Sorcerer"), (42, "Gauntlet Champion"), (55, "Legend of the Source"),
]

ACHIEVEMENTS = [
    {"id": "first_blood", "name": "First Blood",
     "desc": "Solve your first encounter unaided."},
    {"id": "hash_slinger", "name": "Hash Slinger",
     "desc": "Solve five hash-map problems unaided."},
    {"id": "window_cleaner", "name": "Window Cleaner",
     "desc": "Solve three sliding-window problems under the target time."},
    {"id": "tree_climber", "name": "Tree Climber",
     "desc": "Complete a DFS, a BFS and a serialization problem."},
    {"id": "no_oracle", "name": "No Oracle",
     "desc": "Solve a Medium without using the Oracle spell."},
    {"id": "linear", "name": "O(n)",
     "desc": "Replace an O(n^2) solution with an O(n) one."},
    {"id": "first_try", "name": "First Try",
     "desc": "Pass every hidden trial on your first submission."},
    {"id": "bug_hunter", "name": "Bug Hunter", "desc": "Repair ten broken programs."},
    {"id": "armorsmith", "name": "Armorsmith",
     "desc": "Restore every armour piece to full through debugging."},
    {"id": "comeback", "name": "Comeback",
     "desc": "Master a pattern you previously failed."},
    {"id": "memory_master", "name": "Memory Master",
     "desc": "Pass a seven-day disguised retest."},
    {"id": "speed_demon", "name": "Speed Demon",
     "desc": "Beat your own best time on a familiar pattern."},
    {"id": "explainer", "name": "Explainer",
     "desc": "Score full marks on an approach explanation."},
    {"id": "gauntlet_ready", "name": "Gauntlet Ready",
     "desc": "Meet every interview-readiness gate."},
    {"id": "legend", "name": "Legend",
     "desc": "Complete the Null King's Castle."},
]

SHRINE_QUESTIONS = [
    ("What Python structure gives O(1) unique membership?", ["set", "a set"], "SET"),
    ("What pattern handles contiguous ranges under a constraint?",
     ["sliding window", "window"], "SLIDING_WINDOW"),
    ("What structure naturally implements undo?", ["stack", "a stack"], "STACK"),
    ("What structure does BFS use for its frontier?",
     ["queue", "deque", "a queue"], "BFS"),
    ("Average complexity of a dict lookup?", ["o(1)", "1", "constant"], "HASH_MAP"),
    ("What is the purpose of a recursion base case?",
     ["stop", "terminate", "end the recursion", "prevent infinite recursion"],
     "RECURSION"),
    ("What syntax safely increments a dictionary counter?",
     ["get", "counts.get(k, 0) + 1", "defaultdict", "counter"], "PYTHON"),
    ("Which collection removes from the front in O(1)?",
     ["deque", "collections.deque"], "QUEUE"),
    ("What does sorting cost, in the general case?",
     ["o(n log n)", "n log n"], "BIG_O"),
    ("Which structure gives you the smallest element repeatedly, cheaply?",
     ["heap", "heapq", "priority queue"], "HEAP"),
    ("What must you delete when a sliding-window count reaches zero?",
     ["the key", "key", "the dict key"], "SLIDING_WINDOW"),
    ("In BFS, when should a node be marked visited?",
     ["when enqueued", "on push", "when you add it", "enqueue"], "BFS"),
    ("What does `all([])` return?", ["true"], "PYTHON"),
    ("Which is faster for membership: a list or a set?", ["set", "a set"], "SET"),
    ("What turns an O(n^2) pair search into O(n)?",
     ["hash map", "dict", "a dictionary", "hashmap"], "HASH_MAP"),
]

QUEST_TEMPLATES = {
    "MAIN": "Defeat {boss} in {region}.",
    "SIDE": "Help {mentor} with three {skill} encounters.",
    "DAILY": "Clear {count} encounters in {region}.",
    "BOUNTY": "Beat your previous time on {problem}.",
    "RETEST": "Return to {region}: a {skill} pattern is due for retest.",
    "MENTOR": "Complete three {skill} encounters without a syntax error.",
    "SECRET": "Discover that a brute-force O(n^2) approach can become O(n).",
}


def title_for(level: int) -> str:
    earned = "Python Apprentice"
    for threshold, name in TITLES:
        if level >= threshold:
            earned = name
    return earned


def level_for(xp: int) -> int:
    """Gentle curve: early levels arrive fast so the first session feels alive."""
    level, need, total = 1, 120, 0
    while xp >= total + need:
        total += need
        level += 1
        need = int(need * 1.18)
    return level


def xp_to_next(xp: int) -> tuple:
    level, need, total = 1, 120, 0
    while xp >= total + need:
        total += need
        level += 1
        need = int(need * 1.18)
    return xp - total, need


# The castle is the exam hall, not another dungeon. It opens only when the
# evidence says the player is close to ready.
CASTLE_BOSS_REQUIREMENT = 8
CASTLE_MASTERY_REQUIREMENT = 60
CASTLE_GATE_REQUIREMENT = 10        # of the thirteen readiness gates


def unlocked_regions(skills: dict, cleared_bosses: set,
                     readiness: dict | None = None) -> list:
    """A region opens when its prerequisites have real evidence behind them."""
    open_ids = {"python_village", "fields_of_syntax", "debugging_dungeon"}
    for region in REGIONS:
        if region["id"] in open_ids:
            continue
        deps = region["unlocks"]
        if not deps:
            open_ids.add(region["id"])
            continue
        castle = region["id"] == "null_kings_castle"
        floor = CASTLE_MASTERY_REQUIREMENT if castle else 25
        ready = True
        for dep in deps:
            dep_region = REGION_BY_ID.get(dep)
            if not dep_region:
                continue
            state = skills.get(dep_region["skill"])
            if state is None or state.mastery < floor:
                ready = False
                break
        if castle:
            ready = ready and len(cleared_bosses) >= CASTLE_BOSS_REQUIREMENT
            if ready and readiness is not None:
                ready = readiness.get("gates_passed", 0) >= CASTLE_GATE_REQUIREMENT
        if ready:
            open_ids.add(region["id"])
    return [r["id"] for r in REGIONS if r["id"] in open_ids]


def castle_requirements(skills: dict, cleared_bosses: set,
                        readiness: dict | None = None) -> dict:
    """What the player still owes before the Null King will see them."""
    castle = REGION_BY_ID["null_kings_castle"]
    deps = []
    for dep in castle["unlocks"]:
        region = REGION_BY_ID.get(dep)
        if not region:
            continue
        state = skills.get(region["skill"])
        mastery = state.mastery if state else 0
        deps.append({"region": region["name"], "skill": region["skill"],
                     "mastery": round(mastery),
                     "required": CASTLE_MASTERY_REQUIREMENT,
                     "met": mastery >= CASTLE_MASTERY_REQUIREMENT})
    gates_passed = (readiness or {}).get("gates_passed", 0)
    gates_total = (readiness or {}).get("gates_total", 13)
    return {
        "regions": deps,
        "bosses": {"cleared": len(cleared_bosses),
                   "required": CASTLE_BOSS_REQUIREMENT,
                   "met": len(cleared_bosses) >= CASTLE_BOSS_REQUIREMENT},
        "gates": {"passed": gates_passed, "required": CASTLE_GATE_REQUIREMENT,
                  "total": gates_total,
                  "met": gates_passed >= CASTLE_GATE_REQUIREMENT},
        "open": all(d["met"] for d in deps)
        and len(cleared_bosses) >= CASTLE_BOSS_REQUIREMENT
        and gates_passed >= CASTLE_GATE_REQUIREMENT,
    }


def town_tier(mastery: float) -> int:
    """Villages visibly rebuild as fluency returns. 0 = ruined, 3 = thriving."""
    if mastery >= 75:
        return 3
    if mastery >= 45:
        return 2
    if mastery >= 20:
        return 1
    return 0
