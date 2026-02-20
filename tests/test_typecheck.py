import subprocess
import sys


def test_ty_check():
    result = subprocess.run([sys.executable, "-m", "ty", "check"], capture_output=True, text=True)
    assert result.returncode == 0, f"ty check failed:\n{result.stdout}\n{result.stderr}"
