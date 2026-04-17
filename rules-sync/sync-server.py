#!/usr/bin/env python3
"""
Rules Sync Server – Polls analyser API and writes Falco rules.
Also accepts:
  POST /webhook         – lightweight trigger (existing behaviour, pull-based)
  POST /push-rules      – direct push from analyser (new, push-based)
  GET  /health          – liveness check
"""
import os
import time
import logging
import hashlib
import threading
from pathlib import Path

import requests
from flask import Flask, request, jsonify
from datetime import datetime, timezone

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 2 * 1024 * 1024
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("rules-sync")


def get_env_var(name):
    """Return value from ENV VAR or _FILE variant."""
    file_var = os.environ.get(f"{name}_FILE")
    if file_var and os.path.exists(file_var):
        with open(file_var, 'r') as f:
            return f.read().strip()
    return os.environ.get(name)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
ANALYSER_URL    = os.environ.get("ANALYSER_URL", "http://analyser:5000")
RULES_API_KEY   = get_env_var("RULES_API_KEY")   or ""
WEBHOOK_API_KEY = get_env_var("WEBHOOK_API_KEY") or ""
SYNC_INTERVAL   = int(os.environ.get("SYNC_INTERVAL_SECONDS", 60))
RULES_OUTPUT_PATH = Path(
    os.environ.get("RULES_OUTPUT_PATH",
                   "/etc/falco/rules.d/falco_threatintel_rules.yaml")
)

# ---------------------------------------------------------------------------
# Global state
# ---------------------------------------------------------------------------
current_hash  = None
sync_trigger  = threading.Event()
last_sync_ts  = None          # ISO timestamp of the last successful write
last_sync_ok  = True          # False after a failed fetch


# ---------------------------------------------------------------------------
# Core rule-writing logic
# ---------------------------------------------------------------------------

def _write_rules(content: str) -> bool:
    """
    Write *content* to disk if it differs from what's already there.
    Returns True if the file was updated, False if unchanged.
    Raises on I/O error.
    """
    global current_hash, last_sync_ts, last_sync_ok

    new_hash = hashlib.sha256(content.encode()).hexdigest()
    if new_hash == current_hash:
        logger.debug("Rules unchanged (hash %s), skipping write", new_hash[:8])
        return False
    try:
        RULES_OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        RULES_OUTPUT_PATH.write_text(content, encoding='utf-8')
    except PermissionError as e:
        logger.error(f"Permission denied writing to {RULES_OUTPUT_PATH}: {e}")
        raise
    except OSError as e:
        logger.error(f"OS error writing to {RULES_OUTPUT_PATH}: {e}")
        raise

    current_hash = new_hash

    last_sync_ts = datetime.now(timezone.utc).isoformat()
    last_sync_ok = True

    logger.info("Rules updated (hash %s) → %s", new_hash[:8], RULES_OUTPUT_PATH)
    return True


# ---------------------------------------------------------------------------
# Pull-based sync (original behaviour)
# ---------------------------------------------------------------------------

def fetch_and_update_rules():
    """Fetch rules from analyser, write to disk if changed."""
    global last_sync_ok
    headers = {}
    if RULES_API_KEY:
        headers["X-API-Key"] = RULES_API_KEY

    try:
        resp = requests.get(
            f"{ANALYSER_URL}/api/rules/falco",
            headers=headers,
            timeout=30,
        )
        if resp.status_code != 200:
            logger.warning("Analyser returned %s, skipping update", resp.status_code)
            last_sync_ok = False
            return
        _write_rules(resp.text)
    except Exception as e:
        logger.error("Failed to fetch/update rules: %s", e)
        last_sync_ok = False


def poll_loop():
    while True:
        fetch_and_update_rules()
        sync_trigger.wait(SYNC_INTERVAL)
        sync_trigger.clear()


# ---------------------------------------------------------------------------
# Flask routes
# ---------------------------------------------------------------------------

def _check_auth():
    """Return None if auth passes, or a (response, status) tuple to return."""
    if not WEBHOOK_API_KEY:
        return None
    provided = request.headers.get("X-API-Key")
    if not provided or provided != WEBHOOK_API_KEY:
        return jsonify({"error": "Unauthorized"}), 401
    return None


@app.route('/push-rules', methods=['POST'])
def push_rules():
    """
    Receive rules content directly from the analyser (push model).
    The body must be the raw YAML rules text.
    Auth: X-API-Key header (same WEBHOOK_API_KEY secret).
    """
    auth_err = _check_auth()
    if auth_err:
        return auth_err

    client_ip = request.remote_addr or "unknown"
    content = request.get_data(as_text=True)
    content_len = len(content)

    logger.info(f"Received push-rules ({content_len} bytes) from {client_ip}")

    if not content or not content.strip():
        return jsonify({"error": "Empty body"}), 400

    try:
        updated = _write_rules(content)
        return jsonify({"updated": updated}), 200
    except Exception as e:
        logger.error("Failed to write pushed rules: %s", e)
        return jsonify({"error": str(e)}), 500


@app.route('/webhook', methods=['POST'])
def webhook():
    """Trigger an immediate pull-sync cycle."""
    auth_err = _check_auth()
    if auth_err:
        return auth_err

    client_ip = request.remote_addr or "unknown"
    logger.info(f"Received webhook trigger from {client_ip}")

    sync_trigger.set()
    return '', 204


@app.route('/health', methods=['GET'])
def health():
    return jsonify({
        "status":            "ok",
        "last_sync":         last_sync_ts,
        "last_sync_ok":      last_sync_ok,
        "rules_path":        str(RULES_OUTPUT_PATH),
        "analyser_url":      ANALYSER_URL,
        "current_rules_hash": current_hash[:16] if current_hash else None,
        "sync_interval":     SYNC_INTERVAL,
    }), 200


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    fetch_and_update_rules()
    thread = threading.Thread(target=poll_loop, daemon=True)
    thread.start()
    app.run(host='0.0.0.0', port=5002)
