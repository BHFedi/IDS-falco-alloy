#!/usr/bin/env python3
"""
Rules Sync Server – Polls analyser API and writes Falco rules.
Also accepts webhook POST to trigger immediate sync.
"""
import os
import time
import logging
import hashlib
import threading
from pathlib import Path

import requests
from flask import Flask, request, jsonify

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("rules-sync")

def get_env_var(name):
    """Return value from ENV VAR or _FILE variant."""
    file_var = os.environ.get(f"{name}_FILE")
    if file_var and os.path.exists(file_var):
        with open(file_var, 'r') as f:
            return f.read().strip()
    return os.environ.get(name)

# Configuration
ANALYSER_URL = os.environ.get("ANALYSER_URL", "http://analyser:5000")
RULES_API_KEY = get_env_var("RULES_API_KEY") or ""
WEBHOOK_API_KEY = get_env_var("WEBHOOK_API_KEY") or ""
SYNC_INTERVAL = int(os.environ.get("SYNC_INTERVAL_SECONDS", 60))
RULES_OUTPUT_PATH = Path(os.environ.get("RULES_OUTPUT_PATH", "/etc/falco/rules.d/falco_threatintel_rules.yaml"))

# Global state
current_hash = None
sync_trigger = threading.Event()

def fetch_and_update_rules():
    """Fetch rules from analyser, write to disk if changed."""
    global current_hash
    headers = {}
    if RULES_API_KEY:
        headers["X-API-Key"] = RULES_API_KEY

    try:
        resp = requests.get(f"{ANALYSER_URL}/api/rules/falco", headers=headers, timeout=30)
        if resp.status_code != 200:
            logger.warning(f"Analyser returned {resp.status_code}, skipping update")
            return
        new_content = resp.text
        new_hash = hashlib.sha256(new_content.encode()).hexdigest()
        if new_hash == current_hash:
            logger.debug("Rules unchanged, skipping write")
            return

        RULES_OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        RULES_OUTPUT_PATH.write_text(new_content, encoding='utf-8')
        current_hash = new_hash
        logger.info(f"Rules updated (hash {new_hash[:8]}) -> {RULES_OUTPUT_PATH}")
    except Exception as e:
        logger.error(f"Failed to fetch/update rules: {e}")

def poll_loop():
    while True:
        fetch_and_update_rules()
        sync_trigger.wait(SYNC_INTERVAL)
        sync_trigger.clear()

@app.route('/webhook', methods=['POST'])
def webhook():
    if WEBHOOK_API_KEY:
        provided = request.headers.get('X-API-Key')
        if not provided or provided != WEBHOOK_API_KEY:
            return jsonify({'error': 'Unauthorized'}), 401
    logger.info("Webhook received – triggering immediate sync")
    sync_trigger.set()
    return '', 204

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok'}), 200

if __name__ == '__main__':
    fetch_and_update_rules()
    thread = threading.Thread(target=poll_loop, daemon=True)
    thread.start()
    app.run(host='0.0.0.0', port=5002)
