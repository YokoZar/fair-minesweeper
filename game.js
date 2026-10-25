/**
 * Fair Minesweeper - Frontend Game Controller
 */

class MinesweeperGame {
    constructor() {
        this.width = 9;
        this.height = 9;
        this.numMines = 10;
        this.currentDifficulty = "beginner";

        this.boardData = null;
        this.timer = 0;
        this.timerInterval = null;
        this.timerRunning = false;

        // Mouse chord tracking
        this.mouseButtonsDown = new Set();
        this.longPressTimer = null;

        this.initDOM();
        this.initHotkeys();
    }

    initDOM() {
        this.gridEl = document.getElementById("boardGrid");
        this.mineCountEl = document.getElementById("mineCountDisplay");
        this.timerEl = document.getElementById("timerDisplay");
        this.faceBtnEl = document.getElementById("faceBtn");
        this.postMortemCard = document.getElementById("postMortemCard");
        this.postMortemText = document.getElementById("postMortemText");
        this.undoBtn = document.getElementById("undoBtn");
        this.footerUndoBtn = document.getElementById("footerUndoBtn");
        this.muteBtn = document.getElementById("muteBtn");

        // Face button
        this.faceBtnEl.addEventListener("click", () => this.startNewGame());

        // Undo buttons
        this.undoBtn.addEventListener("click", () => this.undoMove());
        this.footerUndoBtn.addEventListener("click", () => this.undoMove());

        // Mute button
        this.muteBtn.addEventListener("click", () => {
            const isMuted = window.soundEffects.toggleMute();
            this.muteBtn.textContent = isMuted ? "🔇 Muted" : "🔊 Sound On";
        });

        // Difficulty selectors
        document.querySelectorAll(".diff-btn").forEach(btn => {
            btn.addEventListener("click", (e) => {
                const diff = e.target.getAttribute("data-diff");
                this.selectDifficulty(diff);
            });
        });

        // Custom Modal
        this.customModal = document.getElementById("customModal");
        document.getElementById("btnCustomCancel").addEventListener("click", () => {
            this.customModal.classList.remove("active");
        });
        document.getElementById("btnCustomConfirm").addEventListener("click", () => {
            const w = parseInt(document.getElementById("customWidth").value, 10);
            const h = parseInt(document.getElementById("customHeight").value, 10);
            const m = parseInt(document.getElementById("customMines").value, 10);
            if (w >= 4 && h >= 4 && m >= 1 && m < w * h) {
                this.width = w;
                this.height = h;
                this.numMines = m;
                this.customModal.classList.remove("active");
                this.startNewGame();
            } else {
                alert("Please enter valid dimensions (W>=4, H>=4, 1 <= Mines < W*H)");
            }
        });

        // Rules modal
        const rulesModal = document.getElementById("rulesModal");
        document.getElementById("rulesBtn").addEventListener("click", () => {
            rulesModal.classList.add("active");
        });
        document.getElementById("btnRulesClose").addEventListener("click", () => {
            rulesModal.classList.remove("active");
        });

        // Prevent context menu on grid
        this.gridEl.addEventListener("contextmenu", (e) => e.preventDefault());
    }

    initHotkeys() {
        window.addEventListener("keydown", (e) => {
            if ((e.ctrlKey && e.key.toLowerCase() === "z") || e.key.toLowerCase() === "u") {
                e.preventDefault();
                this.undoMove();
            } else if (e.key.toLowerCase() === "r") {
                this.startNewGame();
            } else if (e.key.toLowerCase() === "m") {
                const isMuted = window.soundEffects.toggleMute();
                this.muteBtn.textContent = isMuted ? "🔇 Muted" : "🔊 Sound On";
            }
        });
    }

    selectDifficulty(diff) {
        document.querySelectorAll(".diff-btn").forEach(b => b.classList.remove("active"));
        const targetBtn = document.querySelector(`.diff-btn[data-diff="${diff}"]`);
        if (targetBtn) targetBtn.classList.add("active");

        this.currentDifficulty = diff;
        if (diff === "beginner") {
            this.width = 9;
            this.height = 9;
            this.numMines = 10;
            this.startNewGame();
        } else if (diff === "intermediate") {
            this.width = 16;
            this.height = 16;
            this.numMines = 40;
            this.startNewGame();
        } else if (diff === "expert") {
            this.width = 30;
            this.height = 16;
            this.numMines = 99;
            this.startNewGame();
        } else if (diff === "custom") {
            this.customModal.classList.add("active");
        }
    }

