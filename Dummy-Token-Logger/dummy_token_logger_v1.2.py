from flask import Flask, render_template
from flask_socketio import SocketIO
from playwright.sync_api import sync_playwright
from urllib.parse import urlparse
from threading import Event

app = Flask(__name__)

# Flask-SocketIO using threading mode so Playwright can run safely
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

# Shared flag for cancel action
cancel_flag = Event()

# -----------------------------
# Helper functions
# -----------------------------
def emit_log(msg, delay=0.0):
    """Emit a console log line; optional async delay."""
    socketio.emit("log", {"message": msg})
    if delay:
        socketio.sleep(delay)

def emit_progress(percent):
    """Send progress percentage safely between 0–100."""
    socketio.emit("progress", {"percent": int(max(0, min(100, percent)))})

def _safe_url(u: str) -> bool:
    """Simple URL safety check."""
    try:
        p = urlparse(u)
        return p.scheme in ("http", "https") and bool(p.netloc)
    except Exception:
        return False

# -----------------------------
# Main demo logic (with cancel)
# -----------------------------
def demo_sequence():
    """Demo automation with cancel support."""
    urls = [
        ("Example Domain", "https://example.com"),
        ("Python.org", "https://www.python.org"),
        ("Wikipedia", "https://www.wikipedia.org"),
        ("Google", "https://www.google.com"),
    ]
    urls = [(n, u) for (n, u) in urls if _safe_url(u)]
    total = len(urls)

    emit_log("[PLAYWRIGHT] Launching visible Chromium browser...", 0.5)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()

        for i, (name, url) in enumerate(urls, start=1):
            if cancel_flag.is_set():
                emit_log("[CANCEL] Run aborted by user before visiting next site.", 0.2)
                break

            step_start = int(((i - 1) / total) * 100)
            step_end = int((i / total) * 100)

            emit_log(f"[STEP {i}] Visiting {name} ...", 0.2)
            page.goto(url)
            emit_log(f"[OPENED] {url}", 0.1)
            emit_progress(max(step_start, min(step_end - 5, 95)))

            # Perform a small custom action on Google
            if "google.com" in url and not cancel_flag.is_set():
                emit_log("[ACTION] Typing into the Google search bar...", 0.1)
                try:
                    search_box = page.locator("textarea[name='q']")
                    search_box.click()
                    search_box.type("this is just a test", delay=100)
                    emit_log("[DONE] Typed text without submitting.", 0.2)
                except Exception as e:
                    emit_log(f"[ERROR] Google typing failed: {e}")

            # Simulate human observation with cancel check
            for t in range(3):
                if cancel_flag.is_set():
                    emit_log("[CANCEL] Stopping midway...", 0.2)
                    break
                emit_log(f"[WAIT] Observing content... {t+1}/3")
                frac = (t + 1) / 3
                emit_progress(step_start + int((step_end - step_start) * frac))
                socketio.sleep(0.9)

            if cancel_flag.is_set():
                break

        emit_log("[CLEANUP] Closing browser window...", 0.3)
        browser.close()

    if cancel_flag.is_set():
        emit_log("[SYS] Playwright run cancelled.", 0.2)
        emit_progress(0)
        cancel_flag.clear()
    else:
        emit_progress(100)
        emit_log("[DONE] Demo sequence completed ✅", 0.2)

# -----------------------------
# Wrapper for initial dummy logs
# -----------------------------
def dummy_log_sequence():
    """Simulated boot logs + demo sequence."""
    if cancel_flag.is_set():
        cancel_flag.clear()

    intro = [
        "[INFO] Initializing dummy token logger...",
        "[BOOT] Loading environment variables...",
        "[SYS] Connection established.",
        "[OK] Starting Playwright page demo..."
    ]
    for line in intro:
        emit_log(line, 0.25)
        if cancel_flag.is_set():
            emit_log("[CANCEL] User aborted before Playwright started.", 0.2)
            return

    demo_sequence()

    if not cancel_flag.is_set():
        outro = [
            "[SYS] Performing cleanup...",
            "[OK] Demo sequence complete.",
            "[EXIT] All systems normal. Goodbye."
        ]
        for line in outro:
            emit_log(line, 0.2)

# -----------------------------
# SocketIO Events
# -----------------------------
@socketio.on("start_logger")
def handle_start_logger(data=None):
    """Triggered when the user presses Run."""
    emit_log("[SYS] Starting Playwright demo...")
    socketio.emit("status", {"running": True})
    socketio.start_background_task(dummy_log_sequence)
    return {"status": "started"}

@socketio.on("cancel_run")
def handle_cancel_run():
    """Triggered when the user presses Cancel."""
    emit_log("[SYS] Cancel signal received.")
    cancel_flag.set()
    socketio.emit("status", {"running": False})

# -----------------------------
# Flask routes
# -----------------------------
@app.route("/")
def home():
    return render_template("index.html")

@app.route("/demo")
def demo():
    return render_template("demo.html")

# -----------------------------
# Entrypoint
# -----------------------------
if __name__ == "__main__":
    print("🚀 Dummy Token Logger v1.3 running at http://127.0.0.1:5000")
    socketio.run(app, host="0.0.0.0", port=5000, debug=True, allow_unsafe_werkzeug=True)
