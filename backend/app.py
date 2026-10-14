import os
from waitress import serve
from pmo import create_app
from pmo.scheduler import start_scheduler

app = create_app()

if __name__ == "__main__":
    start_scheduler(app)
    serve(app, host=os.getenv("HOST", "127.0.0.1"), port=int(os.getenv("PORT", "5000")), threads=8)
