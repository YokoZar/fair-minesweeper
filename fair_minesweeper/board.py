"""
Fair Minesweeper - Board Representation & Core Game Rules
"""

import random
import copy
from typing import List, Tuple, Set, Optional, Dict, Any

STATE_HIDDEN = 0
STATE_REVEALED = 1
STATE_FLAGGED = 2

GAME_NOT_STARTED = "NOT_STARTED"
GAME_IN_PROGRESS = "IN_PROGRESS"
GAME_WON = "WON"
GAME_LOST = "LOST"


class Board:
    def __init__(self, width: int = 9, height: int = 9, num_mines: int = 10):
        self.width = max(2, min(width, 50))
        self.height = max(2, min(height, 50))
        max_mines = (self.width * self.height) - 1
        self.num_mines = max(1, min(num_mines, max_mines))

        self.mines: Set[Tuple[int, int]] = set()
        self.state: List[List[int]] = [
            [STATE_HIDDEN for _ in range(self.width)] for _ in range(self.height)
        ]
        self.game_state: str = GAME_NOT_STARTED
        self.first_click_done: bool = False
        
        # Post-mortem analysis metadata if game is lost
        self.post_mortem: Optional[Dict[str, Any]] = None
        
        # Undo history stack for Debug Mode / Time Machine
        self.history: List[Dict[str, Any]] = []

        # Immutable record of clue numbers shown to the player for revealed tiles
        self.revealed_clues: Dict[Tuple[int, int], int] = {}

    def get_neighbors(self, r: int, c: int) -> List[Tuple[int, int]]:
        neighbors = []
        for dr in (-1, 0, 1):
            for dc in (-1, 0, 1):
                if dr == 0 and dc == 0:
                    continue
                nr, nc = r + dr, c + dc
                if 0 <= nr < self.height and 0 <= nc < self.width:
                    neighbors.append((nr, nc))
        return neighbors

    def count_adjacent_mines(self, r: int, c: int) -> int:
        count = 0
        for nr, nc in self.get_neighbors(r, c):
            if (nr, nc) in self.mines:
                count += 1
        return count

    def count_adjacent_flags(self, r: int, c: int) -> int:
        count = 0
        for nr, nc in self.get_neighbors(r, c):
            if self.state[nr][nc] == STATE_FLAGGED:
                count += 1
        return count

    def initialize_mines(self, safe_r: int, safe_c: int):
        """
        Populate mines ensuring safe_r, safe_c and its immediate 8 neighbors are mine-free
        if possible, guaranteeing an opening 0-cascade on first click.
        """
        all_cells = [(r, c) for r in range(self.height) for c in range(self.width)]
        safe_zone = set(self.get_neighbors(safe_r, safe_c))
        safe_zone.add((safe_r, safe_c))

        candidate_cells = [cell for cell in all_cells if cell not in safe_zone]
        
        # If board is too dense for a full 9-cell opening, at least keep the clicked cell safe
        if len(candidate_cells) < self.num_mines:
            candidate_cells = [cell for cell in all_cells if cell != (safe_r, safe_c)]

        self.mines = set(random.sample(candidate_cells, self.num_mines))
        self.first_click_done = True
        self.game_state = GAME_IN_PROGRESS

    def save_snapshot(self):
        """Saves current state onto the undo history stack."""
        snapshot = {
            "mines": set(self.mines),
            "state": [row[:] for row in self.state],
            "game_state": self.game_state,
            "first_click_done": self.first_click_done,
            "post_mortem": copy.deepcopy(self.post_mortem),
            "revealed_clues": dict(self.revealed_clues),
        }
        self.history.append(snapshot)
        # Limit history to 50 steps
        if len(self.history) > 50:
            self.history.pop(0)

    def undo(self) -> bool:
        """Restores the previous board state. Returns True if successful."""
        if not self.history:
            return False
        snapshot = self.history.pop()
        self.mines = snapshot["mines"]
        self.state = snapshot["state"]
        self.game_state = snapshot["game_state"]
        self.first_click_done = snapshot["first_click_done"]
        self.post_mortem = snapshot["post_mortem"]
        self.revealed_clues = snapshot.get("revealed_clues", {})
        return True

    def toggle_flag(self, r: int, c: int) -> bool:
        """Toggles flag on an unrevealed tile."""
        if self.game_state in (GAME_WON, GAME_LOST):
            return False
        if not (0 <= r < self.height and 0 <= c < self.width):
            return False
        
        if self.state[r][c] == STATE_HIDDEN:
            self.save_snapshot()
            self.state[r][c] = STATE_FLAGGED
            self.check_win()
            return True
        elif self.state[r][c] == STATE_FLAGGED:
            self.save_snapshot()
            self.state[r][c] = STATE_HIDDEN
            return True
        return False

    def reveal(self, r: int, c: int) -> List[Tuple[int, int]]:
        """
        Reveals cell (r, c). Returns list of newly revealed cells.
        Does NOT handle Karma shifting directly (KarmaEngine handles pre-reveal logic).
        """
        if self.state[r][c] != STATE_HIDDEN or self.game_state in (GAME_WON, GAME_LOST):
            return []

        # If detonating on a mine
        if (r, c) in self.mines:
            self.state[r][c] = STATE_REVEALED
            self.game_state = GAME_LOST
            return [(r, c)]

        # Flood fill reveal for safe cells
        revealed_cells = []
        queue = [(r, c)]
        self.state[r][c] = STATE_REVEALED
        self.revealed_clues[(r, c)] = self.count_adjacent_mines(r, c)
        revealed_cells.append((r, c))

        while queue:
            curr_r, curr_c = queue.pop(0)
            adj_mines = self.count_adjacent_mines(curr_r, curr_c)
            if adj_mines == 0:
                for nr, nc in self.get_neighbors(curr_r, curr_c):
                    if self.state[nr][nc] == STATE_HIDDEN:
                        self.state[nr][nc] = STATE_REVEALED
                        self.revealed_clues[(nr, nc)] = self.count_adjacent_mines(nr, nc)
                        revealed_cells.append((nr, nc))
                        queue.append((nr, nc))

        self.check_win()
        return revealed_cells

    def chord(self, r: int, c: int) -> List[Tuple[int, int]]:
        """
        If cell (r, c) is revealed and has adjacent flags equal to its number,
        reveals all unflagged hidden neighbors.
        """
        if self.state[r][c] != STATE_REVEALED or self.game_state != GAME_IN_PROGRESS:
            return []
        
        clue_num = self.count_adjacent_mines(r, c)
        if clue_num == 0:
            return []
        
        flags = self.count_adjacent_flags(r, c)
        if flags != clue_num:
            return []

        to_reveal = [
            (nr, nc) for nr, nc in self.get_neighbors(r, c)
            if self.state[nr][nc] == STATE_HIDDEN
        ]
        return to_reveal

    def check_win(self):
        """Checks if all non-mine cells have been revealed."""
        if self.game_state != GAME_IN_PROGRESS:
            return
        
        all_safe_revealed = True
        for r in range(self.height):
            for c in range(self.width):
                if (r, c) not in self.mines and self.state[r][c] != STATE_REVEALED:
                    all_safe_revealed = False
                    break
            if not all_safe_revealed:
                break

        if all_safe_revealed:
            self.game_state = GAME_WON

    def get_remaining_mines_count(self) -> int:
        flagged_count = sum(
            1 for r in range(self.height) for c in range(self.width)
            if self.state[r][c] == STATE_FLAGGED
        )
        return self.num_mines - flagged_count

    def to_dict(self) -> Dict[str, Any]:
        """Serializes current board state for the frontend."""
        grid = []
        for r in range(self.height):
            row = []
            for c in range(self.width):
                st = self.state[r][c]
                is_mine = (r, c) in self.mines
                adj = self.revealed_clues.get((r, c), self.count_adjacent_mines(r, c)) if st == STATE_REVEALED and not is_mine else 0
                cell_data = {
                    "r": r,
                    "c": c,
                    "state": st,
                    "adj": adj,
                    # Reveal all mines if game over
                    "is_mine": is_mine if self.game_state in (GAME_WON, GAME_LOST) else False,
                }
                row.append(cell_data)
            grid.append(row)

        return {
            "width": self.width,
            "height": self.height,
            "num_mines": self.num_mines,
            "mines_remaining": self.get_remaining_mines_count(),
            "game_state": self.game_state,
            "grid": grid,
            "post_mortem": self.post_mortem,
            "can_undo": len(self.history) > 0,
        }
