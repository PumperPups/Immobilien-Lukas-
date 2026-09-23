"""Der Claude-Code-Waechter (.claude/hooks/datenschutz.py) sperrt echte Daten."""

import json
import subprocess
import sys
import unittest
from pathlib import Path

HOOK = Path(__file__).resolve().parent.parent / ".claude" / "hooks" / "datenschutz.py"


def entscheidung(werkzeug: str, **eingabe) -> int:
    r = subprocess.run([sys.executable, str(HOOK)], input=json.dumps({"tool_name": werkzeug, "tool_input": eingabe}),
                       capture_output=True, text=True, timeout=20)
    return r.returncode


class HookTest(unittest.TestCase):
    def test_gesperrt(self):
        for werkzeug, eingabe in [
            ("Read", {"file_path": "/home/x/Hausverwaltung-Daten/verwaltung.db"}),
            ("Read", {"file_path": r"C:\Users\x\Hausverwaltung-Daten\bank\archiv\2026-10\umsatz.csv"}),
            ("Grep", {"pattern": "Miete", "path": "/home/x/Hausverwaltung-Daten"}),
            ("Bash", {"command": "python -m verwaltung monat"}),
            ("Bash", {"command": "sqlite3 ~/irgendwo/verwaltung.db .dump"}),
            ("Read", {"file_path": "/tmp/Stammdaten_2026.csv"}),
        ]:
            self.assertEqual(entscheidung(werkzeug, **eingabe), 2, eingabe)

    def test_erlaubt(self):
        for werkzeug, eingabe in [
            ("Read", {"file_path": "/p/daten_demo/bank/eingang/sparkasse_2026-09.csv"}),
            ("Bash", {"command": "python -m verwaltung --demo monat"}),
            ("Bash", {"command": "python3 -m unittest discover -s tests"}),
            ("Read", {"file_path": "/p/verwaltung/stammdaten.py"}),
            ("Write", {"file_path": "/p/docs/DATENSCHUTZ.md", "content": "~/Hausverwaltung-Daten/verwaltung.db"}),
        ]:
            self.assertEqual(entscheidung(werkzeug, **eingabe), 0, eingabe)


if __name__ == "__main__":
    unittest.main()