    startNewGame() {
        this.stopTimer();
        this.resetTimer();
        this.hidePostMortem();
        this.setFace("🙂");

        if (!window.pyodideBridge || !window.pyodideBridge.ready) {
            return;
        }

        this.boardData = window.pyodideBridge.newGame(this.width, this.height, this.numMines);
        this.renderBoard();
        this.updateHUD();
    }

    startTimer() {
        if (this.timerRunning) return;
        this.timerRunning = true;
        this.timer = 0;
        this.timerEl.textContent = "000";
        this.timerInterval = setInterval(() => {
            this.timer = Math.min(999, this.timer + 1);
            this.timerEl.textContent = String(this.timer).padStart(3, "0");
        }, 1000);
    }

    stopTimer() {
        this.timerRunning = false;
        if (this.timerInterval) {
            clearInterval(this.timerInterval);
            this.timerInterval = null;
        }
    }

    resetTimer() {
        this.timer = 0;
        this.timerEl.textContent = "000";
    }

    setFace(emoji) {
        this.faceBtnEl.textContent = emoji;
    }

    renderBoard() {
        if (!this.boardData) return;

        this.gridEl.innerHTML = "";
        this.gridEl.style.gridTemplateColumns = `repeat(${this.boardData.width}, 34px)`;

        const isGameOver = this.boardData.game_state === "LOST" || this.boardData.game_state === "WON";
        const postMortem = this.boardData.post_mortem;

        const missedSafe = postMortem?.missed_safe_cell;
        const clueCoords = new Set(
            (postMortem?.clues || []).map(c => `${c.r},${c.c}`)
        );
        const clickedCoord = postMortem?.clicked;

        for (let r = 0; r < this.boardData.height; r++) {
            for (let c = 0; c < this.boardData.width; c++) {
                const cellData = this.boardData.grid[r][c];
                const cellEl = document.createElement("div");
                cellEl.className = "cell";
                cellEl.dataset.r = r;
                cellEl.dataset.c = c;

                // State styling
                if (cellData.state === 0) { // HIDDEN
                    cellEl.classList.add("hidden");

                    if (isGameOver && cellData.is_mine) {
                        cellEl.classList.add("mine");
                        cellEl.textContent = "💣";
                    }

                    // Highlight missed safe tile in post-mortem
                    if (missedSafe && missedSafe.r === r && missedSafe.c === c) {
                        cellEl.classList.add("highlight-safe");
                        cellEl.title = "This tile was 100% logically guaranteed safe!";
                    }
                } else if (cellData.state === 1) { // REVEALED
                    cellEl.classList.add("revealed");
                    if (cellData.is_mine) {
                        cellEl.classList.add("mine");
                        cellEl.textContent = "💣";
                        if (clickedCoord && clickedCoord.r === r && clickedCoord.c === c) {
                            cellEl.classList.add("detonated");
                        }
                    } else if (cellData.adj > 0) {
                        cellEl.textContent = cellData.adj;
                        cellEl.setAttribute("data-num", cellData.adj);
                    }

                    // Highlight clue(s) that proved the safe tile
                    if (clueCoords.has(`${r},${c}`)) {
                        cellEl.classList.add("highlight-clue");
                        cellEl.title = "This clue proved the safe tile!";
                    }
                } else if (cellData.state === 2) { // FLAGGED
                    cellEl.classList.add("hidden", "flagged");
                    cellEl.textContent = "🚩";
                }

                // Mouse / Touch listeners
                this.attachCellListeners(cellEl, r, c);
                this.gridEl.appendChild(cellEl);
            }
        }
    }

