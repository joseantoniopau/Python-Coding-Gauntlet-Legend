"""The ramp's declarations: which span of each problem carries the idea.

This file is CONTENT. It authors no problems — there are no new ids here, no new
canonical solutions, no new tests and no new lineages. Every entry names a
problem that already exists and already passed validation, and says which span
of *its own canonical solution* is the one worth making the player write.

    "fs-write-longest": [
        ("len(word) > len(best)", "this word beats the longest one so far"),
        ("best = word",           "so remember it instead"),
    ],

From that one declaration `gauntlet/scaffold.py` generates every rung: rung 3
strikes the first two or three spans, rung 2 strikes span #1, rung 1 strikes
span #1 and offers four tokens to choose between. That is why 313 declarations
buy what 313 new problems could not: the corpus stays 1,013 problems, the
hold-out stays the same 122 ids, and no lineage changes membership, because
nothing was created. A further 185 come free, read back out of the blanked
starters that already shipped — see `scaffold.derive_spans`, and note that the
read is itself the check those 214 starters never had.

WHICH SPAN — docs/14-the-ramp.md §4, in priority order:

    1. the accumulator's update — the right-hand side of `+=`
    2. the comparison in an `if` or `while` test
    3. the index expression inside `[...]`
    4. the argument to `.append()` / `.add()` / `.popleft()`
    5. the returned expression, when it is not a bare name

NEVER a parameter name the body already uses, never a builtin's name, never bare
punctuation or a keyword, and never a literal the problem statement already
hands over. All four are in the shipped corpus and all four are lookups rather
than ideas; they are defensible at GUIDED, where naming the part IS the lesson,
and indefensible above it. `validate._verify_scaffold` enforces that split.

THE GLOSS IS THE TEACHING. A blank with no sentence beside it is a guessing
game. The standard to meet is `# 1. the number to hand back` — say what the
missing expression has to DO, in the player's words, without naming the
construct that does it.

An AST pass proposed the spans below and agreed with the shipped human choices
50% of the time (§4). Every one of them was therefore read and confirmed by
hand, and the proposal was overruled wherever it had reached for the line that
was merely easiest to see.
"""
from __future__ import annotations

# ---------------------------------------------------------------------------
# TUTORIAL — the whole job.
# ---------------------------------------------------------------------------
#
# Measured before this pass: 7 of 202 TUTORIAL problems carried any scaffold at
# all, and 195 were a blank screen. GUIDED hands a player complete code with one
# expression struck out; TUTORIAL handed them nothing and EASY handed them
# nothing, so the ramp's middle rung was a rung the engine reserved space for
# and the content never filled. 93.5% to 3.5% in one step is the cliff the
# player felt, and this section is the 59% of the work that removes it.

