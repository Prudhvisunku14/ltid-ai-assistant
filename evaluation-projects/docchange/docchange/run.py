"""python run.py  -> dashboard on http://127.0.0.1:8000 (mock Drive by default).
Click "Scan all documents" in the UI (or run `python -m monitor.cli scan`) to build history."""
import os
from monitor import server
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    srv = server.build(db=os.environ.get("HISTORY_DB", "history.db"), port=port, host=os.environ.get("HOST", "127.0.0.1"))
    print(f"Dashboard: http://127.0.0.1:{port}  (source={os.environ.get('DRIVE_SOURCE', 'snapshot')}). Ctrl+C to stop.")
    srv.serve_forever()