    attachCellListeners(el, r, c) {
        // Prevent default browser context menu on right click / long press
        el.addEventListener("contextmenu", (e) => {
            e.preventDefault();
        });

        // Track touch gestures to prevent synthetic mouse click conflicts
        let touchStartX = 0;
        let touchStartY = 0;
        let touchMoved = false;
        let longPressTriggered = false;

        // Desktop mouse chord & click handling
        el.addEventListener("mousedown", (e) => {
            if (this.boardData.game_state !== "LOST" && this.boardData.game_state !== "WON") {
                this.setFace("😮");
            }
            this.mouseButtonsDown.add(e.button);

            // Left + Right simultaneous chord click
            if (this.mouseButtonsDown.has(0) && this.mouseButtonsDown.has(2)) {
                this.onCellChord(r, c);
            }
        });

        el.addEventListener("mouseup", (e) => {
            this.mouseButtonsDown.delete(e.button);
            if (this.boardData.game_state === "IN_PROGRESS" || this.boardData.game_state === "NOT_STARTED") {
                this.setFace("🙂");
            }

            // Suppress synthetic mouseup if touch long-press just fired
            if (longPressTriggered) {
                longPressTriggered = false;
                return;
            }

            if (e.button === 0) { // Left click
                this.onCellClick(r, c);
            } else if (e.button === 2) { // Right click
                this.onCellFlag(r, c);
            } else if (e.button === 1) { // Middle click chord
                this.onCellChord(r, c);
            }
        });

        // Double click chord (Desktop)
        el.addEventListener("dblclick", (e) => {
            e.preventDefault();
            this.onCellChord(r, c);
        });

        // Mobile touch handling (long-press: flag hidden tile OR chord revealed number)
        el.addEventListener("touchstart", (e) => {
            if (e.touches.length > 1) {
                if (this.longPressTimer) {
                    clearTimeout(this.longPressTimer);
                    this.longPressTimer = null;
                }
                return;
            }

            touchStartX = e.touches[0].clientX;
            touchStartY = e.touches[0].clientY;
            touchMoved = false;
            longPressTriggered = false;

            if (this.boardData.game_state !== "LOST" && this.boardData.game_state !== "WON") {
                this.setFace("😮");
            }

            this.longPressTimer = setTimeout(() => {
                this.longPressTimer = null;
                longPressTriggered = true;

                if (this.boardData.game_state === "IN_PROGRESS" || this.boardData.game_state === "NOT_STARTED") {
                    this.setFace("🙂");
                }

                if (!this.boardData || !this.boardData.grid || !this.boardData.grid[r]) return;
                const cellData = this.boardData.grid[r][c];

                if (cellData.state === 1 && cellData.adj > 0) {
                    // Mobile: Long-press on revealed number performs a chord (both-click)
                    this.onCellChord(r, c);
                    if (navigator.vibrate) navigator.vibrate(35);
                } else if (cellData.state === 0 || cellData.state === 2) {
                    // Mobile: Long-press on hidden or flagged tile toggles flag
                    this.onCellFlag(r, c);
                    if (navigator.vibrate) navigator.vibrate(25);
                }
            }, 380);
        }, { passive: true });

        el.addEventListener("touchmove", (e) => {
            if (!this.longPressTimer) return;
            const dx = e.touches[0].clientX - touchStartX;
            const dy = e.touches[0].clientY - touchStartY;
            // If finger moved > 10px, the user is panning/scrolling the grid
            if (Math.hypot(dx, dy) > 10) {
                touchMoved = true;
                clearTimeout(this.longPressTimer);
                this.longPressTimer = null;
                if (this.boardData.game_state === "IN_PROGRESS" || this.boardData.game_state === "NOT_STARTED") {
                    this.setFace("🙂");
                }
            }
        }, { passive: true });

        el.addEventListener("touchcancel", () => {
            if (this.longPressTimer) {
                clearTimeout(this.longPressTimer);
                this.longPressTimer = null;
            }
            if (this.boardData.game_state === "IN_PROGRESS" || this.boardData.game_state === "NOT_STARTED") {
                this.setFace("🙂");
            }
        });

        el.addEventListener("touchend", (e) => {
            if (this.boardData.game_state === "IN_PROGRESS" || this.boardData.game_state === "NOT_STARTED") {
                this.setFace("🙂");
            }

            if (longPressTriggered) {
                e.preventDefault();
                return;
            }

            if (this.longPressTimer) {
                // Short tap (finger lifted before 380ms)
                clearTimeout(this.longPressTimer);
                this.longPressTimer = null;

                if (!touchMoved) {
                    e.preventDefault(); // Suppress synthetic 300ms delayed click
                    if (this.boardData && this.boardData.grid && this.boardData.grid[r]) {
                        const cellData = this.boardData.grid[r][c];
                        if (cellData.state === 0) {
                            this.onCellClick(r, c);
                        }
                    }
                }
            }
        });
    }

