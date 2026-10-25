"""
Fair Minesweeper - Logic Solver & Constraint Satisfaction Engine
"""

from typing import List, Tuple, Set, Dict, Optional, Any
from collections import defaultdict
from fair_minesweeper.board import Board, STATE_HIDDEN, STATE_REVEALED, STATE_FLAGGED


class Deduction:
    def __init__(
        self,
        cell: Tuple[int, int],
        is_mine: bool,
        clues: List[Tuple[int, int]],
        explanation: str
    ):
        self.cell = cell
        self.is_mine = is_mine
        self.clues = clues
        self.explanation = explanation

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cell": {"r": self.cell[0], "c": self.cell[1]},
            "is_mine": self.is_mine,
            "clues": [{"r": r, "c": c} for r, c in self.clues],
            "explanation": self.explanation,
        }


class SolverResult:
    def __init__(self):
        self.safe_cells: Set[Tuple[int, int]] = set()
        self.mine_cells: Set[Tuple[int, int]] = set()
        self.ambiguous_cells: Set[Tuple[int, int]] = set()
        self.deductions: Dict[Tuple[int, int], Deduction] = {}

    def add_safe(self, cell: Tuple[int, int], deduction: Optional[Deduction] = None):
        self.safe_cells.add(cell)
        if deduction:
            self.deductions[cell] = deduction

    def add_mine(self, cell: Tuple[int, int], deduction: Optional[Deduction] = None):
        self.mine_cells.add(cell)
        if deduction:
            self.deductions[cell] = deduction