TUTORIAL = {
    "ah-contains-duplicate": [
        ("len(set(nums)) != len(nums)",
         "true exactly when some value turned up more than once"),
    ],
    "dll-backward": [
        ("node.prev = tail", "the link that makes this list readable backwards"),
        ("tail = tail.prev", "step to the node in front of this one"),
    ],
    "fs-write-banner": [
        ('"*" * len(text)', "a row of stars exactly as long as the text"),
        ('edge + " " + text + " " + edge',
         "the finished banner: the stars, the text, the stars"),
    ],
    "fs-write-initials": [
        ("first[0]", "the first letter of the first name"),
        ("start + end", "the two letters, side by side"),
    ],
    "fs-write-longest": [
        ("len(word) > len(best)", "this word beats the longest one so far"),
        ("best = word", "so remember it instead"),
    ],
    "fs-write-positive-total": [
        ("running + number", "the running total with this number folded in"),
        ("number > 0", "only the numbers above zero count"),
    ],
    "gen-closure-accumulator": [
        ("nonlocal total",
         "say that `total` is the one in the enclosing function, not a new local"),
        ("total += value", "fold this value into the total that outlives the call"),
    ],
    "gen-closure-factory": [
        ("value * factor", "scaled by the factor this maker was built with"),
        ("[multiply(value) for value in values]",
         "every value put through that one multiplier"),
    ],
    "gen-ctx-class": [
        ('self.log.append("open:" + self.name)', "what entering the block records"),
        ('self.log.append("close:" + self.name)',
         "what leaving it records, however it is left"),
    ],
    "gen-ctx-contextmanager": [
        ("yield log", "hand the log to the `with` block and pause here"),
        ('log.append("end")',
         "runs on the way out whether or not the block raised"),
    ],
    "gen-deco-count": [
        ("wrapper.calls += 1", "one more call than before"),
        ("fn(*args, **kwargs)",
         "the original function, called with exactly what it was handed"),
    ],
    "gen-deco-prefixed": [
        ('label + ": " + fn(*args, **kwargs)',
         "the label, then whatever the wrapped function answered"),
        ("@wraps(fn)",
         "without this line the wrapper's own name replaces the real one"),
    ],
    "gen-deco-wraps": [
        ("wrapper.last = result", "remember what the last call gave back"),
        ("@wraps(fn)",
         "keeps the wrapped function's name and docstring instead of the wrapper's"),
    ],
    "gen-iter-manual": [
        ("total += next(cursor)", "take the next item by hand and fold it in"),
        ("cursor = iter(items)",
         "the one cursor that remembers how far through the items we are"),
    ],
    "gen-iter-shared": [
        ("list(islice(cursor, 2))", "the first two items, taken off the cursor"),
        ("list(cursor)", "whatever that same cursor has left afterwards"),
    ],
    "gen-lazy-first": [
        ('next((word for word in words if len(word) >= least), "")',
         "the first word long enough, or the empty string if there is none"),
    ],
    "gen-yield-pairs": [
        ("yield [index, text]", "hand back one numbered line and pause here"),
        ("line.strip()", "the line with the space around it gone"),
    ],
    "gen-yieldfrom-chain": [
        ("yield from first", "every item of the first sequence, without writing a loop"),
        ('yield "done"', "one last value of this generator's own"),
    ],
    "lang-anyall-tutorial": [
        ("all(len(p) >= n for p in passwords)",
         "true only if EVERY password is long enough"),
    ],
    "lang-args-tutorial": [
        ("sep.join(str(part) for part in parts)",
         "the parts, each turned into text, joined by the separator"),
    ],
    "lang-default-tutorial": [
        ("[str(value) for value in items] * times",
         "the items as text, the whole list repeated that many times"),
        ("sep.join(parts)", "one string, with the separator between the parts"),
    ],
    "lang-dictcomp-tutorial": [
        ("{value: key for key, value in mapping.items()}",
         "the same pairs with key and value swapped over"),
    ],
    "lang-enumerate-tutorial": [
        ("found.append(i)", "the POSITION this value sits at, not the value"),
        ("value == target", "this is one of the values being looked for"),
    ],
    "lang-fstring-tutorial": [
        ('f"{done}/{total} ({percent:.0f}%)"',
         "the line to show: done, total, and the percentage to no decimal places"),
        ("100 * done / total", "how far along this is, as a percentage"),
    ],
    "lang-identity-tutorial": [
        ("row.get(key) is None",
         "this row holds nothing at all under that key"),
    ],
    "lang-listcomp-tutorial": [
        ("[word for word in words if len(word) > n]",
         "the words longer than n, in the order they arrived"),
    ],
    "lang-maxkey-tutorial": [
        ("min(items, key=lambda item: item[1])",
         "the whole pair whose price is the lowest"),
        ("best[0]", "the name out of that pair"),
    ],
    "lang-nested-tutorial": [
        ('record.get("address", {}).get("city", "unknown")',
         "the city, and no crash when there is no address to look inside"),
    ],
    "lang-range-tutorial": [
        ("sum(range(lo, hi + 1))",
         "every whole number from lo up to and including hi, added up"),
    ],
    "lang-set-tutorial": [
        ("set(a) & set(b)", "the values that appear in both"),
    ],
    "lang-slice-tutorial": [
        ("items[1:-1]", "everything except the first and the last"),
    ],
    "lang-sortkey-tutorial": [
        ("sorted(words, key=len)", "the same words, shortest first"),
    ],
    "lang-ternary-tutorial": [
        ("n < lo", "below the bottom of the range"),
        ("n > hi", "above the top of it"),
    ],
    "lang-truthy-tutorial": [
        ("value", "this item counts as something — ask truthiness, not `!= 0`", 4),
        ("kept.append(value)", "keep it"),
    ],
    "lang-tuple-tutorial": [
        ("zip(*pairs)", "the pairs turned on their side: all the firsts, then all the seconds"),
        ("[list(firsts), list(seconds)]",
         "both of those as lists, because zip hands back tuples"),
    ],
    "lang-unpack-tutorial": [
        ("first, *rest = items",
         "the first item into one name and everything after it into another"),
        ("[first, rest]", "the two of them, in that order"),
    ],
    "lang-zip-tutorial": [
        ("sum(x * y for x, y in zip(a, b))",
         "each pair multiplied together, and all of those added up"),
    ],
    "ll-build": [
        ("ListNode(value, head)", "a new node sitting in front of the chain so far"),
        ("reversed(values)", "walk the values backwards, so the chain comes out forwards"),
    ],
    "ll-has-cycle": [
        ("fast = fast.next.next", "two steps for the slow pointer's one"),
        ("slow is fast", "the two of them are on the SAME node, not on equal ones"),
    ],
    "ll-intersect-equal": [
        ("a.val == b.val", "both lists are showing the same value here"),
        ("a is not None and b is not None", "there is still a node on both sides"),
    ],
    "ll-merge-two": [
        ("a.val <= b.val", "a's node is the smaller one, so it goes next"),
        ("a if a is not None else b", "whichever list still has nodes left in it"),
    ],
    "ll-middle": [
        ("fast = fast.next.next", "two steps for the slow pointer's one"),
        ("slow.val if slow is not None else None",
         "the middle value, or nothing if the list was empty"),
    ],
    "ll-number-to-digits": [
        ("number % 10", "the last digit of what is left"),
        ("number //= 10", "drop that digit off the end"),
    ],
    "ll-palindrome": [
        ("values[left] != values[right]", "the two ends disagree"),
        ("left < right", "the two ends have not met in the middle yet"),
    ],
    "ll-remove-value": [
        ("node.next = node.next.next", "unlink the next node by pointing straight past it"),
        ("node.next.val == target", "the NEXT node is one of the ones to remove"),
    ],
    "ll-reverse": [
        ("node.next = prev", "turn this node's arrow around"),
        ("following = node.next", "save the rest of the list before that link is cut"),
    ],
    "ll-sum": [
        ("node.val", "the number this node is carrying"),
        ("node = node.next", "move along to the next one"),
    ],
    "lru-evictions": [
        ("order.pop(0)", "the least recently used key — the one at the front"),
        ("len(order) > capacity", "the cache has overflowed"),
    ],
    "mx-transpose": [
        ("[list(row) for row in zip(*matrix)] if matrix else []",
         "rows and columns swapped over, with an empty grid left alone"),
    ],
    "ob-comprehension-filter": [
        ("[value for value in nums if value > 0]",
         "the numbers above zero, in the order they came"),
    ],
    "ob-comprehension-upper": [
        ("[word.upper() for word in words]", "every word, shouted"),
    ],
    "ob-count-vowels": [
        ("ch in \"aeiou\"", "this character is one of the five vowels"),
        ("count + 1", "one more than the count so far"),
    ],
    "ob-default-argument": [
        ("text.upper() + mark", "the text shouted, with the mark on the end"),
    ],
    "ob-dict-default": [
        ("prices.get(item, 0)", "the price, or zero when the item is not in the book"),
    ],
    "ob-every-third": [
        ("range(0, len(items), 3)", "0, then 3, then 6, up to the end"),
        ("items[i]", "the item sitting at that position"),
    ],
    "ob-first-three": [
        ("text[:3]", "the first three characters, and no error on a shorter string"),
    ],
    "ob-grade": [
        ("score >= 90", "high enough for an A"),
        ("score >= 80", "high enough for a B"),
        ("score >= 70", "high enough for a C"),
    ],
    "ob-group-by-letter": [
        ("groups[word[0]].append(word)", "file this word under its own first letter"),
        ("{key: groups[key] for key in sorted(groups)}",
         "a plain dict of those groups, letters in order"),
    ],
    "ob-has-value": [
        ("value in known", "this value is one of the ones seen"),
    ],
    "ob-last-letter": [
        ("text[-1]", "the final character, counted from the end"),
    ],
    "ob-last-two": [
        ("items[-2:]", "the last two, and a shorter list left whole"),
    ],
    "ob-number-to-text": [
        ("\"count: \" + str(count)", "the label and the number as one piece of text"),
    ],
    "ob-pair-up": [
        ("[x, y]", "one item from each list, side by side"),
        ("zip(a, b)", "the two lists walked in step"),
    ],
    "ob-running-max": [
        ("value > best", "this one beats the biggest so far"),
        ("not nums", "there is nothing here to be the largest of"),
    ],
    "ob-serve-queue": [
        ("line.popleft()", "the person at the FRONT of the queue"),
        ("[out, list(line)]", "who got served, and who is still waiting"),
    ],
    "ob-set-build": [
        ("seen.add(value)", "record that this value turned up"),
        ("sorted(seen)", "the distinct values, in order"),
    ],
    "ob-type-name": [
        ("type(value).__name__", "the name of this value's type, as text"),
    ],
    "oopl-bare-except-tutorial": [
        # `raise SystemExit(3)` reads like the idea but is not: no test looks at
        # the exit code, so any number fills it. The input that SELECTS that
        # branch is what the tests actually turn on.
        ('kind == "exit"',
         "the input that raises the one failure `except Exception` will not catch"),
        ("raise SystemExit(3)",
         "and that failure, which walks straight past the handler below"),
    ],
    "oopl-classattr-tutorial": [
        ("a.tag = new_value",
         "give `a` a tag of its own, without touching the class's"),
        ("[a.tag, b.tag, Sigil.tag]", "what each of the three reads afterwards"),
    ],
    "oopl-classmethod-tutorial": [
        ("cls(int(year), int(month), int(day))",
         "build one of whatever class this was called on"),
        ("text.split(\"-\")", "the three parts of an ISO date"),
    ],
    "oopl-eq-default-tutorial": [
        ("[first == second, first == first, first != second]",
         "what each comparison answers when nobody wrote `__eq__`"),
    ],
    "oopl-exc-hierarchy-tutorial": [
        ("type(exc).__name__", "the exact class that was raised, not the one caught"),
        ("raise LockedError(\"locked\")",
         "the locked-vault failure, from the family the handler below catches"),
    ],
    "oopl-except-order-tutorial": [
        ("{}[\"missing\"]", "something that fails with a KeyError"),
        ("[][0]", "something that fails with an IndexError"),
    ],
    "oopl-getitem-tutorial": [
        ("self.items[index]", "the item at that position, out of the list inside"),
        ("Bag(items)[index]",
         "square brackets on the Bag itself, which `__getitem__` is what makes legal"),
    ],
    "oopl-gil-lock-tutorial": [
        ("state[\"value\"] += 1", "one more, while the lock is held"),
        ("threading.Lock()", "the thing only one thread may hold at a time"),
    ],
    "oopl-identity-tutorial": [
        ("[a == b, a is b, a is alias]",
         "equal contents, separate objects, and one object under two names"),
    ],
    "oopl-isinstance-tutorial": [
        ("[isinstance(obj, Animal), type(obj) is Animal]",
         "one test that accepts a subclass and one that refuses it"),
    ],
    "oopl-iter-generator-tutorial": [
        ("yield number * 2", "hand back one doubled number and pause here"),
        ("list(Doubler(nums))", "everything `__iter__` yields, collected up"),
    ],
    "oopl-lt-tuple-tutorial": [
        ("(self.seconds, self.name) < (other.seconds, other.name)",
         "time decides; the name is only there to break a tie"),
        ("[run.name for run in sorted(runs)]",
         "the names in the order `__lt__` put them"),
    ],
    "oopl-method-tutorial": [
        ("self.total += amount", "fold this amount into the tally the object carries"),
        ("[tally.add(step) for step in steps]", "the running total after each step"),
    ],
    "oopl-mro-resolve-tutorial": [
        ("chosen().greet()", "make one and ask it — Python decides whose `greet` that is"),
    ],
    "oopl-property-setter-tutorial": [
        ("self.celsius = (value - 32) * 5 / 9",
         "write the one number this object really keeps, converted back"),
        ("self.celsius * 9 / 5 + 32", "that same reading in Fahrenheit"),
    ],
    "oopl-repr-vs-str-tutorial": [
        ('f"Temp({self.celsius})"',
         "the developer's view: text you could paste back into Python"),
        ('f"{self.celsius} degrees"', "the human's view"),
    ],
    "oopl-slots-reject-tutorial": [
        ('["refused", name]', "what to report when there is no slot to put it in"),
        ("setattr(pixel, name, 9)", "try to write to an attribute chosen at run time"),
    ],
    "oopl-super-override-tutorial": [
        ('"[t] " + super().line(text)',
         "this class's prefix in front of whatever the parent produced"),
    ],
    "pt-class-biggest": [
        ("key=lambda item: (-item[1], item[0])",
         "biggest total first, and the account name only to break a tie"),
        ("ranked[:max(n, 0)]", "the first n of those, and never a negative slice"),
    ],
    "pt-config-layers": [
        ("{**merged, **layer}",
         "everything merged so far, with this layer laid on top of it"),
    ],
    "pt-csv-to-dicts": [
        ("dict(zip(header, values))",
         "one record: each header name against its own value"),
        ("len(values) != len(header)",
         "this row does not carry one value per column"),
    ],
    "pt-file-comments": [
        ('not text or text.startswith("#")',
         "there is nothing on this line worth keeping"),
        ("kept.append(text)", "keep the trimmed line, not the raw one"),
    ],
    "pt-json-index-by": [
        ("index[record[key]] = record", "file this record under its own key"),
        ("not isinstance(record, dict) or key not in record",
         "this entry cannot be filed at all"),
    ],
    "pt-log-level-counts": [
        ("fields[2]", "the level, which is the third field on the line"),
        ("len(fields) >= 3", "this line has enough fields to carry a level"),
    ],
    "pt-regex-parse-kv": [
        (r'dict(re.findall(r"(\w+)=(\S+)", text))',
         "every name=value pair in the text, collected into a dict"),
    ],
    "pt-text-tokenise": [
        ("word.strip(string.punctuation).lower()",
         "the word with punctuation trimmed off both ends, lower-cased"),
        ("cleaned", "there is something left after the trimming", 6),
    ],
    "pt-time-elapsed": [
        ("datetime.strptime(end, fmt) - datetime.strptime(start, fmt)",
         "how much later the end is than the start"),
        ("int(delta.total_seconds())", "that gap, in whole seconds"),
    ],
    "pv-all-unique": [
        ("len(set(items)) == len(items)", "true when nothing repeated"),
    ],
    "pv-any-all": [
        ("[any(v > 0 for v in nums), all(v > 0 for v in nums)]",
         "whether at least one is positive, then whether every one is"),
    ],
    "pv-clamp": [
        ("max(lo, min(hi, value))",
         "the value pulled back inside the range at both ends"),
    ],
    "pv-count-chars": [
        # Not `dict(Counter(s))`: a Counter compares equal to a dict, so the
        # wrapper can be dropped and every test still passes. The objective
        # test caught that, and the span moved to the part that carries the idea.
        ("Counter(s)", "how many times each character turns up"),
    ],
    "pv-deque-rotate": [
        ("d.rotate(k)", "shift everything round by k, wrapping at the ends"),
    ],
    "pv-dict-comprehension": [
        ("{i: i * i for i in range(n)}", "each number below n against its own square"),
    ],
    "pv-digits-only": [
        ('"".join(c for c in text if c.isdigit())',
         "only the digits, joined with nothing between them"),
    ],
    "pv-enumerate": [
        ("[[i, value] for i, value in enumerate(items, start)]",
         "each item paired with its number, counting from start"),
    ],
    "pv-every-other": [
        ("items[::2]", "positions 0, 2, 4 and so on, taken in one slice"),
    ],
    "pv-filter-map": [
        ("[value * 2 for value in nums if value > 0]", "the positive ones, doubled"),
    ],
    "pv-flatten": [
        ("[value for row in nested for value in row]",
         "every value of every row, in one flat list"),
    ],
    "pv-fstring": [
        ('f"{name} scored {score:.2f}"',
         "the name, then the score to exactly two decimal places"),
    ],
    "pv-invert-dict": [
        ("{value: key for key, value in d.items()}",
         "the same pairs, the other way round"),
    ],
    "pv-join": [
        ("sep.join(str(value) for value in items)",
         "each item as text, with the separator between them"),
    ],
    "pv-lambda-sort": [
        ("sorted(nums, key=lambda value: -value)", "biggest first"),
    ],
    "pv-merge-dicts": [
        ("{**a, **b}", "both of them, with b winning any key they share"),
    ],
    "pv-min-max": [
        ("[] if not nums else [min(nums), max(nums)]",
         "the smallest and the largest — and nothing at all for an empty list"),
    ],
    "pv-reverse-slice": [
        ("items[::-1]", "the same items, back to front"),
    ],
    "pv-running-totals": [
        ("total += value", "the total so far with this value folded in"),
        ("out.append(total)", "record the total at this point, not the value"),
    ],
    "pv-safe-divide": [
        ("a / b", "the division that might not be legal"),
    ],
    "pv-safe-increment": [
        ("counts.get(key, 0) + 1",
         "one more than it was, treating a key that is missing as zero"),
        ("counts = dict(counts)", "a copy, so the caller's dict is left alone"),
    ],
    "pv-set-ops": [
        ("[sorted(sa | sb), sorted(sa & sb), sorted(sa - sb)]",
         "in either, in both, in the first only — each of them sorted"),
    ],
    "pv-sort-by-second": [
        ("key=lambda p: p[1]", "order by the second item of each pair"),
    ],
    "pv-squares": [
        ("[value * value for value in nums]", "each number multiplied by itself"),
    ],
    "pv-strip-punctuation": [
        ('"".join(c for c in text if c.isalnum() or c.isspace())',
         "letters, digits and spaces only, joined back into one string"),
    ],
    "pv-sum-evens": [
        ("sum(value for value in nums if value % 2 == 0)", "the even ones, added up"),
    ],
    "pv-sum-nested": [
        ("sum(sum(row) for row in nested)",
         "every row totalled, and those totals totalled"),
    ],
    "pv-tuple-swap": [
        ("[[b, a] for a, b in pairs]", "each pair with its two halves exchanged"),
    ],
    "pv-unique-sorted": [
        ("sorted(set(items))", "the distinct values, in order"),
    ],
    "pv-word-count": [
        ("Counter(text.split())", "how many times each word turns up"),
    ],
    "pv-zip-pairs": [
        ("[list(pair) for pair in zip(a, b)]",
         "the two lists walked in step, each pairing a list of its own"),
    ],
    "py-accumulate-max": [
        ("list(accumulate(nums, max))", "the biggest seen so far, at every position"),
    ],
    "py-bisect-insort": [
        ("bisect.insort(out, target)",
         "drop the value into the one place that keeps the list sorted"),
        ("out = list(values)", "a copy, so the caller's list is untouched"),
    ],
    "py-chain-merge-feeds": [
        ("list(dict.fromkeys(chain(a, b, c)))",
         "all three feeds end to end, with only the first sighting of each kept"),
    ],
    "py-cmp-to-key-magnitude": [
        ("abs(a) - abs(b)",
         "negative when a is the smaller in size — the comparator's contract"),
        ("sorted(nums, key=cmp_to_key(compare))",
         "sorted by that two-argument comparator"),
    ],
    "py-combinations-sums": [
        ("sorted(a + b for a, b in combinations(nums, 2))",
         "the total of every unordered pair, in order"),
    ],
    "py-counter-top-word": [
        ("min(counts, key=lambda word: (-counts[word], word))",
         "the most frequent word, ties broken alphabetically"),
    ],
    "py-dataclass-order": [
        ("sorted(Entry(*row) for row in rows)",
         "the entries in the order `order=True` gives them"),
        ("[[entry.score, entry.name] for entry in entries]",
         "each of them back as a plain pair"),
    ],
    "py-defaultdict-index": [
        ("found[value].append(index)", "note this position under the value sitting at it"),
        ("dict(found)", "an ordinary dict, no longer conjuring empty lists on lookup"),
    ],
    "py-deque-rotate": [
        ("wheel.rotate(k)", "turn the wheel k places to the right"),
    ],
    "py-enum-iterate": [
        ("[level.name for level in Level if level.value > cutoff.value]",
         "the names of every level above the cutoff"),
    ],
    "py-groupby-encode": [
        ("ch + str(len(list(run)))",
         "the character, then how many of it ran together"),
    ],
    "py-heapq-nsmallest": [
        ("heapq.nsmallest(k, nums)", "the k smallest, without sorting the whole list"),
        ("k <= 0", "nothing was asked for"),
    ],
    "py-lru-cache-climb": [
        ("ways(step - 1) + ways(step - 2)", "one step back, plus two steps back"),
        ("@lru_cache(maxsize=None)",
         "the line that turns this from exponential into linear"),
    ],
    "py-math-isqrt": [
        ("root * root == n", "the integer root, squared, lands exactly back on n"),
        ("n < 0", "no negative number is a square"),
    ],
    "py-namedtuple-rank": [
        ("key=lambda player: (-player.score, player.name)",
         "highest score first, the name only to break a tie"),
        ("[[player.name, player.score] for player in players]",
         "each of them as a plain [name, score] pair"),
    ],
    "py-ordereddict-evict": [
        ("cache.popitem(last=False)", "throw out the OLDEST key, not the newest"),
        ("len(cache) > capacity", "the cache has overflowed"),
    ],
    "py-partial-clamp": [
        ("partial(clamp, lo, hi)", "clamp, with its first two arguments already fixed"),
        ("max(low, min(high, value))", "the value pulled back inside both bounds"),
    ],
    "py-permutations-words": [
        ('sorted({"".join(order) for order in permutations(text)})',
         "every distinct rearrangement of the letters, in order"),
    ],
    "py-product-repeat": [
        ('["".join(code) for code in product(digits, repeat=length)]',
         "every code of that length, digits allowed to repeat"),
    ],
    "py-reduce-merge": [
        ("reduce(lambda acc, item: {**acc, **item}, dicts, {})",
         "fold them all into one dict, with later ones winning"),
    ],
    "py-statistics-centre": [
        ("[statistics.mean(values), statistics.median(values)]",
         "the average, then the middle value"),
    ],
    "rc-factorial": [
        ("n * factorial(n - 1)", "this number times the answer for one less than it"),
        ("n <= 1", "small enough to answer without calling itself again"),
    ],
    "rp-bst-inorder": [
        ("values[i] >= values[i + 1]", "these two are out of order, so it is not a BST"),
        ("walk(node.left)", "everything smaller than this node comes first"),
    ],
    "rp-design-editor": [
        ("self.text = self.past.pop()", "step back to the most recently saved text"),
        ("self.future = []",
         "a fresh write throws away anything that could have been redone", 8),
    ],
    "rp-design-hash-map": [
        ("self.slots[key % self.BUCKETS]", "the one bucket this key belongs in"),
        ("bucket[i] = (key, value)",
         "overwrite the pair already stored under this key"),
    ],
    "rp-matrix-rotate-counter": [
        ("[list(row) for row in zip(*grid)]", "rows and columns swapped over"),
        ("turned.reverse()",
         "and the order of the rows flipped, which together is one quarter turn"),
    ],
    "rp-rolling-max-deque": [
        ("waiting and nums[waiting[-1]] <= value",
         "the index at the tail can never be the maximum again"),
        ("waiting[0] <= i - k", "the index at the front has fallen out of the window"),
    ],
    "rp-three-sum-pair": [
        ("total < target", "too small, so the small end has to come up"),
        ("values[i] + values[left] + values[right]",
         "what the three currently chosen values add up to"),
    ],
    "rp-tree-deserialize": [
        ("node.left = build()",
         "the tokens that come next are this node's left subtree, all of them"),
        ('token == "#"', "this token says there is no node here"),
    ],
    "rp-window-k-distinct-text": [
        ("len(counts) > k", "the window is holding too many distinct characters"),
        ("counts[s[left]] -= 1",
         "the character leaving the window is one less common inside it"),
    ],
    "so-bit-flags": [
        ("flags | mask", "those bits turned on, every other bit untouched"),
        ("flags & ~mask", "those bits turned off, every other bit untouched"),
    ],
    "so-bit-single-number": [
        ("odd_one ^= value", "pairs cancel each other here; the loner does not"),
    ],
    "so-bt-combinations": [
        ("walk(value + 1)", "carry on from the NEXT value, so nothing is chosen twice"),
        ("path.pop()", "undo this choice before trying the next one"),
    ],
    "so-greedy-change": [
        ("divmod(left, coin)", "how many of this coin fit, and what is left over"),
        ("used if left == 0 else -1",
         "the count, or -1 when the amount could not be made exactly"),
    ],
    "so-greedy-profit": [
        ("prices[i] - prices[i - 1]", "the size of this one rise"),
        ("prices[i] > prices[i - 1]", "the price went up from the day before"),
    ],
    "so-int-attend-all": [
        ("free_at is not None and start < free_at",
         "this meeting begins before the previous one ended"),
        ("free_at = end", "remember when this one frees the room up"),
    ],
    "so-int-union-two": [
        ("max(a[0], b[0]) <= min(a[1], b[1])",
         "the later start is not past the earlier end, so they touch or overlap"),
        ("[[min(a[0], b[0]), max(a[1], b[1])]]", "one interval covering both of them"),
    ],
    "so-math-digit-sum": [
        ("divmod(n, 10)", "what is left, and the digit peeled off the end"),
        ("total += digit", "that digit added to the running total"),
    ],
    "so-math-is-prime": [
        ("factor * factor <= n",
         "stop once the factor would pass the square root, without computing one"),
        ("n % factor == 0", "this factor divides n exactly"),
    ],
    "so-math-lcm": [
        ("first, second = second, first % second", "one step of Euclid's algorithm"),
        ("a * b // first", "the product, divided by their greatest common divisor"),
    ],
    "so-sort-counting": [
        ("counts[value] += 1", "one more of that value seen"),
        ("[value] * seen", "that value repeated as many times as it was counted"),
    ],
    "so-sort-stable": [
        ("key=lambda record: record[0]",
         "order by the team alone, which leaves each team's members as they came"),
    ],
    "so-topo-sources": [
        ("blocked[target] += 1", "one more thing that node is waiting on"),
        ("[node for node in range(n) if blocked[node] == 0]",
         "every node that is waiting on nothing"),
    ],
    "so-uf-same-group": [
        ("parent[x] = parent[parent[x]]",
         "point straight at the grandparent, halving the path on the way up"),
        ("parent[root_b] = root_a", "join the two groups under one root"),
    ],
    "tr-count-nodes": [
        ("1 + count_nodes(root.left) + count_nodes(root.right)",
         "this node, plus everything under each side of it"),
        ("root is None", "there is no node here at all"),
    ],
    "tr-sum-tree": [
        ("root.val + sum_tree(root.left) + sum_tree(root.right)",
         "this node's number, plus each side's total"),
        ("root is None", "nothing here to add"),
    ],
    # -----------------------------------------------------------------
    # A SECOND SPAN — the same content gap, on the TUTORIAL side.
    # -----------------------------------------------------------------
    #
    # 75 of the 178 TUTORIAL declarations carried one span. Nineteen of them
    # have a second idea in the body; the rest are one-expression functions
    # and stay as they are. See the matching block in GUIDED below.
    "lang-identity-tutorial": [
        ('row.get(key) is None', 'this row holds nothing at all under that key'),
        ('missing += 1', 'one more row with nothing under that key'),
    ],
    "ob-has-value": [
        ('value in known', 'this value is one of the ones seen'),
        ('known = set(items)', 'the values already seen, in a form that answers `in` instantly'),
    ],
    "oopl-eq-default-tutorial": [
        ('[first == second, first == first, first != second]', 'what each comparison answers when nobody wrote `__eq__`'),
        ('second = Plain(value)', 'a second object with the same contents, built separately'),
    ],
    "oopl-identity-tutorial": [
        ('[a == b, a is b, a is alias]', 'equal contents, separate objects, and one object under two names'),
        ('alias = a', 'not a copy — a second name for the very same object'),
    ],
    "oopl-isinstance-tutorial": [
        ('[isinstance(obj, Animal), type(obj) is Animal]', 'one test that accepts a subclass and one that refuses it'),
        ('{"animal": Animal(), "dog": Dog()}[which]', 'the object this name stands for'),
    ],
    "oopl-mro-resolve-tutorial": [
        ('chosen().greet()', 'make one and ask it — Python decides whose `greet` that is'),
        ('return "left"', 'what Left says when it is asked'),
    ],
    "oopl-super-override-tutorial": [
        ('"[t] " + super().line(text)', "this class's prefix in front of whatever the parent produced"),
        ('return "[log] " + text', "what the parent's own version produces"),
    ],
    "pt-config-layers": [
        ('{**merged, **layer}', 'everything merged so far, with this layer laid on top of it'),
        ('merged = {}', 'nothing merged yet'),
    ],
    "pv-deque-rotate": [
        ('d.rotate(k)', 'shift everything round by k, wrapping at the ends'),
        ('deque(items)', 'a deque, which is the thing that knows how to rotate'),
    ],
    "pv-safe-divide": [
        ('a / b', 'the division that might not be legal'),
        ('return None', 'the answer when the division was not legal'),
    ],
    "pv-set-ops": [
        ('[sorted(sa | sb), sorted(sa & sb), sorted(sa - sb)]', 'in either, in both, in the first only — each of them sorted'),
        ('sa, sb = set(a), set(b)', 'both inputs as sets, which is what the operators need'),
    ],
    "py-counter-top-word": [
        ('min(counts, key=lambda word: (-counts[word], word))', 'the most frequent word, ties broken alphabetically'),
        ('Counter(words)', 'how many times each word turns up'),
    ],
    "py-deque-rotate": [
        ('wheel.rotate(k)', 'turn the wheel k places to the right'),
        ('deque(items)', 'a deque — a list cannot rotate'),
    ],
    "py-enum-iterate": [
        ('[level.name for level in Level if level.value > cutoff.value]', 'the names of every level above the cutoff'),
        ('Level[floor]', 'the member named by `floor`'),
    ],
    "py-groupby-encode": [
        ('ch + str(len(list(run)))', 'the character, then how many of it ran together'),
        ('groupby(text)', 'the text walked in runs of equal characters'),
    ],
    "sc-sort-by-key": [
        ('(-r[1], r[0])', 'score descending first, then name ascending as the tie-break'),
        ('ordered[:n]', 'just the first n of them'),
    ],
    "sc-tree-invert": [
        ('invert_tree(root.right), invert_tree(root.left)', 'each side becomes the mirrored form of the OTHER side'),
        ('root is None', 'there is no node here to mirror'),
    ],
    "so-bit-single-number": [
        ('odd_one ^= value', 'pairs cancel each other here; the loner does not'),
        ('odd_one = 0', 'the starting value that cancels with nothing'),
    ],

    # -----------------------------------------------------------------
    # FOUR SPANS THE OBJECTIVE TEST CAN SEE THROUGH.
    # -----------------------------------------------------------------
    #
    # `validate._verify_scaffold` judged only spans[0] until the ramp audit, so
    # spans 1 and 2 — which rung 3 strikes, and rung 3 is EASY's floor — were
    # served to players and never checked. Re-run over every span a rung can
    # strike, four TUTORIAL seconds turn out to be decorative: filling them with
    # a plausible neighbour passes every test. `dict(found)` because a Counter
    # and a defaultdict compare equal to the dict they hold; `[][0]` because the
    # KeyError above it already lands in the same `except LookupError`;
    # `raise SystemExit(3)` because the only neighbour anything can build is
    # `SystemExit(4)`; `int(delta.total_seconds())` because 3600.0 == 3600.
    # Each moves to a span of the same lesson that something disagrees with.
    "py-defaultdict-index": [
        ("found[value].append(index)",
         "note this position under the value sitting at it"),
        ("enumerate(items)", "each item together with the position it sits at"),
    ],
    "oopl-except-order-tutorial": [
        ('{}["missing"]', "something that fails with a KeyError"),
        ("1 / 0", "something that fails with a ZeroDivisionError"),
    ],
    "oopl-bare-except-tutorial": [
        ('kind == "exit"',
         "the input that raises the one failure `except Exception` will not catch"),
        ('raise ValueError("ordinary failure")',
         "the ordinary failure — this one the handler below does catch"),
    ],
    "pt-time-elapsed": [
        ("datetime.strptime(end, fmt) - datetime.strptime(start, fmt)",
         "how much later the end is than the start"),
        ("delta.total_seconds()", "that gap expressed in seconds"),
    ],
}

