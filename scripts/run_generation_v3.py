"""Run the same engine on separately frozen, explicitly seen development cases."""

from pathlib import Path

import run_generation_v2 as runner

ROOT = Path(__file__).resolve().parents[1]
runner.PROTOCOL = ROOT / "reports/generation-v3/protocol.json"
runner.PUBLIC = ROOT / "reports/generation-v3/results.json"
runner.PRIVATE = ROOT / "outputs/generation-v3/raw.json"

if __name__ == "__main__":
    runner.run()
