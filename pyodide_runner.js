/**
 * Pyodide WebAssembly Runner for Fair Minesweeper
 * Manages Python CPython runtime in the browser and exposes JS interface.
 */

class PyodideBridge {
    constructor() {
        this.pyodide = null;
        this.ready = false;
        this.onReadyCallback = null;
        this.onStatusUpdate = null;
    }

    async init(statusCallback) {
        this.onStatusUpdate = statusCallback;
        this._updateStatus("Loading WebAssembly Python engine...");

        try {
            // Load Pyodide script dynamically if not already present
            if (!window.loadPyodide) {
                await this._loadScript("https://cdn.jsdelivr.net/pyodide/v0.26.2/full/pyodide.js");
            }

            this._updateStatus("Initializing CPython in browser...");
            this.pyodide = await window.loadPyodide({
                indexURL: "https://cdn.jsdelivr.net/pyodide/v0.26.2/full/"
            });

            this._updateStatus("Mounting Fair Minesweeper logic engine...");
            await this._mountPythonFiles();

            // Setup bridge code
            await this.pyodide.runPythonAsync(`
import json
import sys
sys.path.insert(0, '/')
from fair_minesweeper.karma import KarmaEngine

_engine = KarmaEngine()

def py_new_game(width, height, num_mines):
    _engine.start_new_game(int(width), int(height), int(num_mines))
    return json.dumps(_engine.board.to_dict())

def py_click(r, c):
    res = _engine.handle_click(int(r), int(c))
    return json.dumps(res)

def py_flag(r, c):
    res = _engine.handle_flag(int(r), int(c))
    return json.dumps(res)

def py_chord(r, c):
    res = _engine.handle_chord(int(r), int(c))
    return json.dumps(res)

def py_undo():
    res = _engine.handle_undo()
    return json.dumps(res)
            `);

            this.ready = true;
            this._updateStatus("Engine ready!");
            if (this.onReadyCallback) {
                this.onReadyCallback();
            }
        } catch (err) {
            console.error("Pyodide initialization error:", err);
            this._updateStatus("Error loading Python engine: " + err.message);
            throw err;
        }
    }

    _updateStatus(msg) {
        if (this.onStatusUpdate) {
            this.onStatusUpdate(msg);
        }
    }

    _loadScript(src) {
        return new Promise((resolve, reject) => {
            const script = document.createElement("script");
            script.src = src;
            script.onload = () => resolve();
            script.onerror = () => reject(new Error("Failed to load script: " + src));
            document.head.appendChild(script);
        });
    }

    async _mountPythonFiles() {
        // Attempt to fetch from relative paths with aggressive cache-busting;
        // if fetch fails (e.g. file:// origin), fallback to embedded source code.
        const files = [
            "fair_minesweeper/__init__.py",
            "fair_minesweeper/board.py",
            "fair_minesweeper/solver.py",
            "fair_minesweeper/karma.py"
        ];

        this.pyodide.FS.mkdirTree("/fair_minesweeper");

        const cacheBuster = Date.now();
        for (const f of files) {
            let content = null;
            let loadedFrom = "unknown";

            try {
                const resp = await fetch(`${f}?_ts=${cacheBuster}`, {
                    cache: "no-store",
                    headers: {
                        "Cache-Control": "no-cache, no-store, must-revalidate",
                        "Pragma": "no-cache"
                    }
                });
                if (resp.ok) {
                    content = await resp.text();
                    loadedFrom = "network (cache-busted)";
                }
            } catch (e) {
                // Fetch failed (likely file:// origin or static restrictions)
            }

            if (!content && window.EMBEDDED_PYTHON_FILES) {
                content = window.EMBEDDED_PYTHON_FILES[f] || window.EMBEDDED_PYTHON_FILES[f.replace(/\//g, "\\")];
                if (content) {
                    loadedFrom = "embedded bundle";
                }
            }

            if (content) {
                this.pyodide.FS.writeFile("/" + f, content);
                console.log(`[PyodideBridge] Mounted ${f} (${content.length} bytes, from ${loadedFrom})`);
            } else {
                throw new Error("Unable to load python module: " + f);
            }
        }
    }

    newGame(w, h, m) {
        if (!this.ready) return null;
        const jsonStr = this.pyodide.runPython(`py_new_game(${w}, ${h}, ${m})`);
        return JSON.parse(jsonStr);
    }

    click(r, c) {
        if (!this.ready) return null;
        const jsonStr = this.pyodide.runPython(`py_click(${r}, ${c})`);
        return JSON.parse(jsonStr);
    }

    flag(r, c) {
        if (!this.ready) return null;
        const jsonStr = this.pyodide.runPython(`py_flag(${r}, ${c})`);
        return JSON.parse(jsonStr);
    }

    chord(r, c) {
        if (!this.ready) return null;
        const jsonStr = this.pyodide.runPython(`py_chord(${r}, ${c})`);
        return JSON.parse(jsonStr);
    }

    undo() {
        if (!this.ready) return null;
        const jsonStr = this.pyodide.runPython(`py_undo()`);
        return JSON.parse(jsonStr);
    }
}

window.pyodideBridge = new PyodideBridge();