# ---------------------------------------------------------------------------
# EASY — where writing it all becomes the majority act.
# ---------------------------------------------------------------------------
#
# EASY's floor is rung 3: it may be served several blanks, and never the single
# hand-held one. That is the structural fix for the monotonicity violation the
# audit found — 21 EASY problems carrying a two-blank scaffold while TUTORIAL
# above them was a blank screen, so the ramp rose where it should have fallen.
#
# A consequence worth stating plainly: a ONE-LINE function cannot be served at
# rung 3, because there is only one idea in it to strike out. Those are left
# undeclared here on purpose. Under the floor they are served whole, which is
# the right answer for a function whose whole body is its one idea.

EASY = {
    "ah-first-unique": [
        ("counts[ch] == 1", "this character appears exactly once in the whole string"),
        ("Counter(s)", "how many times each character turns up"),
    ],
    "ah-majority": [
        ("1 if value == candidate else -1",
         "a vote for the current candidate, or one against it"),
        ("count == 0", "the votes have cancelled out, so start again from here"),
    ],
    "ah-nearby-duplicate": [
        ("value in last_seen and i - last_seen[value] <= k",
         "this value was seen before, and no more than k positions back"),
        ("last_seen[value] = i", "remember where it was last seen"),
    ],
    "ah-pivot-index": [
        ("left == total - left - value",
         "the total before this position equals the total after it"),
        ("left += value", "this value now counts as being on the left"),
    ],
    "ah-two-sum-indices": [
        ("target - value in seen",
         "the number that would complete the pair has already gone past"),
        ("[seen[target - value], i]",
         "where that earlier number was, and where this one is"),
    ],
    "ah-two-sum-values": [
        ("target - value in seen", "the partner this value needs has already gone past"),
        ("sorted([target - value, value])", "the two of them, smaller first"),
    ],
    "bs-search": [
        ("nums[mid] < target",
         "the target, if it is here at all, lies in the upper half"),
        ("lo <= hi", "there is still at least one candidate left to check"),
        ("(lo + hi) // 2", "the middle of what is left"),
    ],
    "bs-sqrt": [
        ("mid * mid <= n", "this candidate does not overshoot"),
        ("best = mid", "so it is the best answer found so far"),
        ("lo = mid + 1", "and something bigger might still fit"),
    ],
    "dll-remove": [
        ("node.prev.next = node.next",
         "the node in front now points straight past this one"),
        ("node.next.prev = node.prev", "and the node behind points back past it"),
        ("node is not None and node.val != target",
         "keep walking while there is a node and it is not the one wanted"),
    ],
    "dp-climb-stairs": [
        ("a, b = b, a + b",
         "slide the pair along: the next answer is the two before it added"),
        ("a, b = 1, 1",
         "one way to stand where you already are, and one to be a step behind"),
    ],
    "ds-moving-window": [
        ("self.total -= self.window.popleft()",
         "the value falling out of the window comes off the total"),
        ("len(self.window) > self.size", "the window has grown past its size"),
    ],
    "gen-closure-late-binding": [
        ("lambda v, factor=factor: v * factor",
         "a function holding THIS factor, not whatever the loop ends on"),
        ("[fn(value) for fn in built]",
         "each of those functions handed the same value"),
    ],
    "gen-ctx-vault": [
        ('self.log.append("lock")',
         "what leaving records, whether the block finished or blew up"),
        ('self.log.append("unlock")', "what entering records"),
    ],
    "gen-deco-at-least": [
        ("max(floor, fn(*args, **kwargs))",
         "the wrapped function's answer, never allowed below the floor"),
        ("[score(value) for value in values]",
         "every value put through the decorated function"),
    ],
    "gen-deco-memoize": [
        ("cache[value] = fn(value)", "work it out once, and keep the answer"),
        ("value not in cache", "this argument has not been asked about before"),
    ],
    "gen-fixed_window-guild-3": [
        ("values[i] - values[i - k]", "the value coming in, less the value going out"),
        ("sum(values[:k])", "the first window, totalled the slow way, once"),
    ],
    "gen-fixed_window-market-6": [
        ("values[i] - values[i - k]", "the value coming in, less the value going out"),
        ("sum(values[:k])", "the first window, totalled the slow way, once"),
    ],
    "gen-fixed_window-telemetry-0": [
        ("values[i] - values[i - k]", "the value coming in, less the value going out"),
        ("sum(values[:k])", "the first window, totalled the slow way, once"),
    ],
    "gen-fixed_window-sensors-2": [
        ("window and values[window[-1]] >= value",
         "the index at the tail can never be the minimum again"),
        ("window[0] <= i - k", "the index at the front has fallen out of the window"),
    ],
    "gen-fixed_window-telemetry-5": [
        ("window and values[window[-1]] >= value",
         "the index at the tail can never be the minimum again"),
        ("window[0] <= i - k", "the index at the front has fallen out of the window"),
    ],
    "gen-frequency-caravan-4": [
        ("counts[item] == 1", "this item appears exactly once in the whole list"),
        ("Counter(items)", "how many times each item turns up"),
    ],
    "gen-frequency-market-1": [
        ("counts[item] == 1", "this item appears exactly once in the whole list"),
        ("Counter(items)", "how many times each item turns up"),
    ],
    "gen-frequency-sensors-7": [
        ("counts[item] == 1", "this item appears exactly once in the whole list"),
        ("Counter(items)", "how many times each item turns up"),
    ],
    # DERIVED ORDER OVERRIDDEN. The hand-blanked starter put `visited.add(...)`
    # first, and the objective test proved it can be filled with `discard` and
    # still pass every test — without the mark the search re-queues cells and is
    # slower, but it still finds the shortest path. The step that carries
    # correctness is the one that queues the neighbour one further out.
    "sc-bfs-grid-shortest": [
        ("frontier.append((nr, nc, dist + 1))",
         "queue it, one step further out than the cell it came from"),
        ("visited.add((nr, nc))",
         "claim the cell when it is QUEUED, not when it is dequeued, "
         "or it enters the frontier many times"),
    ],
    "gen-genexp-pipeline": [
        ("sum(len(line) for line in kept)", "the total length of what survived"),
        ("line.strip() for line in lines",
         "each line with its surrounding space gone — one at a time, not all at once"),
    ],
    "gen-infinite-naturals": [
        ("yield value", "hand back the current number and pause here"),
        ("list(islice(naturals(start), n))", "the first n of an endless stream"),
    ],
    "gen-iter-class": [
        ("self.current <= 0", "the countdown has finished"),
        ("self.current -= 1", "one lower for next time"),
    ],
    "gen-iter-reiterable": [
        ("value < self.stop", "there is still room before the stop"),
        ("value += self.step", "move on by one step"),
    ],
    "gen-pair-caravan-4": [
        ("target - value in seen",
         "the number that completes the pair has already gone past"),
        ("[seen[target - value], i]",
         "where that earlier number was, and where this one is"),
    ],
    "gen-pair-market-1": [
        ("target - value in seen",
         "the number that completes the pair has already gone past"),
        ("[seen[target - value], i]",
         "where that earlier number was, and where this one is"),
    ],
    "gen-pair-sensors-7": [
        ("target - value in seen",
         "the number that completes the pair has already gone past"),
        ("[seen[target - value], i]",
         "where that earlier number was, and where this one is"),
    ],
    "gen-pair-guild-3": [
        ("seen[target - value]", "how many earlier values this one pairs with"),
        ("seen[value] += 1", "and this value is now there to be paired with later"),
    ],
    "gen-pair-market-6": [
        ("seen[target - value]", "how many earlier values this one pairs with"),
        ("seen[value] += 1", "and this value is now there to be paired with later"),
    ],
    "gen-pair-telemetry-0": [
        ("seen[target - value]", "how many earlier values this one pairs with"),
        ("seen[value] += 1", "and this value is now there to be paired with later"),
    ],
    "gen-pair-sensors-2": [
        ("target - value in seen", "the partner this value needs has already gone past"),
        ("seen.add(value)", "and this value is now available as a partner"),
    ],
    "gen-pair-telemetry-5": [
        ("target - value in seen", "the partner this value needs has already gone past"),
        ("seen.add(value)", "and this value is now available as a partner"),
    ],
    "gen-return-stops": [
        ("value >= limit", "this value reaches the limit, so the stream is over"),
        ("yield value", "hand this one back and pause here"),
    ],
    "gen-yieldfrom-flatten": [
        ("yield from group", "every item of this group, without writing an inner loop"),
        ("list(flatten(groups))", "all of them, drawn out into one list"),
    ],
    "gr-bfs-order": [
        ("seen.add(nxt)", "mark it on the way IN, or it gets queued twice"),
        ("queue.popleft()",
         "the node that has waited longest — which is what makes this breadth-first"),
    ],
    "gr-dfs-order": [
        ("node in seen", "this node has already been walked"),
        ("walk(nxt)", "go all the way down this neighbour before trying the next"),
    ],
    "gr-flood-fill": [
        ("0 <= r < rows and 0 <= c < cols and grid[r][c] == start",
         "inside the grid, and part of the region being filled"),
        ("not grid or grid[sr][sc] == colour",
         "there is nothing to do — and filling anyway would loop forever"),
    ],
    "lang-anyall-easy": [
        ("all(len(row) == width for row in rows)", "every row is exactly this wide"),
        ("any(len(row) == 0 for row in rows)", "at least one row is empty"),
    ],
    "lang-args-easy": [
        ("row(**values)", "call it with the dict's keys used as parameter names"),
        ('f"{name}:{score}:{state}"', "the three fields, separated by colons"),
    ],
    "lang-nested-easy": [
        ('[m for team in org["teams"] for m in team["members"]]',
         "every member of every team, in one flat list"),
        ("sorted(names)", "those names in order"),
    ],
    "lang-set-easy": [
        ("set(required) - have", "the required keys that were not provided"),
        ("set(provided)", "what was provided, as a set"),
    ],
    "lang-truthy-easy": [
        ("name for name, value in config.items() if value",
         "the names whose value counts as on"),
        ("name for name, value in config.items() if not value",
         "and the names whose value does not"),
    ],
    "lang-unpack-easy": [
        ("first, *middle, last = items",
         "the first, the last, and everything between — in one statement"),
        ("[first, last, middle]", "those three, in that order"),
    ],
    "ll-add-one": [
        ("carry + (node.val if node is not None else 0)",
         "this digit plus the carry, treating a finished list as zero"),
        ("carry = total // 10", "what carries into the next digit"),
        ("ListNode(total % 10)", "the digit that stays here"),
    ],
    "ll-cycle-length": [
        ("runner is not slow", "one lap of the ring, back to where it started"),
        ("slow is fast", "the two pointers are on the SAME node, not on equal ones"),
    ],
    "ll-intersect": [
        ("la > lb", "the first list is the longer one, so it starts further back"),
        ("a.val == b.val", "both lists are showing the same value here"),
    ],
    "ll-merge-alternate": [
        ("a if a is not None else b", "whichever list still has nodes left in it"),
        ("tail.next = a", "take one from the first list"),
    ],
    "ll-reverse-rec": [
        ("head.next.next = head",
         "the node in front of me turns round to point back at me"),
        ("head is None or head.next is None",
         "nothing, or one node: already reversed either way"),
    ],
    "ll-value-at": [
        ("steps == index", "this is the position that was asked for"),
        ("steps += 1", "one node further along"),
    ],
    "lru-hits": [
        ("key in order", "this key was already in the cache"),
        ("order.pop(0)", "throw out whatever is at the front"),
    ],
    "ob-add-lists": [
        ("x + y", "one from each list, added together"),
        ("zip(a, b)", "the two lists walked in step"),
    ],
    "ob-dict-lines": [
        ('str(key) + "=" + str(prices[key])',
         "the key, an equals sign, and that key's price"),
        ("sorted(prices)", "the keys in order, so the output is predictable"),
    ],
    "ob-first-repeat": [
        ("value in seen", "this value has turned up before"),
        ("seen.add(value)", "record that it has now been seen"),
    ],
    "ob-helper-call": [
        ("len(word) * 2", "twice the length of the word"),
        # Pinned: `doubled_length(word)` is also the helper's own def line, and
        # blanking that leaves `def __BLANK__:`.
        ("doubled_length(word)", "the helper, called on this word", 6),
    ],
    "ob-index-of": [
        ("value == target", "this is the value being looked for"),
        ("enumerate(items)", "each item together with where it sits"),
    ],
    "ob-keep-long-words": [
        ("len(word) >= least", "this word is long enough to keep"),
        ("out.append(word)", "so keep it"),
    ],
    "oopl-bool-is-int-easy": [
        ("sum(1 for value in values if isinstance(value, int))",
         "how many are ints — counting bools, which ARE ints"),
        ("sum(1 for value in values if type(value) is int)",
         "how many are exactly int and nothing else"),
    ],
    "oopl-classattr-easy": [
        ("self.contents = []",
         "a fresh list for THIS pack; in the class body it would be one shared list"),
        ("self.contents.append(item)", "add to this pack's own list"),
    ],
    "oopl-container-easy": [
        ("len(self.names)", "how many names — this is what `len()` will report"),
        ("name in self.names", "this is what `in` will answer"),
    ],
    # THE EXERCISE IS THE BLOCK LADDER, NOT THE PAYLOAD. This declared the two
    # `order.append(...)` calls, which sit one line under the `else:` and
    # `finally:` keywords that name their own strings and are visibly identical
    # to the three appends left standing around them. At EASY's floor both are
    # struck at once, so the whole served exercise was transcribing two lines
    # the player can read three copies of. The spans move to the two lines that
    # decide where control actually goes.
    "oopl-else-finally-easy": [
        ('kind == "boom"', "the input that makes this block fail"),
        ('raise ValueError("boom")',
         "the failure that sends control to the except clause"),
    ],
    "oopl-eq-hash-easy": [
        ("hash((self.x, self.y))",
         "the same fields `__eq__` compares, in the same order"),
        ("(self.x, self.y) == (other.x, other.y)",
         "two points are equal when both coordinates match"),
    ],
    "oopl-iter-exhaust-easy": [
        ("self.current <= 0", "the countdown has finished"),
        ("self.current + 1",
         "the value from before the decrement, because it has already happened"),
    ],
    "oopl-ordering-easy": [
        ("self.points < other.points", "which of two scores comes first"),
        ("[score.name for score in ordered]",
         "the names in the order `__lt__` put them"),
    ],
    "oopl-property-validate-easy": [
        ("value < 0", "a balance that has to be refused"),
        ("self._balance = value", "the one place the number is actually stored"),
    ],
    "oopl-raise-from-easy": [
        ('raise ParseError("bad port: " + text) from exc',
         "a failure in this module's own vocabulary, with the original kept behind it"),
        ("int(text)", "the conversion that might not work"),
    ],
    "oopl-state-easy": [
        ("move < 0 and self.balance + move < 0",
         "a withdrawal that would take the balance below zero"),
        ("self.balance += move", "otherwise, apply it"),
    ],
    "oopl-super-chain-easy": [
        ('super().parts() + ["middle"]',
         "everything the parent listed, then this class's own part"),
        ('super().parts() + ["leaf"]', "the same again, one level further down"),
    ],
    "pt-class-touch": [
        ("self.order.remove(key)", "take the key out of the position it is in", 40),
        ("self.order.append(key)", "and put it back as the youngest", 41),
        ("key not in self.values",
         "the key is not here at all, so there is nothing to make younger"),
    ],
    "pt-config-deep-merge": [
        ("deep_merge(current, value)",
         "two dicts at this key, so merge those the same way, all the way down"),
        ("isinstance(current, dict) and isinstance(value, dict)",
         "both sides of this key are dicts"),
    ],
    "pt-csv-sum-by": [
        ("totals[record[group_by]] += value", "add this amount to its group's total"),
        ("int(record[amount])", "the amount as a number, which may not convert"),
    ],
    "pt-file-settings": [
        ('text.partition("=")', "the line split at the FIRST equals sign only"),
        ('not text or text.startswith("#") or "=" not in text',
         "there is nothing on this line that is a setting"),
    ],
    "pt-log-worst-path": [
        ("status >= 500", "a server-side failure, not a client one"),
        ("sorted(failures, key=lambda path: (-failures[path], path))[0]",
         "the path that failed most, ties broken by name"),
    ],
    "pt-time-duration": [
        ("seconds % 86400 // 3600", "whole hours, once the days are taken out"),
        ("seconds % 3600 // 60", "whole minutes, once the hours are taken out"),
    ],
    "pt-time-sort": [
        ('datetime.strptime(record["at"], "%d/%b/%Y:%H:%M:%S")',
         "the timestamp parsed into something that can be ordered"),
        ('[record["id"] for record in sorted(records, key=moment)]',
         "the ids, oldest first"),
    ],
    "pv-chunk": [
        ("[items[i:i + size] for i in range(0, len(items), size)]",
         "slices of that size, the last one short if it has to be"),
        ("size <= 0", "a size that cannot make any chunk at all"),
    ],
    "pv-dedupe-preserve": [
        ("value not in seen", "this value has not turned up before"),
        ("out.append(value)", "keep it, in the order it arrived"),
    ],
    "pv-defaultdict-group": [
        ("out[key].append(value)",
         "file this value under its key, with no 'is the key there yet' check"),
        ("{k: out[k] for k in sorted(out)}", "a plain dict of that, keys in order"),
    ],
    "pv-rotate": [
        ("items[-k:] + items[:-k] if k else list(items)",
         "the last k moved to the front — and no rotation at all when k is zero"),
        ("k %= len(items)", "a rotation bigger than the list just wraps round"),
    ],
    "py-bisect-range": [
        ("bisect.bisect_left(values, lo)", "the first position not below lo"),
        ("bisect.bisect_right(values, hi)", "the first position past hi"),
    ],
    "py-cmp-to-key-versions": [
        ('[int(piece) for piece in version.split(".")]',
         "the version as numbers, so 10 sorts after 9 instead of before it"),
        ("left < right", "a is the earlier version"),
    ],
    "py-counter-ransom": [
        ("Counter(note) - Counter(letters)",
         "what the note needs that the letters do not supply"),
        ("not missing", "nothing is missing"),
    ],
    "py-defaultdict-adjacency": [
        ("graph[a].add(b)", "b is a neighbour of a"),
        ("graph[b].add(a)", "and the edge goes both ways"),
    ],
    "py-groupby-longest": [
        ("[[value, len(list(run))] for value, run in groupby(items)]",
         "each run as [the value, how long it ran]"),
        ("max(runs, key=lambda entry: entry[1])",
         "the longest of them, and the FIRST one on a tie"),
    ],
    "py-lru-cache-grid": [
        ("routes(r - 1, c) + routes(r, c - 1)",
         "the ways in from above, plus the ways in from the left"),
        ("r == 0 or c == 0", "on an edge, where there is exactly one way in"),
    ],
    "py-reduce-intersect": [
        ("sorted(reduce(set.intersection, map(set, lists)))",
         "the values present in every one of the lists, in order"),
        ("not lists", "there is nothing to intersect at all"),
    ],
    "rc-digit-reduce": [
        ("sum(int(d) for d in str(n))", "this number's digits added up"),
        ("n >= 10", "there is still more than one digit left"),
    ],
    "rp-tree-round-trip": [
        ('tokens.append("#")', "the marker that says there is no node here"),
        ("node.left = read()",
         "the tokens that come next are the left subtree, all of them"),
    ],
    "sec-alert-burst": [
        ("window -= counts[i - k]",
         "the count leaving the window comes off the running total"),
        ("window += value", "and the one arriving goes on"),
    ],
    "sec-alert-logger": [
        ("previous is not None and timestamp < previous + self.cooldown",
         "seen before, and still inside its cooldown"),
        ("self.last[message] = timestamp",
         "record when this message was last let through"),
    ],
    "sec-alert-queue": [
        ("queue.popleft()", "the oldest alert is the one that gets dropped"),
        ("len(queue) == capacity", "the buffer is already full"),
    ],
    "sec-egress-burst": [
        ("sizes[i] - sizes[i - k]", "the size coming in, less the size going out"),
        ("k > len(sizes)", "the window is wider than all the data there is"),
    ],
    "sec-first-repeat-asset": [
        ("asset in seen", "this asset has already come past"),
        ("seen.add(asset)", "record that it has now"),
    ],
}