    onCellClick(r, c) {
        if (!this.boardData || this.boardData.game_state === "LOST" || this.boardData.game_state === "WON") {
            return;
        }

        const res = window.pyodideBridge.click(r, c);
        if (!res || res.status === "IGNORED") return;

        this.startTimer();
        this.boardData = res.board;

        if (res.status === "PUNISHED") {
            this.stopTimer();
            this.setFace("💀");
            window.soundEffects.playExplosion();
            this.showPostMortem(res);
        } else if (res.status === "SAFE_MOVE" || res.status === "FORCED_SAFE" || res.status === "FIRST_CLICK") {
            if (this.boardData.game_state === "WON") {
                this.stopTimer();
                this.setFace("😎");
                window.soundEffects.playWin();
            } else {
                if (res.revealed && res.revealed.length > 1) {
                    window.soundEffects.playCascade();
                } else {
                    window.soundEffects.playClick();
                }
            }
        }

        this.renderBoard();
        this.updateHUD();
    }

    onCellFlag(r, c) {
        if (!this.boardData || this.boardData.game_state === "LOST" || this.boardData.game_state === "WON") {
            return;
        }

        const res = window.pyodideBridge.flag(r, c);
        if (res && res.success) {
            this.boardData = res.board;
            window.soundEffects.playFlag();
            this.renderBoard();
            this.updateHUD();
        }
    }

    onCellChord(r, c) {
        if (!this.boardData || this.boardData.game_state !== "IN_PROGRESS") {
            return;
        }

        const res = window.pyodideBridge.chord(r, c);
        if (!res || res.status === "NO_OP") return;

        this.boardData = res.board;
        if (res.status === "PUNISHED") {
            this.stopTimer();
            this.setFace("💀");
            window.soundEffects.playExplosion();
            this.showPostMortem(res);
        } else {
            if (this.boardData.game_state === "WON") {
                this.stopTimer();
                this.setFace("😎");
                window.soundEffects.playWin();
            } else {
                window.soundEffects.playCascade();
            }
        }

        this.renderBoard();
        this.updateHUD();
    }

    undoMove() {
        if (!this.boardData) return;
        const res = window.pyodideBridge.undo();
        if (res && res.success) {
            this.boardData = res.board;
            window.soundEffects.playUndo();
            this.hidePostMortem();
            if (this.boardData.game_state === "IN_PROGRESS") {
                this.setFace("🙂");
            }
            this.renderBoard();
            this.updateHUD();
        }
    }

    showPostMortem(res) {
        this.postMortemCard.style.display = "flex";
        const missed = res.missed_safe_cell;
        const clicked = res.clicked;
        this.postMortemText.innerHTML = `
            You clicked unproven tile <strong>(${clicked.r + 1}, ${clicked.c + 1})</strong>. 
            However, tile <strong style="color: var(--accent-emerald);">(${missed.r + 1}, ${missed.c + 1})</strong> was 100% logically guaranteed safe!<br>
            <span style="color: var(--accent-cyan); font-size: 0.88rem; display: inline-block; margin-top: 4px;">
                💡 Logic: ${res.explanation}
            </span>
        `;
    }

    hidePostMortem() {
        this.postMortemCard.style.display = "none";
    }

    updateHUD() {
        if (!this.boardData) return;
        const remaining = Math.max(-99, Math.min(999, this.boardData.mines_remaining));
        this.mineCountEl.textContent = String(remaining).padStart(3, "0");
        this.footerUndoBtn.style.opacity = this.boardData.can_undo ? "1" : "0.4";
        this.footerUndoBtn.style.pointerEvents = this.boardData.can_undo ? "auto" : "none";
    }
}

window.minesweeperApp = new MinesweeperGame();