class Solver:
    def __init__(self, board: Board):
        self.board = board

    def solve(self) -> SolverResult:
        result = SolverResult()
        
        # 1. Identify active clues and unrevealed frontier
        clues = self._get_active_clues()
        if not clues:
            # If no active clues (e.g. empty or start), all hidden unflagged are ambiguous
            hidden = self._get_all_hidden_cells()
            result.ambiguous_cells = set(hidden)
            return result

        # 2. Fast Path: Trivial / Direct Deductions
        trivial_found = self._find_trivial_deductions(clues, result)
        if result.safe_cells:
            # If we found guaranteed safe cells trivially, populate remaining frontier and return
            self._populate_ambiguous(clues, result)
            return result

        # 3. Fast Path: Subset Reductions (1-1, 1-2, subset difference)
        self._find_subset_deductions(clues, result)
        if result.safe_cells:
            self._populate_ambiguous(clues, result)
            return result

        # 4. Deep Path: Connected Component CSP / Tank Solver
        self._solve_csp(clues, result)
        self._populate_ambiguous(clues, result)
        return result

    def _get_all_hidden_cells(self) -> List[Tuple[int, int]]:
        cells = []
        for r in range(self.board.height):
            for c in range(self.board.width):
                if self.board.state[r][c] == STATE_HIDDEN:
                    cells.append((r, c))
        return cells

    def _get_active_clues(self) -> Dict[Tuple[int, int], Dict[str, Any]]:
        """
        Returns revealed cells with numbers that touch at least one unrevealed cell.
        """
        clues = {}
        for r in range(self.board.height):
            for c in range(self.board.width):
                if self.board.state[r][c] == STATE_REVEALED:
                    adj_mines = getattr(self.board, "revealed_clues", {}).get((r, c), self.board.count_adjacent_mines(r, c))
                    if adj_mines > 0:
                        neighbors = self.board.get_neighbors(r, c)
                        hidden_neighbors = [
                            (nr, nc) for nr, nc in neighbors
                            if self.board.state[nr][nc] == STATE_HIDDEN
                        ]
                        flagged_neighbors = [
                            (nr, nc) for nr, nc in neighbors
                            if self.board.state[nr][nc] == STATE_FLAGGED
                        ]
                        if hidden_neighbors:
                            clues[(r, c)] = {
                                "num": adj_mines,
                                "effective_num": adj_mines - len(flagged_neighbors),
                                "hidden": set(hidden_neighbors),
                                "flags": set(flagged_neighbors),
                            }
        return clues

    def _find_trivial_deductions(
        self, clues: Dict[Tuple[int, int], Dict[str, Any]], result: SolverResult
    ) -> bool:
        found_any = False
        for (r, c), data in clues.items():
            eff = data["effective_num"]
            hidden = data["hidden"]
            orig_num = data["num"]
            num_flags = len(data["flags"])

            # All required mines already flagged -> all remaining hidden are SAFE
            if eff == 0:
                for hr, hc in hidden:
                    found_any = True
                    desc = (
                        f"Clue '{orig_num}' at ({r+1}, {c+1}) already has all required mines flagged "
                        f"({num_flags}/{orig_num}); neighbor ({hr+1}, {hc+1}) is guaranteed safe."
                    )
                    result.add_safe((hr, hc), Deduction((hr, hc), False, [(r, c)], desc))

            # Remaining hidden cells exactly equal missing mines -> all are MINES
            elif eff == len(hidden):
                for hr, hc in hidden:
                    desc = (
                        f"Clue '{orig_num}' at ({r+1}, {c+1}) needs {eff} more mine(s) among {len(hidden)} "
                        f"hidden neighbor(s); ({hr+1}, {hc+1}) must be a mine."
                    )
                    result.add_mine((hr, hc), Deduction((hr, hc), True, [(r, c)], desc))

        return found_any

    def _find_subset_deductions(
        self, clues: Dict[Tuple[int, int], Dict[str, Any]], result: SolverResult
    ):
        """
        Detects subset reductions between pairs of clues.
        If hidden(A) is a subset of hidden(B), then:
        mines in (hidden(B) - hidden(A)) = eff(B) - eff(A)
        """
        clue_keys = list(clues.keys())
        for i in range(len(clue_keys)):
            k_a = clue_keys[i]
            data_a = clues[k_a]
            hidden_a = data_a["hidden"]
            eff_a = data_a["effective_num"]

            for j in range(len(clue_keys)):
                if i == j:
                    continue
                k_b = clue_keys[j]
                data_b = clues[k_b]
                hidden_b = data_b["hidden"]
                eff_b = data_b["effective_num"]

                if hidden_a.issubset(hidden_b) and hidden_a != hidden_b:
                    diff = hidden_b - hidden_a
                    needed_in_diff = eff_b - eff_a

                    if needed_in_diff == 0:
                        for hr, hc in diff:
                            desc = (
                                f"Clue '{data_a['num']}' at ({k_a[0]+1}, {k_a[1]+1}) accounts for all mines "
                                f"required by clue '{data_b['num']}' at ({k_b[0]+1}, {k_b[1]+1}); "
                                f"therefore, tile ({hr+1}, {hc+1}) is guaranteed safe."
                            )
                            result.add_safe((hr, hc), Deduction((hr, hc), False, [k_a, k_b], desc))

                    elif needed_in_diff == len(diff):
                        for hr, hc in diff:
                            desc = (
                                f"By comparing clue '{data_a['num']}' at ({k_a[0]+1}, {k_a[1]+1}) and "
                                f"'{data_b['num']}' at ({k_b[0]+1}, {k_b[1]+1}), all remaining {len(diff)} "
                                f"neighbor(s) must be mines; ({hr+1}, {hc+1}) is a mine."
                            )
                            result.add_mine((hr, hc), Deduction((hr, hc), True, [k_a, k_b], desc))

    def _solve_csp(
        self, clues: Dict[Tuple[int, int], Dict[str, Any]], result: SolverResult
    ):
        """
        General Tank / Backtracking solver for connected components of the frontier.
        """
        # Build bipartite graph between clues and frontier cells
        frontier_cells: Set[Tuple[int, int]] = set()
        cell_to_clues: Dict[Tuple[int, int], Set[Tuple[int, int]]] = defaultdict(set)
        for clue_pos, data in clues.items():
            for cell in data["hidden"]:
                frontier_cells.add(cell)
                cell_to_clues[cell].add(clue_pos)

        # Decompose frontier into connected components
        visited_cells: Set[Tuple[int, int]] = set()
        components: List[List[Tuple[int, int]]] = []

        for cell in frontier_cells:
            if cell in visited_cells:
                continue
            comp_cells: List[Tuple[int, int]] = []
            queue = [cell]
            visited_cells.add(cell)

            while queue:
                curr = queue.pop(0)
                comp_cells.append(curr)
                # Find all neighbor cells connected via shared clues
                for cl in cell_to_clues[curr]:
                    for neighbor_cell in clues[cl]["hidden"]:
                        if neighbor_cell not in visited_cells:
                            visited_cells.add(neighbor_cell)
                            queue.append(neighbor_cell)
            components.append(comp_cells)

        # Solve each component independently
        for comp in components:
            comp_clues = set()
            for c in comp:
                comp_clues.update(cell_to_clues[c])

            valid_configs = self._enumerate_component_configs(comp, comp_clues, clues)
            if not valid_configs or getattr(self, "last_search_truncated", False):
                continue

            num_configs = len(valid_configs)
            mine_counts = defaultdict(int)
            for cfg in valid_configs:
                for c in comp:
                    if cfg.get(c, 0) == 1:
                        mine_counts[c] += 1

            for c in comp:
                if mine_counts[c] == 0:
                    clue_list = list(cell_to_clues[c])[:3]
                    clue_str = ", ".join(f"({r+1}, {col+1})" for r, col in clue_list)
                    desc = (
                        f"All valid mine configurations satisfying clues at {clue_str} "
                        f"leave tile ({c[0]+1}, {c[1]+1}) guaranteed safe."
                    )
                    result.add_safe(c, Deduction(c, False, clue_list, desc))
                elif mine_counts[c] == num_configs:
                    clue_list = list(cell_to_clues[c])[:3]
                    clue_str = ", ".join(f"({r+1}, {col+1})" for r, col in clue_list)
                    desc = (
                        f"All valid mine configurations satisfying clues at {clue_str} "
                        f"require a mine at tile ({c[0]+1}, {c[1]+1})."
                    )
                    result.add_mine(c, Deduction(c, True, clue_list, desc))

    def _enumerate_component_configs(
        self,
        comp_cells: List[Tuple[int, int]],
        comp_clues: Set[Tuple[int, int]],
        clues: Dict[Tuple[int, int], Dict[str, Any]],
        max_configs: int = 1000,
        max_nodes: int = 20000,
    ) -> List[Dict[Tuple[int, int], int]]:
        """
        Backtracking search over binary assignments for comp_cells.
        Orders cells to prune early and limits node visits to protect latency.
        """
        ordered_cells = sorted(list(comp_cells), key=lambda pt: (pt[0], pt[1]))

        valid_configs: List[Dict[Tuple[int, int], int]] = []
        assignment: Dict[Tuple[int, int], int] = {}
        
        # Precompute which clues touch which cell in this component
        clue_cells = {clue: [c for c in ordered_cells if c in clues[clue]["hidden"]] for clue in comp_clues}

        def is_consistent_partial() -> bool:
            for clue, cells in clue_cells.items():
                assigned_cells = [c for c in cells if c in assignment]
                mines_assigned = sum(assignment[c] for c in assigned_cells)
                eff = clues[clue]["effective_num"]
                
                # If already exceeded clue count
                if mines_assigned > eff:
                    return False
                
                # If remaining unassigned cells cannot reach required clue count
                unassigned_count = len(cells) - len(assigned_cells)
                if mines_assigned + unassigned_count < eff:
                    return False
            return True

        nodes = 0
        self.last_search_truncated = False

        def backtrack(index: int):
            nonlocal nodes
            nodes += 1
            if nodes > max_nodes or len(valid_configs) >= max_configs:
                self.last_search_truncated = True
                return

            if not is_consistent_partial():
                return
            if index == len(ordered_cells):
                valid_configs.append(dict(assignment))
                return

            cell = ordered_cells[index]
            # Try 0 (Safe)
            assignment[cell] = 0
            backtrack(index + 1)
            if self.last_search_truncated:
                del assignment[cell]
                return

            # Try 1 (Mine)
            assignment[cell] = 1
            backtrack(index + 1)

            del assignment[cell]

        backtrack(0)
        return valid_configs

    def _populate_ambiguous(
        self, clues: Dict[Tuple[int, int], Dict[str, Any]], result: SolverResult
    ):
        """Adds all remaining hidden cells that are neither safe nor mines to ambiguous_cells."""
        all_hidden = self._get_all_hidden_cells()
        for cell in all_hidden:
            if cell not in result.safe_cells and cell not in result.mine_cells:
                result.ambiguous_cells.add(cell)