# ---------------------------------------------------------------------------
# MEDIUM — a recovery rung, not a teaching one.
# ---------------------------------------------------------------------------
#
# MEDIUM's floor is rung 4: a player in good standing is served the whole
# function, always. These declarations exist for one path only — a lapsed SRS
# review, which drops the serving by exactly one rung (see `srs.review_rung`).
# That is the only route to a scaffold at MEDIUM, and it is why the expected mix
# puts 10% here rather than zero: the tenth of MEDIUM servings that are
# scaffolded are the ones where the player has just forgotten something.
#
# One per spaced-repetition family as far as the families go, so that whichever
# family a player lapses in, a rung below the blank screen exists there.

MEDIUM = {
    "ah-group-anagrams": [
        ('"".join(sorted(word))',
         "a signature every anagram of this word shares, and no other word does"),
        ("[sorted(group) for group in buckets.values()]",
         "each bucket's words, in order"),
    ],
    "ah-longest-consecutive": [
        ("value - 1 in pool",
         "something one smaller is here too, so this is not the start of a run"),
        ("value + length in pool", "the run carries on one further"),
    ],
    "ah-merge-intervals": [
        ("out and start <= out[-1][1]",
         "this interval touches or overlaps the last one kept"),
        ("max(out[-1][1], end)", "the further of the two ends"),
    ],
    "ah-product-except-self": [
        ("out[i] = running", "everything to the left of here, multiplied together"),
        ("out[i] *= running", "times everything to the right of here"),
    ],
    "ah-subarray-sum-k": [
        ("counts.get(running - k, 0)",
         "how many earlier prefixes would leave exactly k behind"),
        ("counts[running] = counts.get(running, 0) + 1",
         "this prefix is now available to be subtracted from a later one"),
    ],
    "ah-three-sum": [
        ("i and nums[i] == nums[i - 1]",
         "the same first value as last time, so the triples would repeat"),
        ("lo < hi and nums[lo] == nums[lo - 1]",
         "and the same second value, which would repeat too"),
    ],
    "ah-three-sum-target": [
        ("total < target", "too small, so the small end has to come up"),
        ("nums[i] + nums[lo] + nums[hi]",
         "what the three currently chosen values add up to"),
    ],
    "ah-two-sum-count": [
        ("seen[target - value]", "how many earlier values this one pairs with"),
        ("seen[value] += 1", "and this value is now there to be paired with later"),
    ],
    "bs-peak": [
        ("nums[mid] < nums[mid + 1]", "still climbing, so the peak is further right"),
        ("hi = mid", "mid might itself be the peak, so do not step past it"),
    ],
    "bs-rotated": [
        ("nums[lo] <= nums[mid]", "the left half is the sorted one"),
        ("nums[lo] <= target < nums[mid]",
         "and the target lies inside that sorted half"),
    ],
    "dll-deque": [
        ("node.next = anchor.next",
         "the new node points at whatever the anchor was pointing at"),
        ("anchor.next.prev = node", "and that node now points back at the new one"),
    ],
    "dp-coin-change": [
        ("min(dp[value], dp[value - coin] + 1)",
         "the better of what we had and one coin more than the smaller amount"),
        ("coin <= value", "this coin is not bigger than the amount being made"),
    ],
    "dp-decode-ways": [
        ('10 <= int(digits[i - 1:i + 1]) <= 26',
         "these two digits together make a letter"),
        ('digits[i] != "0"', "this digit can stand as a letter on its own"),
    ],
    "dp-house-robber": [
        ("skip + value",
         "rob this house: what skipping the last one left us, plus this one"),
        ("max(skip, take)", "skip this house: the better of the two from last time"),
    ],
    "dp-max-subarray": [
        ("max(value, current + value)",
         "extend the run, or start fresh here — whichever is bigger"),
        ("max(best, current)", "the best seen anywhere so far"),
    ],
    "dp-min-path-sum": [
        ("min(dp[r - 1][c], dp[r][c - 1])",
         "the cheaper of arriving from above and arriving from the left"),
        ("dp[0][c - 1]", "along the top row there is only the cell to the left"),
    ],
    "dp-unique-paths": [
        ("row[c - 1]",
         "the ways in from the left, added to the ways already in from above"),
        ("rows <= 0 or cols <= 0", "a grid with no cells in it at all"),
    ],
    "dp-word-break": [
        ("dp[start] and s[start:end] in pool",
         "everything up to start already breaks, and what follows is a whole word"),
        ("[True] + [False] * len(s)",
         "the empty prefix breaks; nothing else is known yet"),
    ],
    "ds-hash-map": [
        ("hash(key) % self.size", "which bucket this key belongs in"),
        ("slot[i] = (key, value)",
         "overwrite the pair already stored under this key"),
    ],
    "ds-undo-redo": [
        ("self.undone.clear()",
         "a new action throws away anything that could have been redone"),
        ("self.done.pop()", "the most recent action, taken back off"),
    ],
    "gen-best_run-caravan-4": [
        ("max(value, current + value)",
         "extend the run, or start fresh here — whichever is bigger"),
        ("max(best, current)", "the best seen anywhere so far"),
    ],
    "gen-best_run-market-1": [
        ("max(value, current + value)",
         "extend the run, or start fresh here — whichever is bigger"),
        ("max(best, current)", "the best seen anywhere so far"),
    ],
    "gen-best_run-sensors-7": [
        ("max(value, current + value)",
         "extend the run, or start fresh here — whichever is bigger"),
        ("max(best, current)", "the best seen anywhere so far"),
    ],
    "gen-best_run-guild-3": [
        ("min(value, current + value)",
         "extend the run, or start fresh here — whichever is smaller"),
        ("min(best, current)", "the smallest seen anywhere so far"),
    ],
    "gen-best_run-market-6": [
        ("min(value, current + value)",
         "extend the run, or start fresh here — whichever is smaller"),
        ("min(best, current)", "the smallest seen anywhere so far"),
    ],
}


