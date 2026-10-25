# ⚡ Fair Minesweeper - Pure Logic Variant

> **If you think, you cannot lose to luck. If you gamble when logic was available, you die instantly.**

Fair Minesweeper is a strictly logical Minesweeper variant powered by a Python constraint-satisfaction engine compiled to WebAssembly via Pyodide.

---

## 🎮 The Core Rules

1. **Pure Logic Guarantee**: Every single board is solvable without guessing. If you play logically, you will achieve a 100% win rate.
2. **Forced-Guess Protection**: If the board ever reaches a true 50/50 ambiguity where zero tiles can be logically proven safe, any tile you click is **100% guaranteed safe**. The game will seamlessly rearrange the hidden mines behind the scenes without changing any revealed numbers.
3. **Unforced-Guess Retribution**: If you take an unforced gamble while at least one deducible safe move existed elsewhere on the board, the game shifts the mines to ensure you detonate immediately!
4. **Interactive Post-Mortem Visualizer**: Upon death, the game highlights which tile you missed, highlights the clue(s) that proved it safe, and gives you a step-by-step logic explanation.
5. **Time Machine (Undo)**: Press <kbd>Ctrl</kbd> + <kbd>Z</kbd> or click **Rewind Death** to jump back to the moment before your fatal guess and try another logical move.

---

## 🚀 Technologies

- **Python 3.12** (`fair_minesweeper/`): Constraint Satisfaction Problem (CSP) solver, connected component decomposition, and Karma Engine.
- **Pyodide & WebAssembly**: Runs standard CPython inside your browser with near-native speed.
- **Web Audio API**: Real-time retro sound synthesizer (no external audio files needed).
- **Modern Responsive UI**: Supports Beginner (9×9), Intermediate (16×16), Expert (30×16), and Custom grid dimensions.

---

## 🛠 Local Development

To run locally:
```bash
python -m http.server 8080
```
Then open `http://localhost:8080` in any modern web browser.
