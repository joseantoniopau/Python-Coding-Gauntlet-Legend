"""Matrix Citadel and Graph Wastes. Grids you walk and nodes you traverse."""
from __future__ import annotations

from collections import deque

from ._base import code_problem

Q = {"PRACTICAL": 3.0, "GENERAL_SWE": 2.5, "SECURITY_ENGINEERING": 1.5}
QS = {"PRACTICAL": 1.0, "GENERAL_SWE": 1.0, "SECURITY_ENGINEERING": 3.0}
VIZ_M = {"type": "matrix", "caption": "Rows and columns, index discipline."}
VIZ_BFS = {"type": "bfs", "caption": "A wave of light expands ring by ring."}
VIZ_DFS = {"type": "dfs", "caption": "One path, deeply, then visibly back out."}


def _rotate(matrix):
    n = len(matrix)
    for r in range(n):
        for c in range(r + 1, n):
            matrix[r][c], matrix[c][r] = matrix[c][r], matrix[r][c]
    for row in matrix:
        row.reverse()
    return matrix


def _spiral(matrix):
    if not matrix or not matrix[0]:
        return []
    out = []
    top, bottom = 0, len(matrix) - 1
    left, right = 0, len(matrix[0]) - 1
    while top <= bottom and left <= right:
        for c in range(left, right + 1):
            out.append(matrix[top][c])
        top += 1
        for r in range(top, bottom + 1):
            out.append(matrix[r][right])
        right -= 1
        if top <= bottom:
            for c in range(right, left - 1, -1):
                out.append(matrix[bottom][c])
            bottom -= 1
        if left <= right:
            for r in range(bottom, top - 1, -1):
                out.append(matrix[r][left])
            left += 1
    return out


def _transpose(matrix):
    return [list(row) for row in zip(*matrix)] if matrix else []


def _set_zeroes(matrix):
    if not matrix or not matrix[0]:
        return matrix
    rows = {r for r, row in enumerate(matrix) for v in row if v == 0}
    cols = {c for row in matrix for c, v in enumerate(row) if v == 0}
    for r, row in enumerate(matrix):
        for c in range(len(row)):
            if r in rows or c in cols:
                row[c] = 0
    return matrix


