"""
BI Dashboard AI - Single file launcher
Run: python run.py
"""
import subprocess, sys, os, time, signal, sqlite3, random, shutil
from datetime import datetime, timedelta

BASE = os.path.dirname(os.path.abspath(__file__))

# 1. Install deps
def install_deps():
    deps = ["fastapi","uvicorn","groq","pandas","numpy","streamlit","plotly","python-multipart","requests"]
    print("Installing dependencies...")
    subprocess.run([sys.executable, "-m", "pip", "install", *deps, "-q"], check=True)
    print("Dependencies ready.\n")

install_deps()
import requests

# 2. Copy pre-written backend and frontend files
BACKEND_TEMPLATE = os.path.join(BASE, "backend_template.py")
FRONTEND_TEMPLATE = os.path.join(BASE, "frontend_template.py")

os.makedirs(os.path.join(BASE, "backend"), exist_ok=True)
os.makedirs(os.path.join(BASE, "frontend"), exist_ok=True)
os.makedirs(os.path.join(BASE, "data"), exist_ok=True)

open(os.path.join(BASE, "backend", "__init__.py"), "w").close()
open(os.path.join(BASE, "frontend", "__init__.py"), "w").close()

if os.path.exists(BACKEND_TEMPLATE):
    shutil.copy(BACKEND_TEMPLATE, os.path.join(BASE, "backend", "main.py"))
    print("backend/main.py ready")
else:
    print("ERROR: backend_template.py not found next to run.py")
    sys.exit(1)

if os.path.exists(FRONTEND_TEMPLATE):
    shutil.copy(FRONTEND_TEMPLATE, os.path.join(BASE, "frontend", "app.py"))
    print("frontend/app.py ready")
else:
    print("ERROR: frontend_template.py not found next to run.py")
    sys.exit(1)

# 3. Start FastAPI
print("Starting FastAPI backend on port 8000...")
backend_proc = subprocess.Popen(
    [sys.executable, "-m", "uvicorn", "backend.main:app",
     "--host", "0.0.0.0", "--port", "8000", "--log-level", "info"],
    cwd=BASE
)

print("Waiting for backend...")
for _ in range(25):
    try:
        if requests.get("http://localhost:8000/health", timeout=1).status_code == 200:
            print("Backend ready at http://localhost:8000\n")
            break
    except Exception:
        pass
    time.sleep(1)

# 4. Start Streamlit
print("Starting Streamlit frontend...")
print("Open: http://localhost:8501\n")
print("Press Ctrl+C to stop.\n")

frontend_proc = subprocess.Popen(
    [sys.executable, "-m", "streamlit", "run",
     os.path.join(BASE, "frontend", "app.py"),
     "--server.port", "8501",
     "--server.address", "0.0.0.0",
     "--server.headless", "true",
     "--theme.base", "light",
     "--theme.primaryColor", "#4f46e5",
     "--theme.backgroundColor", "#f5f7fa",
     "--theme.secondaryBackgroundColor", "#ffffff",
     "--theme.textColor", "#1e293b"],
    cwd=BASE
)

def shutdown(sig, frame):
    print("\nShutting down...")
    frontend_proc.terminate()
    backend_proc.terminate()
    sys.exit(0)

signal.signal(signal.SIGINT, shutdown)
signal.signal(signal.SIGTERM, shutdown)
frontend_proc.wait()
