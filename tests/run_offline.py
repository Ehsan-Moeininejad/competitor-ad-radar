"""Offline end-to-end test: serves fixture pages instead of the internet, no LLM, no email.
Usage: python tests/run_offline.py   (writes into data/ and docs/; delete them afterwards)"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "radar"))
os.environ["RADAR_FIXTURES"] = str(ROOT / "tests" / "fixtures")
os.environ["FORCE_SCAN"] = "true"
os.environ["FORCE_REPORT"] = "true"
for k in ("GITHUB_TOKEN", "GEMINI_API_KEY", "OPENROUTER_API_KEY", "GROQ_API_KEY", "SMTP_USER"):
    os.environ.pop(k, None)

import publishers  # noqa: E402
import main  # noqa: E402

publishers.read_sheet = lambda: [{"domain": "zoomit.ir", "source": "sheet", "category": "tech", "sheet_tier": 30, "pages": []},
                                 {"domain": "varzesh3.com", "source": "sheet", "category": "sports", "sheet_tier": 90, "pages": []}]
publishers.select_for_run = lambda reg: [reg["zoomit.ir"], reg["varzesh3.com"]]
publishers._tranco_ir = lambda known: ({}, {})
sys.argv = ["main.py", "auto"]
main.main()