def _diagonal_sum(matrix):
    n = len(matrix)
    total = sum(matrix[i][i] for i in range(n))
    total += sum(matrix[i][n - 1 - i] for i in range(n))
    if n % 2:
        total -= matrix[n // 2][n // 2]
    return total


def _count_islands(grid):
    if not grid or not grid[0]:
        return 0
    rows, cols = len(grid), len(grid[0])
    seen = set()
    count = 0
    for r in range(rows):
        for c in range(cols):
            if grid[r][c] != 1 or (r, c) in seen:
                continue
            count += 1
            stack = [(r, c)]
            seen.add((r, c))
            while stack:
                cr, cc = stack.pop()
                for nr, nc in ((cr+1, cc), (cr-1, cc), (cr, cc+1), (cr, cc-1)):
                    if 0 <= nr < rows and 0 <= nc < cols \
                            and grid[nr][nc] == 1 and (nr, nc) not in seen:
                        seen.add((nr, nc))
                        stack.append((nr, nc))
    return count


def _shortest_path(grid):
    if not grid or not grid[0] or grid[0][0] == 1:
        return -1
    rows, cols = len(grid), len(grid[0])
    if rows == 1 and cols == 1:
        return 1
    queue = deque([(0, 0, 1)])
    seen = {(0, 0)}
    while queue:
        r, c, dist = queue.popleft()
        for nr, nc in ((r+1, c), (r-1, c), (r, c+1), (r, c-1)):
            if 0 <= nr < rows and 0 <= nc < cols \
                    and grid[nr][nc] == 0 and (nr, nc) not in seen:
                if nr == rows - 1 and nc == cols - 1:
                    return dist + 1
                seen.add((nr, nc))
                queue.append((nr, nc, dist + 1))
    return -1


def _rotting(grid):
    rows, cols = len(grid), len(grid[0]) if grid else 0
    queue = deque()
    fresh = 0
    for r in range(rows):
        for c in range(cols):
            if grid[r][c] == 2:
                queue.append((r, c))
            elif grid[r][c] == 1:
                fresh += 1
    if not fresh:
        return 0
    minutes = 0
    while queue and fresh:
        minutes += 1
        for _ in range(len(queue)):
            r, c = queue.popleft()
            for nr, nc in ((r+1, c), (r-1, c), (r, c+1), (r, c-1)):
                if 0 <= nr < rows and 0 <= nc < cols and grid[nr][nc] == 1:
                    grid[nr][nc] = 2
                    fresh -= 1
                    queue.append((nr, nc))
    return -1 if fresh else minutes


def _flood_fill(grid, sr, sc, colour):
    if not grid or grid[sr][sc] == colour:
        return grid
    start = grid[sr][sc]
    rows, cols = len(grid), len(grid[0])
    stack = [(sr, sc)]
    while stack:
        r, c = stack.pop()
        if 0 <= r < rows and 0 <= c < cols and grid[r][c] == start:
            grid[r][c] = colour
            stack.extend([(r+1, c), (r-1, c), (r, c+1), (r, c-1)])
    return grid


def _max_area(grid):
    if not grid or not grid[0]:
        return 0
    rows, cols = len(grid), len(grid[0])
    seen = set()
    best = 0
    for r in range(rows):
        for c in range(cols):
            if grid[r][c] != 1 or (r, c) in seen:
                continue
            area, stack = 0, [(r, c)]
            seen.add((r, c))
            while stack:
                cr, cc = stack.pop()
                area += 1
                for nr, nc in ((cr+1, cc), (cr-1, cc), (cr, cc+1), (cr, cc-1)):
                    if 0 <= nr < rows and 0 <= nc < cols \
                            and grid[nr][nc] == 1 and (nr, nc) not in seen:
                        seen.add((nr, nc))
                        stack.append((nr, nc))
            best = max(best, area)
    return best


def _bfs_order(graph, start):
    seen, out, queue = {start}, [], deque([start])
    while queue:
        node = queue.popleft()
        out.append(node)
        for nxt in graph.get(node, []):
            if nxt not in seen:
                seen.add(nxt)
                queue.append(nxt)
    return out


def _dfs_order(graph, start):
    seen, out = set(), []

    def walk(node):
        if node in seen:
            return
        seen.add(node)
        out.append(node)
        for nxt in graph.get(node, []):
            walk(nxt)

    walk(start)
    return out


def _shortest_hops(graph, start, goal):
    if start == goal:
        return 0
    seen, queue = {start}, deque([(start, 0)])
    while queue:
        node, dist = queue.popleft()
        for nxt in graph.get(node, []):
            if nxt == goal:
                return dist + 1
            if nxt not in seen:
                seen.add(nxt)
                queue.append((nxt, dist + 1))
    return -1


def _connected_components(graph):
    seen, groups = set(), []
    for node in sorted(graph):
        if node in seen:
            continue
        group, stack = [], [node]
        seen.add(node)
        while stack:
            cur = stack.pop()
            group.append(cur)
            for nxt in graph.get(cur, []):
                if nxt not in seen:
                    seen.add(nxt)
                    stack.append(nxt)
        groups.append(sorted(group))
    return sorted(groups)


def _has_cycle_directed(graph):
    WHITE, GREY, BLACK = 0, 1, 2
    colour = {node: WHITE for node in graph}
    for node in graph:
        for nxt in graph[node]:
            colour.setdefault(nxt, WHITE)

    def walk(node):
        colour[node] = GREY
        for nxt in graph.get(node, []):
            if colour[nxt] == GREY:
                return True
            if colour[nxt] == WHITE and walk(nxt):
                return True
        colour[node] = BLACK
        return False

    return any(colour[n] == WHITE and walk(n) for n in list(colour))


def _topo_order(graph):
    indegree = {n: 0 for n in graph}
    for node in graph:
        for nxt in graph[node]:
            indegree.setdefault(nxt, 0)
            indegree[nxt] += 1
    queue = deque(sorted(n for n, d in indegree.items() if d == 0))
    out = []
    while queue:
        node = queue.popleft()
        out.append(node)
        for nxt in sorted(graph.get(node, [])):
            indegree[nxt] -= 1
            if indegree[nxt] == 0:
                queue.append(nxt)
    return out if len(out) == len(indegree) else []


def _lateral_paths(graph, start, goal):
    out = []

    def walk(node, path, seen):
        if node == goal:
            out.append(list(path))
            return
        for nxt in sorted(graph.get(node, [])):
            if nxt in seen:
                continue
            seen.add(nxt)
            path.append(nxt)
            walk(nxt, path, seen)
            path.pop()
            seen.discard(nxt)

    walk(start, [start], {start})
    return out


def _infection_spread(grid, minutes):
    rows, cols = len(grid), len(grid[0]) if grid else 0
    queue = deque((r, c) for r in range(rows) for c in range(cols) if grid[r][c] == 2)
    for _ in range(minutes):
        if not queue:
            break
        for _ in range(len(queue)):
            r, c = queue.popleft()
            for nr, nc in ((r+1, c), (r-1, c), (r, c+1), (r, c-1)):
                if 0 <= nr < rows and 0 <= nc < cols and grid[nr][nc] == 1:
                    grid[nr][nc] = 2
                    queue.append((nr, nc))
    return sum(row.count(2) for row in grid)


GRID = [[1, 1, 0, 0], [1, 0, 0, 1], [0, 0, 1, 1], [0, 0, 0, 0]]
GRAPH = {"a": ["b", "c"], "b": ["d"], "c": ["d"], "d": []}


def build() -> list:
    P: list = []

    P.append(code_problem(
        id="mx-rotate", title="The Matrix Golem", realm="matrix_citadel",
        pattern="MATRIX", difficulty="MEDIUM", family="matrix_transform", boss=True,
        profile_weight=Q, viz=VIZ_M,
        source_type="REPORTED_INTERVIEW", year="reported pattern",
        provenance="In-place matrix rotation is a repeatedly reported screen archetype.",
        statement="""
            Rotate the `n x n` matrix 90 degrees clockwise **in place** and return it.

            The Golem is immune to solutions that allocate a second matrix.
        """,
        fn_name="rotate", params="matrix", reference=_rotate,
        canonical="""
            def rotate(matrix):
                n = len(matrix)
                for r in range(n):                       # transpose across the diagonal
                    for c in range(r + 1, n):            # start at r+1, not 0
                        matrix[r][c], matrix[c][r] = matrix[c][r], matrix[r][c]
                for row in matrix:                       # then mirror each row
                    row.reverse()
                return matrix
        """,
        visible=[("3x3", [[[1, 2, 3], [4, 5, 6], [7, 8, 9]]]),
                 ("2x2", [[[1, 2], [3, 4]]])],
        hidden=[("4x4", [[[1, 2, 3, 4], [5, 6, 7, 8], [9, 10, 11, 12], [13, 14, 15, 16]]]),
                ("negatives", [[[-1, -2], [-3, -4]]]),
                ("identical", [[[7, 7], [7, 7]]])],
        edges=[("single", [[[1]]]), ("empty", [[]])],
        time_complexity="O(n^2)", space_complexity="O(1)",
        failures=["Transposing over the full range swaps every pair twice, undoing itself",
                  "Building a new matrix — correct, but not in place",
                  "Reversing columns instead of rows gives a counter-clockwise rotation"],
        nudge="A clockwise rotation is a transpose followed by a horizontal mirror. "
              "Both steps are in place.",
        visual="Flip the grid across its main diagonal, then flip it left-to-right.",
        pseudocode="""
            for r in range(n):
                for c in range(r+1, n):        # upper triangle ONLY
                    swap matrix[r][c], matrix[c][r]
            for each row: row.reverse()
        """,
        tags=["core", "practical", "boss"],
    ))

    P.append(code_problem(
        id="mx-spiral", title="The Winding Descent", realm="matrix_citadel",
        pattern="MATRIX", difficulty="MEDIUM", family="matrix_traverse",
        profile_weight=Q, viz=VIZ_M,
        statement="""
            Return every value of the matrix in spiral order: right along the top, down
            the right side, left along the bottom, up the left side, then inward.

            The matrix need not be square.
        """,
        fn_name="spiral_order", params="matrix", reference=_spiral,
        canonical="""
            def spiral_order(matrix):
                if not matrix or not matrix[0]:
                    return []
                out = []
                top, bottom = 0, len(matrix) - 1
                left, right = 0, len(matrix[0]) - 1
                while top <= bottom and left <= right:
                    for c in range(left, right + 1):
                        out.append(matrix[top][c])
                    top += 1
                    for r in range(top, bottom + 1):
                        out.append(matrix[r][right])
                    right -= 1
                    if top <= bottom:                 # guard: the row may be exhausted
                        for c in range(right, left - 1, -1):
                            out.append(matrix[bottom][c])
                        bottom -= 1
                    if left <= right:                 # guard: the column may be exhausted
                        for r in range(bottom, top - 1, -1):
                            out.append(matrix[r][left])
                        left += 1
                return out
        """,
        visible=[("3x3", [[[1, 2, 3], [4, 5, 6], [7, 8, 9]]]),
                 ("3x4", [[[1, 2, 3, 4], [5, 6, 7, 8], [9, 10, 11, 12]]])],
        hidden=[("single row", [[[1, 2, 3]]]), ("single column", [[[1], [2], [3]]]),
                ("2x2", [[[1, 2], [3, 4]]]),
                ("5x1", [[[1], [2], [3], [4], [5]]])],
        edges=[("empty", [[]]), ("single cell", [[[9]]])],
        time_complexity="O(rows·cols)", space_complexity="O(1) extra",
        failures=["Emitting the middle row twice when only one row remains",
                  "Emitting the middle column twice when only one column remains",
                  "Not handling non-square input"],
        nudge="After the top row and right column, you must re-check whether a row or "
              "column still exists before walking it backwards.",
        visual="Four shrinking walls. Each pass moves one wall inward.",
        pseudocode="""
            while top <= bottom and left <= right:
                walk top row right;    top += 1
                walk right col down;   right -= 1
                if top <= bottom: walk bottom row left;  bottom -= 1
                if left <= right: walk left col up;      left += 1
        """,
        tags=["core", "practical"],
    ))

    P.append(code_problem(
        id="mx-transpose", title="Turning the Tapestry", realm="matrix_citadel",
        pattern="MATRIX", difficulty="TUTORIAL", family="matrix_transform",
        profile_weight=Q, viz=VIZ_M,
        statement="Return the transpose of the matrix — rows become columns.",
        fn_name="transpose", params="matrix", reference=_transpose,
        canonical="""
            def transpose(matrix):
                return [list(row) for row in zip(*matrix)] if matrix else []
        """,
        visible=[("square", [[[1, 2], [3, 4]]]), ("wide", [[[1, 2, 3], [4, 5, 6]]])],
        hidden=[("tall", [[[1], [2], [3]]]), ("single row", [[[1, 2, 3]]])],
        edges=[("empty", [[]])],
        time_complexity="O(rows·cols)", space_complexity="O(rows·cols)",
        failures=["zip returns tuples, not lists", "Assuming the matrix is square"],
        nudge="`zip(*matrix)` unpacks the rows and pairs them column-wise.",
        visual="Rows tip over into columns.",
        pseudocode="[list(row) for row in zip(*matrix)]",
        tags=["tutorial", "python"],
    ))

    P.append(code_problem(
        id="mx-set-zeroes", title="The Nullifying Sigil", realm="matrix_citadel",
        pattern="MATRIX", difficulty="MEDIUM", family="matrix_transform",
        profile_weight=Q, viz=VIZ_M,
        statement="""
            If any cell is `0`, set its entire row and column to `0`. Modify the matrix in
            place and return it.

            The trap: doing this naively as you scan will cascade.
        """,
        fn_name="set_zeroes", params="matrix", reference=_set_zeroes,
        canonical="""
            def set_zeroes(matrix):
                if not matrix or not matrix[0]:
                    return matrix
                # record FIRST, mutate second, or your own zeroes trigger more zeroes
                rows = {r for r, row in enumerate(matrix) for v in row if v == 0}
                cols = {c for row in matrix for c, v in enumerate(row) if v == 0}
                for r, row in enumerate(matrix):
                    for c in range(len(row)):
                        if r in rows or c in cols:
                            row[c] = 0
                return matrix
        """,
        visible=[("one zero", [[[1, 1, 1], [1, 0, 1], [1, 1, 1]]]),
                 ("two zeroes", [[[0, 1, 2, 0], [3, 4, 5, 2], [1, 3, 1, 5]]])],
        hidden=[("all zero", [[[0, 0], [0, 0]]]), ("no zero", [[[1, 2], [3, 4]]]),
                ("edge zero", [[[0, 1], [1, 1]]])],
        edges=[("single zero cell", [[[0]]]), ("empty", [[]])],
        time_complexity="O(rows·cols)", space_complexity="O(rows + cols)",
        failures=["Zeroing during the scan cascades — every new zero triggers more",
                  "Recording only the first zero"],
        nudge="Two phases. Find every zero first, then paint.",
        visual="Mark the doomed rows and columns; only then let the nullification run.",
        pseudocode="collect zero rows and cols; then blank every cell in them",
        tags=["core"],
    ))

    P.append(code_problem(
        id="mx-diagonal-sum", title="Crossing the Citadel", realm="matrix_citadel",
        pattern="MATRIX", difficulty="EASY", family="matrix_traverse",
        profile_weight=Q, viz=VIZ_M,
        statement="""
            Return the sum of both diagonals of an `n x n` matrix. The centre cell of an
            odd-sized matrix belongs to both diagonals but is counted only once.
        """,
        fn_name="diagonal_sum", params="matrix", reference=_diagonal_sum,
        canonical="""
            def diagonal_sum(matrix):
                n = len(matrix)
                total = sum(matrix[i][i] for i in range(n))
                total += sum(matrix[i][n - 1 - i] for i in range(n))
                if n % 2:
                    total -= matrix[n // 2][n // 2]   # counted twice
                return total
        """,
        visible=[("3x3", [[[1, 2, 3], [4, 5, 6], [7, 8, 9]]]),
                 ("2x2", [[[1, 2], [3, 4]]])],
        hidden=[("4x4", [[[1, 1, 1, 1]] * 4]), ("negatives", [[[-1, -2], [-3, -4]]]),
                ("5x5", [[[1] * 5] * 5])],
        edges=[("single", [[[7]]])],
        time_complexity="O(n)", space_complexity="O(1)",
        failures=["Double-counting the centre of an odd matrix",
                  "Getting the anti-diagonal index backwards"],
        nudge="Anti-diagonal index is `n - 1 - i`. Odd sizes share one cell.",
        visual="Two lines crossing at the centre stone.",
        pseudocode="sum m[i][i] + sum m[i][n-1-i]; subtract the centre when n is odd",
        tags=["core"],
    ))

    P.append(code_problem(
        id="gr-count-islands", title="The Sundered Isles", realm="graph_wastes",
        pattern="DFS", difficulty="MEDIUM", family="grid_traverse",
        secondary=["BFS", "MATRIX"], profile_weight=Q, viz=VIZ_DFS,
        source_type="REPORTED_INTERVIEW", year="reported pattern",
        provenance="Grid connected-components is a repeatedly reported archetype.",
        statement="""
            `grid` holds `1` for land and `0` for water. Return the number of islands.
            Cells connect only horizontally and vertically, never diagonally.
        """,
        fn_name="count_islands", params="grid", reference=_count_islands,
        canonical="""
            def count_islands(grid):
                if not grid or not grid[0]:
                    return 0
                rows, cols = len(grid), len(grid[0])
                seen = set()
                count = 0
                for r in range(rows):
                    for c in range(cols):
                        if grid[r][c] != 1 or (r, c) in seen:
                            continue
                        count += 1
                        stack = [(r, c)]
                        seen.add((r, c))
                        while stack:                       # flood the whole island
                            cr, cc = stack.pop()
                            for nr, nc in ((cr+1, cc), (cr-1, cc), (cr, cc+1), (cr, cc-1)):
                                if (0 <= nr < rows and 0 <= nc < cols
                                        and grid[nr][nc] == 1 and (nr, nc) not in seen):
                                    seen.add((nr, nc))
                                    stack.append((nr, nc))
                return count
        """,
        visible=[("three islands", [GRID]), ("one island", [[[1, 1], [1, 1]]])],
        hidden=[("all water", [[[0, 0], [0, 0]]]), ("diagonal is not connected",
                                                    [[[1, 0], [0, 1]]]),
                ("single row", [[[1, 0, 1]]]), ("large blob", [[[1] * 5] * 5])],
        edges=[("empty", [[]]), ("single land", [[[1]]])],
        perf=[("120x120", [[[1 if (r + c) % 3 else 0 for c in range(120)]
                            for r in range(120)]])],
        time_complexity="O(rows·cols)", space_complexity="O(rows·cols)",
        failures=["Marking a cell visited only when you pop it, so it enters the stack "
                  "many times and the search blows up",
                  "Counting diagonal neighbours",
                  "Recursing on a large grid and hitting the recursion limit"],
        nudge="Every unvisited land cell starts exactly one island. Then drown the whole "
              "island so it is never counted again.",
        visual="An explorer lands on new ground and walks every connected tile before "
               "returning to the survey.",
        pseudocode="""
            for each cell:
                if land and unseen:
                    count += 1
                    flood-fill (BFS or DFS) marking every connected land cell
        """,
        variants=["gr-max-island-area", "sec-infection-spread"],
        tags=["core", "practical"],
    ))

    P.append(code_problem(
        id="gr-max-island-area", title="Greatest of the Isles", realm="graph_wastes",
        pattern="DFS", difficulty="MEDIUM", family="grid_traverse",
        source_type="GENERATED_VARIANT", profile_weight=Q, viz=VIZ_DFS,
        statement="Return the size in cells of the largest island, or `0` if there is none.",
        fn_name="max_island_area", params="grid", reference=_max_area,
        canonical="""
            def max_island_area(grid):
                if not grid or not grid[0]:
                    return 0
                rows, cols = len(grid), len(grid[0])
                seen = set()
                best = 0
                for r in range(rows):
                    for c in range(cols):
                        if grid[r][c] != 1 or (r, c) in seen:
                            continue
                        area, stack = 0, [(r, c)]
                        seen.add((r, c))
                        while stack:
                            cr, cc = stack.pop()
                            area += 1
                            for nr, nc in ((cr+1, cc), (cr-1, cc), (cr, cc+1), (cr, cc-1)):
                                if (0 <= nr < rows and 0 <= nc < cols
                                        and grid[nr][nc] == 1 and (nr, nc) not in seen):
                                    seen.add((nr, nc))
                                    stack.append((nr, nc))
                        best = max(best, area)
                return best
        """,
        visible=[("mixed", [GRID]), ("full", [[[1, 1], [1, 1]]])],
        hidden=[("all water", [[[0]]]), ("two equal", [[[1, 0, 1]]]),
                ("snake", [[[1, 1, 0], [0, 1, 0], [0, 1, 1]]])],
        edges=[("empty", [[]])],
        time_complexity="O(rows·cols)", space_complexity="O(rows·cols)",
        failures=["Counting a cell more than once by adding to area on push and on pop"],
        nudge="Same flood fill; count as you drain the stack.",
        visual="Same survey, but each island is weighed.",
        pseudocode="flood fill, incrementing area per popped cell; track the max",
        prerequisites=["gr-count-islands"], tags=["variant"],
    ))

    P.append(code_problem(
        id="gr-shortest-path-grid", title="The Queue Lance", realm="graph_wastes",
        pattern="BFS", difficulty="MEDIUM", family="grid_bfs",
        secondary=["QUEUE", "MATRIX"], profile_weight=Q, viz=VIZ_BFS,
        statement="""
            `grid` holds `0` for open and `1` for blocked. Return the number of cells on
            the shortest path from the top-left to the bottom-right, moving only up, down,
            left or right. Return `-1` if no path exists.

            A single open cell grid has a path of length `1`.
        """,
        fn_name="shortest_path", params="grid", reference=_shortest_path,
        canonical="""
            def shortest_path(grid):
                from collections import deque
                if not grid or not grid[0] or grid[0][0] == 1:
                    return -1
                rows, cols = len(grid), len(grid[0])
                if rows == 1 and cols == 1:
                    return 1
                queue = deque([(0, 0, 1)])
                seen = {(0, 0)}
                while queue:
                    r, c, dist = queue.popleft()
                    for nr, nc in ((r+1, c), (r-1, c), (r, c+1), (r, c-1)):
                        if (0 <= nr < rows and 0 <= nc < cols
                                and grid[nr][nc] == 0 and (nr, nc) not in seen):
                            if nr == rows - 1 and nc == cols - 1:
                                return dist + 1     # BFS: first arrival IS shortest
                            seen.add((nr, nc))
                            queue.append((nr, nc, dist + 1))
                return -1
        """,
        visible=[("open path", [[[0, 0, 0], [1, 1, 0], [0, 0, 0]]]),
                 ("blocked", [[[0, 1], [1, 0]]])],
        hidden=[("start blocked", [[[1, 0], [0, 0]]]),
                ("straight line", [[[0, 0, 0, 0]]]),
                ("maze", [[[0, 0, 1], [1, 0, 1], [1, 0, 0]]])],
        edges=[("single open", [[[0]]]), ("single blocked", [[[1]]]), ("empty", [[]])],
        perf=[("100x100 open", [[[0] * 100 for _ in range(100)]])],
        time_complexity="O(rows·cols)", space_complexity="O(rows·cols)",
        failures=["Using DFS, which finds *a* path but not the shortest",
                  "Marking cells visited on pop instead of on push, so the queue floods",
                  "Forgetting the 1x1 case"],
        nudge="BFS reaches every cell in increasing distance order. The first time you "
              "touch the goal, you are done — no comparison needed.",
        visual="A ring of light expands from the entrance one step at a time. The instant "
               "it touches the exit, that ring's radius is the answer.",
        pseudocode="""
            queue = [(start, 1)]; seen = {start}
            while queue:
                pop; for each open unseen neighbour:
                    if it is the goal: return dist + 1
                    mark seen; push with dist + 1
        """,
        tags=["core", "practical"],
    ))

    P.append(code_problem(
        id="gr-rotting", title="The Spreading Blight", realm="graph_wastes",
        pattern="BFS", difficulty="MEDIUM", family="grid_bfs", profile_weight=Q,
        viz=VIZ_BFS,
        statement="""
            `0` is empty, `1` is fresh, `2` is rotten. Each minute, every rotten cell rots
            its four orthogonal fresh neighbours. Return the minutes until nothing fresh
            remains, or `-1` if some fresh cell can never rot. Return `0` if nothing is
            fresh to begin with.
        """,
        fn_name="minutes_to_rot", params="grid", reference=_rotting,
        canonical="""
            def minutes_to_rot(grid):
                from collections import deque
                rows, cols = len(grid), len(grid[0]) if grid else 0
                queue = deque()
                fresh = 0
                for r in range(rows):
                    for c in range(cols):
                        if grid[r][c] == 2:
                            queue.append((r, c))
                        elif grid[r][c] == 1:
                            fresh += 1
                if not fresh:
                    return 0
                minutes = 0
                while queue and fresh:
                    minutes += 1
                    for _ in range(len(queue)):      # one whole minute per level
                        r, c = queue.popleft()
                        for nr, nc in ((r+1, c), (r-1, c), (r, c+1), (r, c-1)):
                            if 0 <= nr < rows and 0 <= nc < cols and grid[nr][nc] == 1:
                                grid[nr][nc] = 2
                                fresh -= 1
                                queue.append((nr, nc))
                return -1 if fresh else minutes
        """,
        visible=[("spreads", [[[2, 1, 1], [1, 1, 0], [0, 1, 1]]]),
                 ("unreachable", [[[2, 1, 1], [0, 1, 1], [1, 0, 1]]])],
        hidden=[("nothing fresh", [[[0, 2]]]), ("all fresh no source", [[[1, 1]]]),
                ("already rotten", [[[2, 2]]]), ("single fresh next to rot", [[[2, 1]]])],
        edges=[("empty", [[]]), ("all empty cells", [[[0, 0]]])],
        time_complexity="O(rows·cols)", space_complexity="O(rows·cols)",
        failures=["Counting a minute for the initial rotten cells",
                  "Not tracking fresh count, so unreachable cells go unnoticed",
                  "Processing the queue one cell at a time instead of one level at a time"],
        nudge="Multi-source BFS. Every initially rotten cell starts in the queue together, "
              "and one queue level equals one minute.",
        visual="Many waves start at once and expand together, ring by ring.",
        pseudocode="seed queue with all rotten; per level: minutes += 1, rot neighbours",
        prerequisites=["gr-shortest-path-grid"], tags=["core"],
    ))

    P.append(code_problem(
        id="gr-flood-fill", title="Recolouring the Wastes", realm="graph_wastes",
        pattern="DFS", difficulty="EASY", family="grid_traverse", profile_weight=Q,
        viz=VIZ_DFS,
        statement="""
            Starting at `(sr, sc)`, repaint every orthogonally connected cell of the same
            starting colour to `colour`. Return the grid.
        """,
        fn_name="flood_fill", params="grid, sr, sc, colour", reference=_flood_fill,
        canonical="""
            def flood_fill(grid, sr, sc, colour):
                if not grid or grid[sr][sc] == colour:
                    return grid                 # without this guard you loop forever
                start = grid[sr][sc]
                rows, cols = len(grid), len(grid[0])
                stack = [(sr, sc)]
                while stack:
                    r, c = stack.pop()
                    if 0 <= r < rows and 0 <= c < cols and grid[r][c] == start:
                        grid[r][c] = colour
                        stack.extend([(r+1, c), (r-1, c), (r, c+1), (r, c-1)])
                return grid
        """,
        visible=[("classic", [[[1, 1, 1], [1, 1, 0], [1, 0, 1]], 1, 1, 2]),
                 ("no change", [[[0, 0], [0, 0]], 0, 0, 0])],
        hidden=[("corner", [[[1, 2], [2, 1]], 0, 0, 3]),
                ("whole grid", [[[5, 5], [5, 5]], 1, 1, 9]),
                ("isolated", [[[1, 0, 1]], 0, 0, 7])],
        edges=[("single cell", [[[1]], 0, 0, 2])],
        time_complexity="O(rows·cols)", space_complexity="O(rows·cols)",
        failures=["Infinite loop when the new colour equals the old one",
                  "Repainting cells of a different colour"],
        nudge="Guard the no-op case first, or you will repaint forever.",
        visual="Paint spreads outward through matching tiles only.",
        pseudocode="if same colour: return; else flood every matching connected cell",
        tags=["core"],
    ))

    P.append(code_problem(
        id="gr-bfs-order", title="Rings of the Waste", realm="graph_wastes",
        pattern="BFS", difficulty="EASY", family="graph_traverse", secondary=["QUEUE"],
        profile_weight=Q, viz=VIZ_BFS,
        statement="""
            `graph` maps each node to its neighbour list. Return the nodes in
            breadth-first order from `start`, visiting each node once, taking neighbours
            in the order given.
        """,
        fn_name="bfs_order", params="graph, start", reference=_bfs_order,
        canonical="""
            def bfs_order(graph, start):
                from collections import deque
                seen = {start}
                out = []
                queue = deque([start])
                while queue:
                    node = queue.popleft()
                    out.append(node)
                    for nxt in graph.get(node, []):
                        if nxt not in seen:
                            seen.add(nxt)         # mark on PUSH, not on pop
                            queue.append(nxt)
                return out
        """,
        visible=[("diamond", [GRAPH, "a"]), ("single", [{"a": []}, "a"])],
        hidden=[("cycle", [{"a": ["b"], "b": ["a"]}, "a"]),
                ("disconnected", [{"a": [], "b": []}, "a"]),
                ("chain", [{"a": ["b"], "b": ["c"], "c": []}, "a"])],
        edges=[("missing start key", [{}, "a"])],
        time_complexity="O(V + E)", space_complexity="O(V)",
        failures=["Marking visited on pop, which enqueues duplicates",
                  "Using list.pop(0), which is O(n)",
                  "Crashing when a node has no entry in the dict"],
        nudge="`deque` and a `seen` set. Mark seen the moment you enqueue.",
        visual="A wave expands outward, one ring per level.",
        pseudocode="queue = [start]; seen = {start}; pop, record, enqueue unseen neighbours",
        tags=["core"],
    ))

    P.append(code_problem(
        id="gr-dfs-order", title="Into the Deep Waste", realm="graph_wastes",
        pattern="DFS", difficulty="EASY", family="graph_traverse",
        secondary=["RECURSION"], profile_weight=Q, viz=VIZ_DFS,
        statement="""
            Return the nodes in depth-first pre-order from `start`, following neighbours in
            the order given and never revisiting a node.
        """,
        fn_name="dfs_order", params="graph, start", reference=_dfs_order,
        canonical="""
            def dfs_order(graph, start):
                seen = set()
                out = []

                def walk(node):
                    if node in seen:
                        return
                    seen.add(node)
                    out.append(node)
                    for nxt in graph.get(node, []):
                        walk(nxt)

                walk(start)
                return out
        """,
        visible=[("diamond", [GRAPH, "a"]), ("chain", [{"a": ["b"], "b": ["c"], "c": []}, "a"])],
        hidden=[("cycle", [{"a": ["b"], "b": ["a"]}, "a"]),
                ("branching", [{"a": ["b", "c"], "b": [], "c": []}, "a"]),
                ("self loop", [{"a": ["a", "b"], "b": []}, "a"])],
        edges=[("missing start key", [{}, "a"])],
        time_complexity="O(V + E)", space_complexity="O(V)",
        failures=["No visited set means cycles loop forever",
                  "Recording after recursing gives post-order, not pre-order"],
        nudge="Commit to one path fully before backing out. A `seen` set stops the cycles.",
        visual="An explorer follows one corridor to its end, then visibly backtracks.",
        pseudocode="walk(node): seen -> return; mark; record; walk each neighbour",
        tags=["core"],
    ))

    P.append(code_problem(
        id="gr-shortest-hops", title="The Graph Necromancer", realm="graph_wastes",
        pattern="BFS", difficulty="MEDIUM", family="graph_shortest", boss=True,
        profile_weight=Q, viz=VIZ_BFS,
        statement="""
            Return the fewest edges from `start` to `goal` in an unweighted graph, or `-1`
            if unreachable. `start == goal` is `0` hops.
        """,
        fn_name="shortest_hops", params="graph, start, goal", reference=_shortest_hops,
        canonical="""
            def shortest_hops(graph, start, goal):
                from collections import deque
                if start == goal:
                    return 0
                seen = {start}
                queue = deque([(start, 0)])
                while queue:
                    node, dist = queue.popleft()
                    for nxt in graph.get(node, []):
                        if nxt == goal:
                            return dist + 1
                        if nxt not in seen:
                            seen.add(nxt)
                            queue.append((nxt, dist + 1))
                return -1
        """,
        visible=[("two hops", [GRAPH, "a", "d"]), ("same node", [GRAPH, "a", "a"])],
        hidden=[("unreachable", [{"a": [], "b": []}, "a", "b"]),
                ("long chain", [{"a": ["b"], "b": ["c"], "c": ["d"], "d": []}, "a", "d"]),
                ("cycle", [{"a": ["b"], "b": ["a", "c"], "c": []}, "a", "c"])],
        edges=[("empty graph", [{}, "a", "b"])],
        time_complexity="O(V + E)", space_complexity="O(V)",
        failures=["Using DFS and reporting the first path found",
                  "Not handling start == goal",
                  "Not returning -1 when the goal is unreachable"],
        nudge="BFS visits in distance order. First contact is the answer.",
        visual="Rings expand until one touches the goal.",
        pseudocode="BFS carrying distance; return on first sight of the goal",
        variants=["sec-lateral-paths"], tags=["core", "boss"],
    ))

    P.append(code_problem(
        id="gr-components", title="Islands in the Node-Sea", realm="graph_wastes",
        pattern="DFS", difficulty="MEDIUM", family="graph_traverse", profile_weight=Q,
        viz=VIZ_DFS,
        statement="""
            The graph is undirected and given as an adjacency dict. Return its connected
            components: a sorted list of sorted node lists.
        """,
        fn_name="connected_components", params="graph", reference=_connected_components,
        canonical="""
            def connected_components(graph):
                seen = set()
                groups = []
                for node in sorted(graph):
                    if node in seen:
                        continue
                    group, stack = [], [node]
                    seen.add(node)
                    while stack:
                        cur = stack.pop()
                        group.append(cur)
                        for nxt in graph.get(cur, []):
                            if nxt not in seen:
                                seen.add(nxt)
                                stack.append(nxt)
                    groups.append(sorted(group))
                return sorted(groups)
        """,
        visible=[("two groups", [{"a": ["b"], "b": ["a"], "c": []}]),
                 ("one group", [{"a": ["b"], "b": ["a"]}])],
        hidden=[("isolated", [{"a": [], "b": [], "c": []}]),
                ("chain", [{"a": ["b"], "b": ["a", "c"], "c": ["b"]}]),
                ("star", [{"a": ["b", "c"], "b": ["a"], "c": ["a"]}])],
        edges=[("empty", [{}])],
        time_complexity="O(V + E)", space_complexity="O(V)",
        failures=["Restarting the search from every node without a global visited set",
                  "Forgetting to sort for a deterministic answer"],
        nudge="One outer loop over unvisited nodes; one flood fill each.",
        visual="Each unvisited node begins a new island; the flood claims all of it.",
        pseudocode="for each unseen node: flood fill collecting the whole component",
        prerequisites=["gr-dfs-order"], tags=["core"],
    ))

    P.append(code_problem(
        id="gr-detect-cycle", title="The Looping Curse", realm="graph_wastes",
        pattern="DFS", difficulty="HARD", family="graph_cycle", profile_weight=Q,
        viz=VIZ_DFS, cmp="bool",
        statement="""
            The graph is **directed**. Return `True` if it contains a cycle.

            A node reachable twice by different paths is not a cycle. Only a node that is
            still on the current path counts.
        """,
        fn_name="has_cycle", params="graph", reference=_has_cycle_directed,
        canonical="""
            def has_cycle(graph):
                WHITE, GREY, BLACK = 0, 1, 2      # unseen / on the current path / done
                colour = {node: WHITE for node in graph}
                for node in graph:
                    for nxt in graph[node]:
                        colour.setdefault(nxt, WHITE)

                def walk(node):
                    colour[node] = GREY
                    for nxt in graph.get(node, []):
                        if colour[nxt] == GREY:
                            return True           # back edge to the current path
                        if colour[nxt] == WHITE and walk(nxt):
                            return True
                    colour[node] = BLACK
                    return False

                return any(colour[n] == WHITE and walk(n) for n in list(colour))
        """,
        visible=[("cycle", [{"a": ["b"], "b": ["c"], "c": ["a"]}]), ("dag", [GRAPH])],
        hidden=[("self loop", [{"a": ["a"]}]),
                ("diamond is not a cycle", [{"a": ["b", "c"], "b": ["d"], "c": ["d"], "d": []}]),
                ("disconnected cycle", [{"a": [], "b": ["c"], "c": ["b"]}]),
                ("long chain", [{"a": ["b"], "b": ["c"], "c": []}])],
        edges=[("empty", [{}]), ("single node", [{"a": []}])],
        time_complexity="O(V + E)", space_complexity="O(V)",
        failures=["A plain visited set reports a cycle for any diamond shape",
                  "Not restarting from every unvisited node",
                  "Missing self-loops"],
        nudge="You need three states, not two. 'Seen before' and 'currently on my path' "
              "are different questions.",
        visual="Grey nodes are the corridor you are standing in. Meeting grey means you "
               "walked in a circle. Meeting black just means someone was here before.",
        pseudocode="""
            walk(node): mark GREY
                for each neighbour:
                    GREY  -> cycle
                    WHITE -> recurse
                mark BLACK
        """,
        tags=["hard"],
    ))

    P.append(code_problem(
        id="gr-topo-order", title="The Ordained Sequence", realm="graph_wastes",
        pattern="BFS", difficulty="HARD", family="graph_topo",
        secondary=["QUEUE", "SORTING"], profile_weight=Q,
        statement="""
            The directed graph encodes prerequisites: an edge `u -> v` means `u` must come
            before `v`. Return a valid ordering of every node. Break ties alphabetically
            for a deterministic answer. Return `[]` if no ordering exists.
        """,
        fn_name="topological_order", params="graph", reference=_topo_order,
        canonical="""
            def topological_order(graph):
                from collections import deque
                indegree = {n: 0 for n in graph}
                for node in graph:
                    for nxt in graph[node]:
                        indegree.setdefault(nxt, 0)
                        indegree[nxt] += 1
                queue = deque(sorted(n for n, d in indegree.items() if d == 0))
                out = []
                while queue:
                    node = queue.popleft()
                    out.append(node)
                    for nxt in sorted(graph.get(node, [])):
                        indegree[nxt] -= 1
                        if indegree[nxt] == 0:
                            queue.append(nxt)
                return out if len(out) == len(indegree) else []
        """,
        visible=[("diamond", [GRAPH]), ("chain", [{"a": ["b"], "b": ["c"], "c": []}])],
        hidden=[("cycle has no order", [{"a": ["b"], "b": ["a"]}]),
                ("independent", [{"a": [], "b": []}]),
                ("implicit node", [{"a": ["z"]}])],
        edges=[("empty", [{}])],
        time_complexity="O(V + E)", space_complexity="O(V)",
        failures=["Forgetting nodes that appear only as targets",
                  "Not detecting the cycle by comparing output length to node count"],
        nudge="Repeatedly take a node nothing depends on; removing it may free others.",
        visual="Peel off every node with no incoming arrows, again and again.",
        pseudocode="compute indegrees; queue the zeroes; pop, emit, decrement successors",
        prerequisites=["gr-detect-cycle"], tags=["hard"],
    ))

    P.append(code_problem(
        id="sec-lateral-paths", title="Tracing Lateral Movement", realm="graph_wastes",
        pattern="DFS", difficulty="HARD", family="graph_paths", security=True,
        profile_weight=QS, viz=VIZ_DFS, cmp="exact",
        statement="""
            `graph` maps each host to the hosts it can reach. Return every simple path
            (no host repeated) from `start` to `goal`, each as a list of hosts.

            Explore neighbours in sorted order so your answer is deterministic.
        """,
        fn_name="attack_paths", params="graph, start, goal", reference=_lateral_paths,
        canonical="""
            def attack_paths(graph, start, goal):
                out = []

                def walk(node, path, seen):
                    if node == goal:
                        out.append(list(path))       # copy the trail
                        return
                    for nxt in sorted(graph.get(node, [])):
                        if nxt in seen:
                            continue
                        seen.add(nxt)
                        path.append(nxt)
                        walk(nxt, path, seen)
                        path.pop()                   # undo
                        seen.discard(nxt)            # undo

                walk(start, [start], {start})
                return out
        """,
        visible=[("two paths", [GRAPH, "a", "d"]),
                 ("direct", [{"a": ["b"], "b": []}, "a", "b"])],
        hidden=[("no path", [{"a": [], "b": []}, "a", "b"]),
                ("cycle safe", [{"a": ["b"], "b": ["a", "c"], "c": []}, "a", "c"]),
                ("start is goal", [GRAPH, "a", "a"])],
        edges=[("empty graph", [{}, "a", "b"])],
        time_complexity="O(paths · length)", space_complexity="O(V)",
        failures=["A global visited set that is never undone finds only one path",
                  "Appending the path object instead of a copy",
                  "Infinite recursion on a cycle without per-path tracking"],
        nudge="This is backtracking, not plain DFS: the `seen` set must be undone on the "
              "way back up, or a host visited on one branch blocks every other branch.",
        visual="An explorer marks doors as they pass and unmarks them on the way back, so "
               "each distinct route is discovered independently.",
        pseudocode="mark; recurse; UNMARK. Record a copy at the goal.",
        prerequisites=["gr-dfs-order"], tags=["security", "transfer", "hard"],
    ))

    P.append(code_problem(
        id="sec-infection-spread", title="Segment Infection", realm="matrix_citadel",
        pattern="BFS", difficulty="MEDIUM", family="grid_bfs", security=True,
        profile_weight=QS, viz=VIZ_BFS,
        statement="""
            A network segment is a grid: `0` is an empty slot, `1` is a healthy host, `2`
            is a compromised host. Each minute every compromised host compromises its four
            orthogonal healthy neighbours.

            Return how many hosts are compromised after exactly `minutes` minutes.
        """,
        fn_name="compromised_after", params="grid, minutes", reference=_infection_spread,
        canonical="""
            def compromised_after(grid, minutes):
                from collections import deque
                rows, cols = len(grid), len(grid[0]) if grid else 0
                queue = deque((r, c) for r in range(rows) for c in range(cols)
                              if grid[r][c] == 2)
                for _ in range(minutes):
                    if not queue:
                        break
                    for _ in range(len(queue)):       # exactly one minute per level
                        r, c = queue.popleft()
                        for nr, nc in ((r+1, c), (r-1, c), (r, c+1), (r, c-1)):
                            if 0 <= nr < rows and 0 <= nc < cols and grid[nr][nc] == 1:
                                grid[nr][nc] = 2
                                queue.append((nr, nc))
                return sum(row.count(2) for row in grid)
        """,
        visible=[("one minute", [[[2, 1, 1], [1, 1, 0]], 1]),
                 ("two minutes", [[[2, 1, 1], [1, 1, 0]], 2])],
        hidden=[("zero minutes", [[[2, 1]], 0]), ("no source", [[[1, 1]], 5]),
                ("saturated", [[[2, 2]], 3]),
                ("blocked by empties", [[[2, 0, 1]], 5])],
        edges=[("empty", [[], 3])],
        time_complexity="O(rows·cols)", space_complexity="O(rows·cols)",
        failures=["Not batching by level, so one minute spreads arbitrarily far",
                  "Counting hosts that were already compromised as newly infected"],
        nudge="Level-batched multi-source BFS, capped at a fixed number of rounds.",
        visual="Every compromised host radiates outward together, one ring per minute.",
        pseudocode="seed all sources; repeat `minutes` times: expand exactly one level",
        prerequisites=["gr-rotting"], tags=["security", "transfer"],
    ))

    return P
