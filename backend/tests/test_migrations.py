import os
import shutil
import subprocess
import sys
from pathlib import Path
from uuid import uuid4


def test_alembic_upgrade_head_runs_on_sqlite():
    runtime_dir = Path(__file__).resolve().parents[1] / ".test-runtime" / f"alembic-{uuid4().hex}"
    runtime_dir.mkdir(parents=True, exist_ok=False)
    db_path = runtime_dir / "alembic_test.db"
    env = os.environ.copy()
    env["GEMINI_API_KEY"] = env.get("GEMINI_API_KEY", "test-dummy-key")
    env["DATABASE_URL"] = f"sqlite+aiosqlite:///{db_path}"
    env["DEMO_MODE"] = "false"
    env["AUTH_ENABLED"] = "false"

    try:
        result = subprocess.run(
            [sys.executable, "-m", "alembic", "-c", "alembic.ini", "upgrade", "head"],
            cwd=os.path.dirname(os.path.dirname(__file__)),
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )

        assert result.returncode == 0, result.stderr
        assert db_path.exists()
    finally:
        shutil.rmtree(runtime_dir, ignore_errors=True)
