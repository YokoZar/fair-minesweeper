"""
Unit tests for Fair Minesweeper - Board, Solver, KarmaEngine, and Undo Stack
"""

import unittest
from fair_minesweeper.board import (
    Board,
    STATE_HIDDEN,
    STATE_REVEALED,
    STATE_FLAGGED,
    GAME_IN_PROGRESS,
    GAME_WON,
    GAME_LOST,
)
from fair_minesweeper.solver import Solver
from fair_minesweeper.karma import KarmaEngine


class TestFairMinesweeper(unittest.TestCase):

    def test_first_click_safety_and_cascade(self):
        engine = KarmaEngine()
        board = engine.start_new_game(9, 9, 10)
        res = engine.handle_click(4, 4)
        
        self.assertEqual(res["status"], "FIRST_CLICK")
        self.assertEqual(board.game_state, GAME_IN_PROGRESS)
        self.assertEqual(board.state[4][4], STATE_REVEALED)
        self.assertNotIn((4, 4), board.mines)
        # Verify first click revealed at least 1 cell (and typically an opening cascade)
        self.assertGreater(len(res["revealed"]), 0)

    def test_flagging_and_undo(self):
        engine = KarmaEngine()
        board = engine.start_new_game(9, 9, 10)
        engine.handle_click(0, 0)
        
        # Find a hidden cell
        hidden_cell = None
        for r in range(9):
            for c in range(9):
                if board.state[r][c] == STATE_HIDDEN:
                    hidden_cell = (r, c)
                    break
            if hidden_cell:
                break

        r, c = hidden_cell
        res = engine.handle_flag(r, c)
        self.assertTrue(res["success"])
        self.assertEqual(board.state[r][c], STATE_FLAGGED)

        # Undo flag
        undo_res = engine.handle_undo()
        self.assertTrue(undo_res["success"])
        self.assertEqual(board.state[r][c], STATE_HIDDEN)

    def test_solver_trivial_safe_and_mines(self):
        board = Board(width=4, height=4, num_mines=1)
        board.mines = {(0, 1)}
        board.first_click_done = True
        board.game_state = GAME_IN_PROGRESS
        
        # Reveal (1, 1), which has adj count = 1 (touching mine at (0, 1))
        board.state[1][1] = STATE_REVEALED
        # Flag the mine at (0, 1)
        board.state[0][1] = STATE_FLAGGED
        
        solver = Solver(board)
        result = solver.solve()
        
        # All other hidden neighbors of (1, 1) must be guaranteed safe!
        neighbors = board.get_neighbors(1, 1)
        for nr, nc in neighbors:
            if (nr, nc) != (0, 1) and board.state[nr][nc] == STATE_HIDDEN:
                self.assertIn((nr, nc), result.safe_cells)
                self.assertIn((nr, nc), result.deductions)
                deduction = result.deductions[(nr, nc)]
                self.assertIn("already has all required mines flagged", deduction.explanation)

    def test_solver_subset_reduction(self):
        """
        Setup a classic 1-1 pattern:
        Row 0: [Hidden A, Hidden B, Hidden C]
        Row 1: [Revealed 1, Revealed 1, Safe]
        Touching A, B has 1 mine. Touching A, B, C has 1 mine.
        Therefore, C is guaranteed safe!
        """
        board = Board(width=4, height=3, num_mines=1)
        board.first_click_done = True
        board.game_state = GAME_IN_PROGRESS
        board.mines = {(0, 0)}  # Mine at A
        
        # Set up clues
        board.state[1][0] = STATE_REVEALED  # Clue 1 touches (0, 0) and (0, 1)
        board.state[1][1] = STATE_REVEALED  # Clue 1 touches (0, 0), (0, 1), and (0, 2)
        
        # Make other neighbors revealed/out of way so (0,0),(0,1) touch (1,0),
        # and (0,0),(0,1),(0,2) touch (1,1)
        board.state[1][2] = STATE_REVEALED
        board.state[2][0] = STATE_REVEALED
        board.state[2][1] = STATE_REVEALED
        board.state[2][2] = STATE_REVEALED
        
        solver = Solver(board)
        result = solver.solve()
        
        # Cell (0, 2) must be deduced safe by subset reduction!
        self.assertIn((0, 2), result.safe_cells)

    def test_unforced_guess_punishment(self):
        """
        When a logically deducible safe move exists, but player clicks an ambiguous tile:
        Verify the player detonates and is punished 100% of the time.
        """
        board = Board(width=5, height=5, num_mines=2)
        board.first_click_done = True
        board.game_state = GAME_IN_PROGRESS
        # Set mines
        board.mines = {(0, 0), (4, 4)}
        
        # Reveal (1, 1) and flag (0, 0) -> cell (0, 1) is guaranteed safe!
        board.state[1][1] = STATE_REVEALED
        board.state[0][0] = STATE_FLAGGED
        
        engine = KarmaEngine(board)
        
        # (0, 1) is deducible safe.
        # But the player carelessly clicks far away at (4, 3) (an unforced guess)!
        res = engine.handle_click(4, 3)
        
        self.assertEqual(res["status"], "PUNISHED")
        self.assertEqual(board.game_state, GAME_LOST)
        self.assertIn((4, 3), board.mines)  # Guaranteed to be a mine!
        
        # Post-mortem should highlight the missed deduction
        self.assertIsNotNone(board.post_mortem)
        self.assertTrue(board.post_mortem["punished"])
        self.assertEqual(board.post_mortem["missed_safe_cell"], {"r": 0, "c": 1})

    def test_forced_guess_protection(self):
        """
        When ZERO deducible safe moves exist (forced guess situation):
        Verify that player's guess is guaranteed safe 100% of the time.
        """
        # Create a textbook 2x2 symmetric 50/50 board
        board = Board(width=2, height=2, num_mines=1)
        board.first_click_done = True
        board.game_state = GAME_IN_PROGRESS
        board.mines = {(0, 1)}  # Hidden mine at (0, 1)
        
        # Row 1 is revealed with clue 1
        board.state[1][0] = STATE_REVEALED
        board.state[1][1] = STATE_REVEALED
        # Neither (0, 0) nor (0, 1) can be deduced safe (pure 50/50)

        engine = KarmaEngine(board)
        
        # Player guesses (0, 1), which was initially the mine!
        res = engine.handle_click(0, 1)
        
        # Protection must trigger, shifting the mine to (0, 0) so (0, 1) is safe!
        self.assertEqual(res["status"], "FORCED_SAFE")
        self.assertIn(board.game_state, [GAME_IN_PROGRESS, GAME_WON])
        self.assertEqual(board.state[0][1], STATE_REVEALED)
        self.assertNotIn((0, 1), board.mines)
        self.assertIn((0, 0), board.mines)

    def test_debug_undo_after_death(self):
        """
        Tests the 'Time Machine' undo functionality after dying.
        """
        board = Board(width=4, height=4, num_mines=1)
        board.first_click_done = True
        board.game_state = GAME_IN_PROGRESS
        board.mines = {(0, 0)}
        board.state[1][1] = STATE_REVEALED
        board.state[0][0] = STATE_FLAGGED
        
        engine = KarmaEngine(board)
        # Player dies due to unforced guess at (3, 3)
        res = engine.handle_click(3, 3)
        self.assertEqual(res["status"], "PUNISHED")
        self.assertEqual(board.game_state, GAME_LOST)
        
        # Activate Time Machine Undo
        undo_res = engine.handle_undo()
        self.assertTrue(undo_res["success"])
        self.assertEqual(board.game_state, GAME_IN_PROGRESS)
        self.assertEqual(board.state[3][3], STATE_HIDDEN)
        
        # Now player clicks the correct safe tile (0, 1)
        safe_res = engine.handle_click(0, 1)
        self.assertEqual(safe_res["status"], "SAFE_MOVE")
        self.assertEqual(board.state[0][1], STATE_REVEALED)

    def test_punishment_preserves_revealed_clues(self):
        """
        Regression test: When punishment shifts mines to detonate an unforced guess,
        it MUST NEVER alter existing revealed numbers (e.g. turning a 4 into a 5).
        """
        board = Board(width=6, height=6, num_mines=5)
        board.first_click_done = True
        board.game_state = GAME_IN_PROGRESS
        # Set up a board where (1, 1) is revealed as a 2, with mines at (0, 1) and (0, 0)
        # and hidden neighbors (0, 2), (1, 2), (2, 2).
        # Safe deduction exists at (5, 5).
        board.mines = {(0, 0), (0, 1), (5, 0)}
        board.state[1][1] = STATE_REVEALED
        board.revealed_clues[(1, 1)] = 2
        # (5, 5) has a 0 clue revealed nearby, making (5, 4) trivially safe
        board.state[5][5] = STATE_REVEALED
        board.revealed_clues[(5, 5)] = 0
        
        engine = KarmaEngine(board)
        # Player gambles on (0, 2) which is adjacent to revealed (1, 1)
        res = engine.handle_click(0, 2)
        
        # Verify (1, 1) clue in serialized board remains strictly 2, not 3!
        board_dict = board.to_dict()
        cell_1_1 = board_dict["grid"][1][1]
        self.assertEqual(cell_1_1["adj"], 2, "Revealed clue must never mutate after punishment!")
        self.assertTrue(engine._are_revealed_clues_consistent(), "Revealed clues must remain consistent!")

    def test_user_repro_punishment_preserves_clues(self):
        """
        Exact board setup from user report:
        Revealed clues at (12, 21)=2, (13, 21)=1, (14, 21)=1.
        Clicking unforced gamble (13, 22) must keep all 3 revealed numbers unchanged.
        """
        board = Board(width=30, height=16, num_mines=99)
        board.mines = {
            (0, 2), (0, 8), (0, 13), (0, 24), (0, 25), (1, 2), (1, 3), (1, 8), (1, 17), (1, 23),
            (8, 0), (8, 1), (8, 6), (11, 20), (12, 4), (12, 11), (14, 22)
        }
        board.first_click_done = True
        board.game_state = GAME_IN_PROGRESS

        # Setup clues
        board.state[12][21] = STATE_REVEALED
        board.revealed_clues[(12, 21)] = 2
        board.state[13][21] = STATE_REVEALED
        board.revealed_clues[(13, 21)] = 1
        board.state[14][21] = STATE_REVEALED
        board.revealed_clues[(14, 21)] = 1

        engine = KarmaEngine(board)
        # Attempt to make (13, 22) a mine
        success = engine._ensure_cell_is_mine(13, 22)
        self.assertTrue(success)
        self.assertIn((13, 22), board.mines)
        self.assertTrue(engine._are_revealed_clues_consistent())

        board_dict = board.to_dict()
        self.assertEqual(board_dict["grid"][12][21]["adj"], 2)
        self.assertEqual(board_dict["grid"][13][21]["adj"], 1)
        self.assertEqual(board_dict["grid"][14][21]["adj"], 1)

    def test_large_component_csp_no_keyerror(self):
        """
        Regression test for KeyError when component has > 30 cells.
        Sets up a 35-cell frontier and verifies solve() completes without error.
        """
        board = Board(width=40, height=10, num_mines=10)
        board.first_click_done = True
        board.game_state = GAME_IN_PROGRESS

        # Create a line of 35 revealed cells at row 1, with hidden cells at row 0
        for c in range(1, 36):
            board.state[1][c] = STATE_REVEALED
            board.revealed_clues[(1, c)] = 1

        solver = Solver(board)
        # solve() must execute without throwing KeyError: (r, c)
        result = solver.solve()
        self.assertIsNotNone(result)

    def test_dense_board_forced_guess_protection(self):
        """
        Regression test: On a dense board (e.g. 10x10 with 98 mines, only 2 safe tiles),
        when the first click opens an 8, clicking any wilderness tile MUST be protected as
        a forced guess, and the target tile must NEVER be chosen as its own mine replacement.
        """
        import random
        for _ in range(25):
            engine = KarmaEngine()
            board = engine.start_new_game(10, 10, 98)
            res1 = engine.handle_click(5, 5)
            
            # Find a wilderness tile
            hidden = [(r, c) for r in range(10) for c in range(10) if board.state[r][c] == STATE_HIDDEN]
            neighbors = set(board.get_neighbors(5, 5))
            wilderness = [c for c in hidden if c not in neighbors]
            if wilderness and board.count_adjacent_mines(5, 5) == len(neighbors):
                target = random.choice(wilderness)
                res2 = engine.handle_click(target[0], target[1])
                # Forced guess on wilderness must NOT detonate!
                self.assertNotEqual(board.game_state, GAME_LOST, f"Died on forced guess {target}!")
                self.assertEqual(board.game_state, GAME_WON)

    def test_proven_mine_click_punished(self):
        """
        When a tile is logically proven to be a mine (e.g. clue 1 touching 1 hidden cell),
        clicking that mine directly must detonate and trigger post-mortem explanation.
        """
        board = Board(width=4, height=4, num_mines=1)
        board.first_click_done = True
        board.game_state = GAME_IN_PROGRESS
        board.mines = {(0, 0)}
        board.state[1][1] = STATE_REVEALED
        board.revealed_clues[(1, 1)] = 1
        # Make (0,0) the only hidden neighbor of (1,1)
        for nr, nc in board.get_neighbors(1, 1):
            if (nr, nc) != (0, 0):
                board.state[nr][nc] = STATE_REVEALED
                board.revealed_clues[(nr, nc)] = 0

        engine = KarmaEngine(board)
        res = engine.handle_click(0, 0)
        self.assertEqual(res["status"], "PUNISHED")
        self.assertEqual(board.game_state, GAME_LOST)
        self.assertIsNotNone(board.post_mortem)
        self.assertTrue("require a mine" in board.post_mortem["explanation"] or "must be a mine" in board.post_mortem["explanation"])


if __name__ == "__main__":
    unittest.main()
