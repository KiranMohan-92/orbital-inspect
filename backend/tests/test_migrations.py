import os
import subprocess
import sys


def test_alembic_upgrade_head_runs_on_sqlite(tmp_path):
    db_path = tmp_path / "alembic_test.db"
    env = os.environ.copy()
    env["GEMINI_API_KEY"] = env.get("GEMINI_API_KEY", "test-dummy-key")
    env["DATABASE_URL"] = f"sqlite+aiosqlite:///{db_path}"
    env["DEMO_MODE"] = "false"
    env["AUTH_ENABLED"] = "false"

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
