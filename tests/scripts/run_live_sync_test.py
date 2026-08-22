#!/usr/bin/env python3
import json
import sys
from pathlib import Path

# Ensure repo root is on sys.path so we can import agenda when running from /scripts
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import agenda
import subprocess
import argparse

print("Starting live sync diagnostic for recurring events")

# Allow running the Playwright e2e test via --run-playwright
parser = argparse.ArgumentParser(description="Run live sync diagnostics or e2e popup test")
parser.add_argument("--run-playwright", action="store_true", help="Run the Playwright popup E2E test (headless)")
args = parser.parse_args()

if args.run_playwright:
    test_script = Path(__file__).resolve().parent / "test_sync_popup_playwright.py"
    if not test_script.exists():
        print(f"Test script not found: {test_script}")
        raise SystemExit(1)
    print("Running Playwright E2E test (headless)...")
    subprocess.check_call([sys.executable, str(test_script)])
    raise SystemExit(0)

# Diagnostic: list recurring events and google_id state
recurring = [e for e in agenda.carregar() if e.get("repeat")]
print(f"Found {len(recurring)} recurring local event(s)")
for e in recurring:
    print(f"- id={e['id']} titulo={e.get('titulo')} inicio={e.get('inicio')} repeat={e.get('repeat')} until={e.get('until')} google_id={e.get('google_id')}")

if agenda.GOOGLE_AVAILABLE:
    try:
        service = agenda.get_google_service()
        print("\nVerifying Google event series for recurring events with google_id...")
        for e in recurring:
            gid = e.get("google_id")
            if not gid:
                print(f"  id={e['id']} sem google_id -> precisa exportar")
                continue
            try:
                ge = service.events().get(calendarId=agenda.GOOGLE_CALENDAR_ID, eventId=gid).execute()
                print(f"  id={e['id']} google_id={gid} exists: recurrence={ge.get('recurrence')} status={ge.get('status')}")
            except Exception as ex:
                print(f"  id={e['id']} google_id={gid} lookup failed: {type(ex).__name__} {ex}")
    except Exception as ex:
        print(f"Erro ao verificar eventos do Google: {ex}")

print("\nRunning agenda.sync_all_with_progress()")
msgs = []

def on_progress(msg):
    print("PROGRESS:", msg)
    msgs.append(msg)

result = agenda.sync_all_with_progress(on_progress)

print("FINAL RESULT:")
print(json.dumps({"status": result[0], "exportados": result[1], "importados": result[2]}, ensure_ascii=False, indent=2))
