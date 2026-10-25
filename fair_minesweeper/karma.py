"""
Fair Minesweeper - Karma Engine (Forced-Guess Protection & Unforced-Guess Retribution)
"""

from collections import defaultdict
from typing import Tuple, List, Optional, Dict, Any, Set
from fair_minesweeper.board import (
    Board,
    STATE_HIDDEN,
    STATE_REVEALED,
    STATE_FLAGGED,
    GAME_NOT_STARTED,
    GAME_IN_PROGRESS,
    GAME_WON,
    GAME_LOST,
)
from fair_minesweeper.solver import Solver, SolverResult


class KarmaEngine:
    def __init__(self, board: Optional[Board] = None):
        self.board = board if board is not None else Board()

    def start_new_game(self, width: int = 9, height: int = 9, num_mines: int = 10) -> Board:
        self.board = Board(width=width, height=height, num_mines=num_mines)
        return self.board

    def handle_click(self, r: int, c: int) -> Dict[str, Any]:
        """
        Processes a player's left-click on cell (r, c).
        Returns an event dict describing the result.
        """
        if not (0 <= r < self.board.height and 0 <= c < self.board.width):
            return {"status": "INVALID", "board": self.board.to_dict()}

        if self.board.game_state in (GAME_WON, GAME_LOST):
            return {"status": "GAME_OVER", "board": self.board.to_dict()}

        if self.board.state[r][c] != STATE_HIDDEN:
            return {"status": "IGNORED", "board": self.board.to_dict()}

        # Save snapshot before making any modifications
        self.board.save_snapshot()

        # First click guarantee
        if not self.board.first_click_done:
            self.board.initialize_mines(r, c)
            revealed = self.board.reveal(r, c)
            return {
                "status": "FIRST_CLICK",
                "revealed": [{"r": cr, "c": cc} for cr, cc in revealed],
                "board": self.board.to_dict(),
            }

        # Run solver on current visible state BEFORE click
        solver = Solver(self.board)
        result = solver.solve()

        # Check Karma Condition
        is_proven_safe = (r, c) in result.safe_cells
        deductions_available = len(result.safe_cells) > 0

        # --- CASE 1: PROVEN SAFE MOVE ---
        if is_proven_safe:
            revealed = self.board.reveal(r, c)
            return {
                "status": "SAFE_MOVE",
                "revealed": [{"r": cr, "c": cc} for cr, cc in revealed],
                "board": self.board.to_dict(),
            }

        # --- CASE 2: UNFORCED GUESS (PUNISHMENT) ---
        if deductions_available:
            # Player gambled when they had deducible safe move(s)!
            made_mine = self._ensure_cell_is_mine(r, c)
            if not made_mine and (r, c) not in self.board.mines:
                # If target cannot be made a mine consistently without violating clues,
                # then target was actually logically safe!
                revealed = self.board.reveal(r, c)
                return {
                    "status": "SAFE_MOVE",
                    "revealed": [{"r": cr, "c": cc} for cr, cc in revealed],
                    "board": self.board.to_dict(),
                }

            self.board.reveal(r, c)  # Will detonate mine and set GAME_LOST

            # Pick a missed safe deduction for post-mortem explanation
            missed_cell = next(iter(result.safe_cells))
            deduction = result.deductions.get(missed_cell)
            explanation = deduction.explanation if deduction else (
                f"Tile ({missed_cell[0]+1}, {missed_cell[1]+1}) was guaranteed safe."
            )
            clues = deduction.clues if deduction else []

            self.board.post_mortem = {
                "clicked": {"r": r, "c": c},
                "punished": True,
                "missed_safe_cell": {"r": missed_cell[0], "c": missed_cell[1]},
                "clues": [{"r": cr, "c": cc} for cr, cc in clues],
                "explanation": explanation,
            }

            return {
                "status": "PUNISHED",
                "clicked": {"r": r, "c": c},
                "missed_safe_cell": {"r": missed_cell[0], "c": missed_cell[1]},
                "explanation": explanation,
                "board": self.board.to_dict(),
            }

        # --- CASE 3: FORCED GUESS (PROTECTION) ---
        # No deducible safe moves anywhere on the board!
        self._ensure_cell_is_safe(r, c)
        revealed = self.board.reveal(r, c)
        return {
            "status": "FORCED_SAFE",
            "revealed": [{"r": cr, "c": cc} for cr, cc in revealed],
            "board": self.board.to_dict(),
        }

    def handle_flag(self, r: int, c: int) -> Dict[str, Any]:
        """Toggles a flag on (r, c)."""
        success = self.board.toggle_flag(r, c)
        return {"success": success, "board": self.board.to_dict()}

    def handle_chord(self, r: int, c: int) -> Dict[str, Any]:
        """
        Executes a chord move on revealed cell (r, c).
        Reveals each unflagged hidden neighbor through the Karma engine.
        """
        to_reveal = self.board.chord(r, c)
        if not to_reveal:
            return {"status": "NO_OP", "board": self.board.to_dict()}

        all_revealed = []
        for nr, nc in to_reveal:
            if self.board.game_state == GAME_LOST:
                break
            res = self.handle_click(nr, nc)
            if res.get("status") == "PUNISHED":
                return res
            if "revealed" in res:
                all_revealed.extend(res["revealed"])

        return {
            "status": "CHORD_SUCCESS",
            "revealed": all_revealed,
            "board": self.board.to_dict(),
        }

    def handle_undo(self) -> Dict[str, Any]:
        """Reverts to the previous board state."""
        success = self.board.undo()
        return {"success": success, "board": self.board.to_dict()}

    def _ensure_cell_is_mine(self, target_r: int, target_c: int) -> bool:
        """
        Ensures target_r, target_c contains a mine, adjusting another unconstrained
        cell or component so all existing revealed numbers remain completely valid.
        Returns True if target is (or successfully became) a mine without violating clues.
        """
        if (target_r, target_c) in self.board.mines:
            return True

        orig_mines = set(self.board.mines)

        # Check if target touches any revealed cell
        touches_revealed = any(
            self.board.state[nr][nc] == STATE_REVEALED
            for nr, nc in self.board.get_neighbors(target_r, target_c)
        )

        # CASE A: Wilderness cell (does not touch any revealed clues)
        if not touches_revealed:
            revealed_all = [
                (r, c) for r in range(self.board.height) for c in range(self.board.width)
                if self.board.state[r][c] == STATE_REVEALED
            ]
            def touches_any_revealed(r, c):
                return any(abs(r - rev_r) <= 1 and abs(c - rev_c) <= 1 for rev_r, rev_c in revealed_all)

            floating_mines = [m for m in self.board.mines if not touches_any_revealed(m[0], m[1])]
            if floating_mines:
                donor = floating_mines[0]
                self.board.mines.remove(donor)
                self.board.mines.add((target_r, target_c))
            else:
                self.board.mines.add((target_r, target_c))

            if self._are_revealed_clues_consistent():
                return True
            self.board.mines = orig_mines
            return False

        # CASE B: Frontier cell (touches revealed clues)
        # Use CSP solver to find a valid configuration for this connected component where target == 1
        solver = Solver(self.board)
        clues = solver._get_active_clues()

        frontier_cells = set()
        cell_to_clues = defaultdict(set)
        for clue_pos, data in clues.items():
            for cell in data["hidden"]:
                frontier_cells.add(cell)
                cell_to_clues[cell].add(clue_pos)

        if (target_r, target_c) in frontier_cells:
            visited = set()
            comp = []
            queue = [(target_r, target_c)]
            visited.add((target_r, target_c))
            while queue:
                curr = queue.pop(0)
                comp.append(curr)
                for cl in cell_to_clues.get(curr, []):
                    for neighbor in clues[cl]["hidden"]:
                        if neighbor not in visited:
                            visited.add(neighbor)
                            queue.append(neighbor)

            comp_clues = set()
            for c in comp:
                comp_clues.update(cell_to_clues.get(c, []))

            configs = solver._enumerate_component_configs(comp, comp_clues, clues)
            mine_configs = [cfg for cfg in configs if cfg.get((target_r, target_c)) == 1]

            if mine_configs:
                # Pick the configuration closest to current board state
                best_cfg = min(
                    mine_configs,
                    key=lambda cfg: sum(1 for c in comp if (c in self.board.mines) != (cfg.get(c, 0) == 1))
                )

                old_comp_mines = sum(1 for c in comp if c in self.board.mines)
                new_comp_mines = sum(1 for c in comp if best_cfg.get(c, 0) == 1)
                mine_delta = new_comp_mines - old_comp_mines

                # Apply new configuration to the frontier component
                for c in comp:
                    if best_cfg.get(c, 0) == 1:
                        self.board.mines.add(c)
                    else:
                        self.board.mines.discard(c)

                # Balance mine count in floating wilderness
                revealed_all = [
                    (r, c) for r in range(self.board.height) for c in range(self.board.width)
                    if self.board.state[r][c] == STATE_REVEALED
                ]
                def touches_any_revealed(r, c):
                    return any(abs(r - rev_r) <= 1 and abs(c - rev_c) <= 1 for rev_r, rev_c in revealed_all)

                if mine_delta > 0:
                    floating = [m for m in list(self.board.mines) if not touches_any_revealed(m[0], m[1])]
                    for i in range(min(mine_delta, len(floating))):
                        self.board.mines.remove(floating[i])
                elif mine_delta < 0:
                    all_hidden_floating = [
                        (r, c) for r in range(self.board.height) for c in range(self.board.width)
                        if self.board.state[r][c] == STATE_HIDDEN and (r, c) not in self.board.mines and not touches_any_revealed(r, c)
                    ]
                    for i in range(min(abs(mine_delta), len(all_hidden_floating))):
                        self.board.mines.add(all_hidden_floating[i])

                if self._are_revealed_clues_consistent():
                    return True

        # If no valid configuration allows a mine without violating clues, rollback and return False
        self.board.mines = orig_mines
        return False

    def _ensure_cell_is_safe(self, target_r: int, target_c: int) -> bool:
        """
        Ensures target_r, target_c is NOT a mine, shifting it away to another
        valid unrevealed cell while strictly preserving all revealed numbers.
        """
        if (target_r, target_c) not in self.board.mines:
            return True

        orig_mines = set(self.board.mines)

        touches_revealed = any(
            self.board.state[nr][nc] == STATE_REVEALED
            for nr, nc in self.board.get_neighbors(target_r, target_c)
        )

        # CASE A: Wilderness cell (does not touch revealed clues)
        if not touches_revealed:
            self.board.mines.remove((target_r, target_c))
            revealed_all = [
                (r, c) for r in range(self.board.height) for c in range(self.board.width)
                if self.board.state[r][c] == STATE_REVEALED
            ]
            def touches_any_revealed(r, c):
                return any(abs(r - rev_r) <= 1 and abs(c - rev_c) <= 1 for rev_r, rev_c in revealed_all)

            all_hidden_floating = [
                (r, c) for r in range(self.board.height) for c in range(self.board.width)
                if self.board.state[r][c] == STATE_HIDDEN and (r, c) not in self.board.mines and not touches_any_revealed(r, c)
            ]
            if all_hidden_floating:
                self.board.mines.add(all_hidden_floating[0])
            if self._are_revealed_clues_consistent():
                return True
            self.board.mines = orig_mines
            return False

        # CASE B: Frontier cell (touches revealed clues)
        solver = Solver(self.board)
        clues = solver._get_active_clues()

        frontier_cells = set()
        cell_to_clues = defaultdict(set)
        for clue_pos, data in clues.items():
            for cell in data["hidden"]:
                frontier_cells.add(cell)
                cell_to_clues[cell].add(clue_pos)

        if (target_r, target_c) in frontier_cells:
            visited = set()
            comp = []
            queue = [(target_r, target_c)]
            visited.add((target_r, target_c))
            while queue:
                curr = queue.pop(0)
                comp.append(curr)
                for cl in cell_to_clues.get(curr, []):
                    for neighbor in clues[cl]["hidden"]:
                        if neighbor not in visited:
                            visited.add(neighbor)
                            queue.append(neighbor)

            comp_clues = set()
            for c in comp:
                comp_clues.update(cell_to_clues.get(c, []))

            configs = solver._enumerate_component_configs(comp, comp_clues, clues)
            safe_configs = [cfg for cfg in configs if cfg.get((target_r, target_c)) == 0]

            if safe_configs:
                best_cfg = min(
                    safe_configs,
                    key=lambda cfg: sum(1 for c in comp if (c in self.board.mines) != (cfg.get(c, 0) == 1))
                )

                old_comp_mines = sum(1 for c in comp if c in self.board.mines)
                new_comp_mines = sum(1 for c in comp if best_cfg.get(c, 0) == 1)
                mine_delta = new_comp_mines - old_comp_mines

                for c in comp:
                    if best_cfg.get(c, 0) == 1:
                        self.board.mines.add(c)
                    else:
                        self.board.mines.discard(c)

                revealed_all = [
                    (r, c) for r in range(self.board.height) for c in range(self.board.width)
                    if self.board.state[r][c] == STATE_REVEALED
                ]
                def touches_any_revealed(r, c):
                    return any(abs(r - rev_r) <= 1 and abs(c - rev_c) <= 1 for rev_r, rev_c in revealed_all)

                if mine_delta > 0:
                    floating = [m for m in list(self.board.mines) if not touches_any_revealed(m[0], m[1])]
                    for i in range(min(mine_delta, len(floating))):
                        self.board.mines.remove(floating[i])
                elif mine_delta < 0:
                    all_hidden_floating = [
                        (r, c) for r in range(self.board.height) for c in range(self.board.width)
                        if self.board.state[r][c] == STATE_HIDDEN and (r, c) not in self.board.mines and not touches_any_revealed(r, c)
                    ]
                    for i in range(min(abs(mine_delta), len(all_hidden_floating))):
                        self.board.mines.add(all_hidden_floating[i])

                if self._are_revealed_clues_consistent():
                    return True

        # Fallback: remove mine only if consistent
        self.board.mines.discard((target_r, target_c))
        if self._are_revealed_clues_consistent():
            return True

        self.board.mines = orig_mines
        return False

    def _are_revealed_clues_consistent(self) -> bool:
        """Verifies that currently placed mines match all currently revealed clue numbers."""
        for (r, c), expected_clue in self.board.revealed_clues.items():
            if self.board.count_adjacent_mines(r, c) != expected_clue:
                return False
        return True