# ---------------------------------------------------------------------------
# GUIDED — the one that was left.
# ---------------------------------------------------------------------------
#
# GUIDED was already at 93.5%: 186 of its 199 write-code problems ship a
# hand-blanked starter, and those convert mechanically (see
# `scaffold.derive_spans`). Of the thirteen that did not, eleven are
# RUNE_ASSEMBLY — an ordering puzzle with no editor at all, which is a scaffold
# of a different kind and cannot carry a blank — and one is a DEBUG_BATTLE,
# whose starter must stay broken or there is no bug to find. That leaves one.

GUIDED = {
    # Seventeen of the derived declarations arrived with a blank that had no
    # sentence beside it — the author had put the teaching in a comment the
    # deriver could not attach to a span, or had not written one. A blank with
    # no gloss is a guessing game, so those seventeen are written out here by
    # hand and override the derived reading.
    "ob-say-hello": [
        ("name", "the name that was handed in"),
    ],
    "ob-list-append": [
        ("append", "the list method that puts one value on the end"),
    ],
    "ob-count-to": [
        ("n + 1", "one past n, because range stops before its end"),
    ],
    "ob-repeat-text": [
        ('""', "an empty string — nothing has been added to it yet"),
        ("times", "how many times to go round"),
    ],
    "ob-is-even": [
        ("0", "the remainder an even number leaves behind"),
    ],
    "ob-bigger": [
        (">", "a is the larger of the two"),
        ("b", "the other one, then"),
    ],
    "ob-dict-store": [
        ("item", "the key to file it under"),
        ("price", "the value to file there"),
    ],
    "ob-two-arguments": [
        ("height", "the second measurement"),
    ],
    "ob-enumerate-pairs": [
        ("enumerate", "the builtin that hands you the position as well as the value"),
        ("[index, value]", "the position and the value, together"),
    ],
    "ob-comprehension-first": [
        ("value * 2", "twice each number — the expression comes before the `for`"),
        ("nums", "the list being walked"),
    ],
    "lang-default-guided": [
        ('"Hello"', "the greeting to use when the caller does not say"),
    ],
    "oopl-default-guided": [
        ("None", "the sentinel meaning 'the caller gave nothing' — never a list"),
    ],
    "oopl-try-guided": [
        ("ZeroDivisionError", "the one failure this is allowed to swallow"),
    ],
    "oopl-custom-exc-guided": [
        ("Exception", "the base that every ordinary failure inherits from"),
    ],
    "oopl-narrow-guided": [
        ("(ValueError, TypeError)",
         "both of the recoverable failures, named as a tuple"),
    ],
    "so-bt-binary-strings": [
        ('prefix + "1"', "the other branch: this prefix with a one on the end"),
    ],
    "so-sort-rank": [
        ("-record[1]",
         "highest score first — negated, so ascending order puts the best on top"),
    ],
    # FIVE SHIPPED SCAFFOLDS THAT DO NOT PARSE.
    #
    # `families/scaffolds.py` states the rule in its own docstring: "`__BLANK__`
    # is a bare name, so the starter always parses. A player who runs it
    # untouched gets a NameError naming the rune they still owe, not a
    # SyntaxError pointing at column one." Five starters break it, by striking
    # out an operator or a keyword — `if a __BLANK__ b:`, `__BLANK__ total`,
    # `return value __BLANK__ None`. Nothing checked, because nothing has ever
    # checked a blank. The span moves to the whole expression, which is both the
    # idea and a thing a bare name can stand in for.
    "ob-bigger": [
        ("a > b", "a is the larger of the two"),
        ("b", "the other one, then", 4),
    ],
    "ob-return-not-print": [
        ("return total",
         "hand the number back — `print` only shows it, and the grader cannot see it"),
    ],
    "lang-truthy-guided": [
        ("value or fallback",
         "the value if it is anything at all, and the fallback if it is not"),
    ],
    "lang-identity-guided": [
        ("value is None",
         "nothing was supplied at all — 0 and \"\" and [] are present, not missing"),
    ],
    "pt-file-clean": [
        ("[line.strip() for line in lines if line.strip()]",
         "each line trimmed, with the ones that were only whitespace dropped"),
    ],
    # A CODE_BATTLE that shipped with a `__BLANK__` frozen into its starter.
    # Nothing validated blanks, so it survived. The blank itself was a good one;
    # it was in the wrong place. `apply()` moves it here and gives the problem
    # back its blank screen.
    "pt-class-latest": [
        ("reversed(self.events)",
         "walk the events newest first, so the first match is the answer"),
    ],
    "rp-design-tally": [
        ("self.counts.get(item, 0) + 1",
         "one more than this item's count, treating a missing item as zero"),
        ("self.counts.get(item, 0)", "this item's count, or zero if it has none"),
        ("min(self.counts, key=lambda item: (-self.counts[item], item))",
         "the commonest item, ties broken by name"),
    ],
    # -----------------------------------------------------------------
    # A SECOND SPAN, so rung 3 exists at the bottom of the ramp.
    # -----------------------------------------------------------------
    #
    # 120 of the 184 GUIDED declarations carried exactly one span, so
    # `scaffold.available_rungs` returned (1, 2, 4) and `scaffold.servable`
    # fell a player who had EARNED rung 3 straight up to rung 4 — a blank
    # screen at the easiest band in the game. Measured on the live selector,
    # all 13 of the 62 GUIDED encounters served at rung 4 were one-span
    # problems, which dragged GUIDED to 79.0% scaffolded while TUTORIAL above
    # it carried a blank on 100.0% of its encounters. That one fact IS the
    # monotonicity failure: the ramp rose exactly where it should have fallen.
    #
    # `scaffold.servable` names it in a comment as a content gap and declines
    # to paper over it, because falling DOWN the ladder was measured and costs
    # the invariant that makes rung evidence mean anything. So it is closed
    # here, where content gaps are closed: a second span for every one-span
    # problem that has a second idea in it. The ones left alone are the
    # genuine one-line, one-idea functions — `def area(width, height): return
    # width * height` has one idea and asking a player to fill in two blanks
    # over it would be inventing a second one.
    "fs-elif-blank": [
        ('score >= 50', 'the test for the middle band'),
        ('score >= 90', 'the test for the top band'),
    ],
    "fs-if-blank": [
        ('role == "admin"', 'the question: is this role the admin?'),
        ('return "denied"', 'what comes back when the role is anything else'),
    ],
    "fs-list-loop-blank": [
        ('len(word) >= least', 'the test: is this word long enough?'),
        ('found + 1', 'one more than the tally so far'),
    ],
    "fs-loop-blank": [
        ('running + len(word)', "the running total, plus this word's length"),
        ('running = 0', 'the total before a single word has been added to it'),
    ],
    "gen-closure-blank": [
        ('amount', '`amount` belongs to make_adder, and `add` can still see it', 2),
        ('return add', 'hand back the inner function itself — no parentheses, because it is not being called here'),
    ],
    "gen-closure-nonlocal-blank": [
        ('nonlocal count', 'declare that `count` is the outer one, not a new local'),
        ('count += 1', 'one more than the count that survived the last call'),
    ],
    "gen-ctx-contextmanager-blank": [
        ('yield log', 'hand the log to the block, and pause here'),
        ('log.append("exit:" + name)', 'the note that the block has finished, raised or not'),
    ],
    "gen-ctx-enter-blank": [
        ('return self', 'this is what `as handle` will name'),
        ('self.events.append("close")', 'the note that the block has finished'),
    ],
    "gen-ctx-exit-blank": [
        ('self.log.append("close")', 'the cleanup: record that the door closed'),
        ('return False', 'do not swallow the failure — let it carry on out of the block'),
    ],
    "gen-deco-args-blank": [
        ('return decorate', 'what @repeat(times) evaluates to must be a decorator'),
        ('[fn(*args, **kwargs) for _ in range(times)]', "the wrapped call's answer, collected once for every repeat"),
    ],
    "gen-deco-blank": [
        ('return wrapper', 'a decorator must hand back the replacement function'),
        ('fn(value) * 2', "the wrapped function's answer, doubled"),
    ],
    "gen-deco-passthrough": [
        ('fn(*args, **kwargs)', 'call the wrapped function with whatever arguments arrived'),
        ('return wrapper', 'a decorator hands back the replacement function, not a call to it'),
    ],
    "gen-deco-wraps-blank": [
        ('@wraps(fn)', "copy fn's name and docstring onto the wrapper"),
        ('return wrapper', 'a decorator hands back the replacement function, not a call to it'),
    ],
    "gen-iter-cursor": [
        ('iter(items)', '`next()` needs something to advance. Make one out of `items`.'),
        ('[next(cursor), next(cursor)]', 'the first value, and then the one after it'),
    ],
    "gen-iter-default": [
        ('next(cursor, None)', 'the third value, or None if the cursor has already run out', 4),
        ('iter(items)', 'something `next()` can advance through'),
    ],
    "gen-yield-filter": [
        ('value % 2 == 0', 'keep it only when it divides by two'),
        ('yield value', 'hand this one out, then pause here until the next is asked for'),
    ],
    "gen-yield-first": [
        ('yield i * i', "hand back this number's square, then pause here"),
        ('range(n)', 'the numbers from zero up to but not including n'),
    ],
    "gen-yieldfrom-blank": [
        ('yield from second', 'now the same, for `second`'),
        ('yield from first', 'hand out everything in `first`, one at a time'),
    ],
    "lang-tuple-guided": [
        ('(a, b)', 'Build the pair. One comma is all it takes.', 1),
        ('list(pair)', 'the pair as a list, which is what the caller wants back'),
    ],
    "lang-unpack-guided": [
        ('first, second', 'Two names on the left, one sequence on the right.'),
        ('[second, first]', 'the two values, the other way round'),
    ],
    "ob-is-even": [
        ('0', 'the remainder an even number leaves behind'),
        ('return True', 'what comes back when there is nothing left over'),
    ],
    "ob-list-append": [
        ('append', 'the list method that puts one value on the end'),
        ('return items', 'hand the copy back, with the new value on the end'),
    ],
    "ob-return-not-print": [
        ('return total', 'hand the number back — `print` only shows it, and the grader cannot see it'),
        ('price * quantity', 'the two numbers multiplied together'),
    ],
    "ob-store-value": [
        ('n * 2', '`doubled` is a name for a value. Give it the right value.'),
        ('return doubled', 'hand back the value you have just named'),
    ],
    "oopl-classattr-guided": [
        ('Golem.made += 1', 'Count this golem. Name the class, not `self`.'),
        ('Golem.made = 0', 'wipe the shared tally before counting this batch'),
    ],
    "oopl-custom-exc-guided": [
        ('Exception', 'the base that every ordinary failure inherits from'),
        ('raise ConfigError("missing setting: " + key)', 'the failure to throw when the key is not there'),
    ],
    "oopl-default-guided": [
        ('None', "the sentinel meaning 'the caller gave nothing' — never a list"),
        ('bag = []', 'a fresh empty list, made new on every call'),
    ],
    "oopl-eq-guided": [
        ('self.number == other.number', 'Two badges match when their numbers do.'),
        ('isinstance(other, Badge)', 'the check that the other thing is a badge at all'),
    ],
    "oopl-gil-guided": [
        ('"processes"', 'Only one thread can run bytecode at a time. Which pool?'),
        ('workload == "cpu"', 'the one kind of work that fights over the lock'),
    ],
    "oopl-init-guided": [
        ('y', '`self` is this particular Point. Give it a `y` as well.', 3),
        ('self.x = x', 'store the x that was handed in on this particular Point'),
    ],
    "oopl-iter-guided": [
        ('iter(self.items)', 'Return an ITERATOR, not the list itself.'),
        ('self.items = list(items)', 'keep a list of our own, so the Bag owns its contents'),
    ],
    "oopl-len-guided": [
        ('len(self.items)', 'Forward the question to the list you are wrapping.'),
        ('self.items = list(items)', 'keep a list of our own, so the Bag owns its contents'),
    ],
    "oopl-lt-guided": [
        ('self.seconds < other.seconds', 'Fewer seconds means smaller.'),
        ('sorted(runs)', 'the runs in order, which is the whole point of `__lt__`'),
    ],
    "oopl-mro-guided": [
        ('chosen.__mro__', 'Every class carries its lookup order. Walk it and take the names.'),
        ('{"A": A, "B": B, "C": C, "D": D}[which]', 'the class this name stands for'),
    ],
    "oopl-narrow-guided": [
        ('(ValueError, TypeError)', 'both of the recoverable failures, named as a tuple'),
        ('out.append(int(value))', 'the conversion that might fail, and the answer when it does not'),
    ],
    "oopl-property-guided": [
        ('self.width * self.height', 'Computed on every read. No parentheses at the call site.'),
        ('Rect(width, height).area', 'the area, read like a plain attribute — no parentheses'),
    ],
    "oopl-repr-guided": [
        ('f"Card({self.rank!r}, {self.suit!r})"', '`!r` inside an f-string means "use repr() on this field".'),
        ('repr(Card(rank, suit))', 'what `repr()` makes of a Card'),
    ],
    "oopl-slots-guided": [
        ('("x", "y")', 'Name the two attributes this class is allowed to have.'),
        ('list(Pixel.__slots__)', 'the two names the class declared, as a list'),
    ],
    "oopl-staticmethod-guided": [
        ('text.upper()', 'No `self` here: a static method gets exactly what it is passed.'),
        ('TextTools.shout(text)', 'call it on the class itself — there is no instance here'),
    ],
    "oopl-super-guided": [
        ('super().__init__(name)', 'Run User.__init__ so `name` actually gets stored.'),
        ('self.clearance = clearance', 'the field this subclass adds of its own'),
    ],
    "oopl-try-guided": [
        ('ZeroDivisionError', 'the one failure this is allowed to swallow'),
        ('return None', 'the answer when the division was not legal'),
    ],
    "pt-class-latest": [
        ('reversed(self.events)', 'walk the events newest first, so the first match is the answer'),
        ('event["kind"] == kind', 'this event is of the kind we were asked about'),
    ],
    "pt-config-override": [
        ('merged.update(extra)', 'lay the second dict over the copy'),
        ('return merged', 'hand back the copy, with the second dict laid over it'),
    ],
    "pt-feature-average": [
        ('round(total / count, 2) if count else 0.0', 'the average, to two decimals, with the empty case answered'),
        ('total += sample', 'add this sample to the running total'),
    ],
    "pt-json-get-path": [
        ('current = current[key]', 'step down to the value this key points at'),
        ('key not in current', 'this key is missing from the level we are standing on'),
    ],
    "pt-log-count-errors": [
        ('fields[2] == "ERROR"', 'the level lives at index 2 — compare it, do not search the line'),
        ('line.split()', 'the line cut into its whitespace-separated fields'),
    ],
    "pt-refactor-enumerate": [
        ('enumerate(lines, 1)', 'walk the lines together with their 1-based numbers'),
        ('f"{number}: {line}"', 'the number, a colon and a space, then the line'),
    ],
    "pt-regex-find-ipv4": [
        ('r"\\d{1,3}\\.\\d{1,3}\\.\\d{1,3}\\.\\d{1,3}"', 'four runs of one to three digits, dot-separated — and a bare `.` means any character, so the dots need escaping'),
        ('re.findall(pattern, text)', 'every stretch of the text that matches'),
    ],
    "pt-time-fields": [
        ('"%Y-%m-%d %H:%M:%S"', 'a four-digit year, month and day, then 24-hour time — matching the punctuation exactly'),
        ('moment.hour, moment.minute, moment.second', 'the time of day, in three pieces'),
    ],
    "py-cmp-to-key-guided": [
        ('cmp_to_key(compare)', 'Turn the two-argument comparator into a sort key.'),
        ('len(a) - len(b)', 'negative when a is the shorter of the two, which is what puts it first'),
    ],
    "py-counter-guided": [
        ('Counter(text)', 'Counter counts whatever you iterate. Hand it the text.'),
        ('dict(counts)', 'the tally as an ordinary dict'),
    ],
    "py-dataclass-guided": [
        ('item.price * item.qty', 'What one line of the receipt costs.'),
        ('[Item(*row) for row in rows]', 'one Item per row, with the row spread into its fields'),
    ],
    "py-defaultdict-guided": [
        ('defaultdict(list)', 'A dict whose missing values are born as empty lists.'),
        ('groups[word[0]].append(word)', 'file this word under its first letter'),
    ],
    "py-deque-guided": [
        ('line.popleft()', 'Take the person at the FRONT of the line.'),
        ('deque(names)', 'a queue made out of the names'),
    ],
    "py-enum-guided": [
        ('Level[floor].value', 'The number behind the member named by `floor`.'),
        ('Level[name].value >= cutoff', 'this level is at least as loud as the cutoff'),
    ],
    "py-heapq-guided": [
        ('heapq.heappush(heap, value)', 'Put this value into the heap, keeping the heap a heap.'),
        ('heapq.heappop(heap)', 'the smallest value still in the heap'),
    ],
    "py-lru-cache-guided": [
        ('@lru_cache(maxsize=None)', 'Remember every result this function has already computed.'),
        ('go(k - 1) + go(k - 2)', 'the two smaller answers, added together'),
    ],
    "py-namedtuple-guided": [
        ('point.x', 'Ask each point for its x by name, not by index.'),
        ('[Point(*row) for row in rows]', 'one Point per row, with the row spread into its fields'),
    ],
    "py-ordereddict-guided": [
        ('cache.move_to_end(key)', 'Mark this key as the most recently used one.'),
        ('key in cache', 'only touch keys the cache actually holds'),
    ],
    "py-partial-guided": [
        ('partial(multiply, factor)', 'multiply, with its FIRST argument already set to factor.'),
        ('a * b', 'the two numbers multiplied'),
    ],
    "sc-climb-stairs": [
        ('cur, prev + cur', 'shift the window forward: the new total is the sum of the two before it'),
        ('max(n, 1)', 'one way to climb zero or one step, two ways to climb two'),
    ],
    "sc-count-frequency": [
        ('counts.get(item, 0) + 1', "this item's running count, treating 'never seen' as zero, plus one"),
        ('counts = {}', 'an empty tally, before anything has been counted'),
    ],
    "sc-palindrome-ends": [
        ('s[left] != s[right]', 'the two mirrored characters disagree'),
        ('left < right', 'keep going while the two ends have not met'),
    ],
    "sc-reverse-words": [
        ('" ".join(reversed(words))', 'stitch the words back together, last to first, one space between'),
        ('text.split()', 'the text cut into words on whitespace'),
    ],
    "so-bt-binary-strings": [
        ('prefix + "1"', 'the other branch: this prefix with a one on the end'),
        ('len(prefix) == n', 'the prefix is now as long as it needs to be'),
    ],
    "so-greedy-cookies": [
        ('cookies[j] >= kids[i]', 'is this cookie big enough?'),
        ('sorted(greed)', 'the children, hungriest last'),
    ],
    "so-greedy-us-coins": [
        ('amount // coin', 'how many of this coin fit?'),
        ('amount %= coin', 'what is still owed after those coins'),
    ],
    "so-math-fizzbuzz": [
        ('i % 5 == 0', 'divisible by five as well'),
        ('i % 3 == 0', 'divisible by three'),
    ],
    "so-math-gcd": [
        ('a % b', "the remainder takes b's place"),
        ('abs(a), abs(b)', 'both of them made positive; a minus sign does not change the divisor'),
    ],
    "so-sort-tally": [
        ('counts[value] += 1', 'one more sighting of this value'),
        ('[0] * (top + 1)', 'one slot for every value from zero up to and including top'),
    ],
    "so-topo-indegree": [
        ('counts[target] += 1', 'one more arrow lands on `target`'),
        ('[0] * n', 'one slot per node, all starting at nothing'),
    ],
    "so-uf-find": [
        ('parent[x]', 'step up one level', 2),
        ('return x', 'the root you finally stopped on'),
    ],

    # -----------------------------------------------------------------
    # SPANS THAT HANDED THE ANSWER OVER, RE-DECLARED ON THE IDEA.
    # -----------------------------------------------------------------
    #
    # §4 says never a parameter name the body already uses and never a literal
    # the problem statement already hands over. The onboarding block shipped
    # both, under the GUIDED exemption, and the exemption does not stretch this
    # far: `ob-say-hello` blanked `name` out of `def greet(__BLANK__):` with
    # `message = "Hello, " + name` printed on the line below it, so the answer
    # was visible from the blank and the problem's own lesson — print is not
    # return — was handed over whole. Each of these moves to the line that
    # carries the idea. `ob-dict-store` moves for a second reason as well: its
    # `price` span matched inside `prices` (see `scaffold._boundary_clean`),
    # and the body is where that span belonged in the first place.
    "ob-say-hello": [
        ("return message",
         "hand the message back to the caller, which is not the same as printing it"),
        ('"Hello, " + name', "the greeting with the name stuck on the end"),
    ],
    "ob-two-arguments": [
        ("width * height", "the two measurements multiplied together"),
    ],
    "ob-repeat-text": [
        ("out + text", "what the answer looks like with one more copy on the end"),
        ("range(times)", "the loop that goes round once for every copy"),
    ],
    "ob-dict-store": [
        ("prices[item] = price", "file this price under this item's name"),
        ("return prices", "hand the updated book back"),
    ],
    "ob-bigger": [
        ("a > b", "a is the larger of the two"),
        ("return b", "the one to hand back when the test came out false"),
    ],
    "ob-comprehension-first": [
        ("value * 2", "twice each number — the expression comes before the `for`"),
    ],
}


