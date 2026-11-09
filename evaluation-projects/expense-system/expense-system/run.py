import os
from app.main import create_app

if __name__ == "__main__":
    # Demo data is loaded on first start. Set SEED_DEMO=0 for an empty database.
    app = create_app(seed_demo=os.environ.get("SEED_DEMO", "1") == "1")
    app.run(host=os.environ.get("HOST", "127.0.0.1"), port=int(os.environ.get("PORT", 5000)))
