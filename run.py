import subprocess
import sys
import os
import time
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent

MAIN_FILE = ROOT / "main.py"
APP_FILE = ROOT / "app.py"

def run_process(cmd, name):
    return subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        universal_newlines=True,
        bufsize=1
    )

def stream_output(process, name):
    for line in process.stdout:
        print(f"[{name}] {line}", end="")

if __name__ == "__main__":
    print("🔧 Starting AI Service Desk…")


    env = os.environ.copy()

    # Start FastAPI backend
    print("🚀 Launching FastAPI backend (main.py) on http://localhost:8000 …")
    fastapi_proc = run_process(
        [sys.executable, str(MAIN_FILE)],
        "FastAPI"
    )

    time.sleep(2)

    # Start Streamlit frontend
    print("💬 Launching Streamlit UI (app.py) on http://localhost:8501 …")
    streamlit_proc = run_process(
        ["python", "-m", "streamlit", "run", str(APP_FILE)],
        "Streamlit"
    )

    try:
        while True:
            if fastapi_proc.poll() is not None:
                print("❌ FastAPI backend stopped!")
                break
            if streamlit_proc.poll() is not None:
                print("❌ Streamlit UI stopped!")
                break
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\n🛑 Shutting down processes…")
        fastapi_proc.terminate()
        streamlit_proc.terminate()
        print("Done.")