def declarations() -> dict:
    """Every declaration, as {problem_id: [(target, gloss[, line]), ...]}."""
    out: dict = {}
    for table in (GUIDED, TUTORIAL, EASY, MEDIUM):
        out.update(table)
    return out


def apply(problems) -> int:
    """Attach `scaffold_spans` to every problem that has a declaration.

    Two sources, one field:

    1. DERIVED — a problem that already ships a `__BLANK__` starter is read back
       into a declaration by `scaffold.derive_spans`. That read is itself the
       check: a starter which is not the canonical solution with spans struck
       out raises here rather than shipping.
    2. DECLARED — the tables above, resolved against the canonical solution by
       `scaffold.resolve_targets`, which raises on a target that has gone stale.

    Nothing is created, so lineage and the sealed hold-out see exactly the input
    they saw before this ran.
    """
    from .. import scaffold

    declared = declarations()
    attached = 0
    for problem in problems:
        if getattr(problem, "sealed", False):
            # A sealed problem is never served by the teaching side at any rung,
            # so a declaration on it is inert — and an inert declaration is the
            # kind of thing that later gets "tidied up" into a served one. It is
            # simpler to be able to say, and to test, that the hold-out carries
            # no scaffolding at all.
            problem.scaffold_spans = []
            continue
        pairs = declared.get(problem.id)
        if pairs:
            problem.scaffold_spans = scaffold.resolve_targets(
                problem.canonical_solution, pairs)
            attached += 1
        elif scaffold.MARKER in (problem.starter_code or ""):
            problem.scaffold_spans = scaffold.derive_spans(problem)
            attached += 1
        # A blank frozen into a starter that is not a MISSING_RUNE is mis-filed:
        # the encounter promises a blank screen and hands over a scaffold. The
        # declaration is now the place a scaffold lives, so the starter gets its
        # blank screen back. `validate._verify_scaffold` refuses any that are
        # left, which is the check that would have caught `pt-class-latest`
        # three encounter kinds ago.
        if (scaffold.MARKER in (problem.starter_code or "")
                and problem.encounter_kind != "MISSING_RUNE"):
            problem.starter_code = scaffold.skeleton(problem)
    return attached
