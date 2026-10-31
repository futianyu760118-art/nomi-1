import os
from pathlib import Path
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.engine import URL
from .models import Base, SchemaVersion


def database(url=None):
    folder = Path(__file__).resolve().parents[1] / "data"
    folder.mkdir(exist_ok=True)
    url = url or os.getenv("DATABASE_URL")
    if not url and os.getenv("MYSQL_HOST"):
        url = URL.create("mysql+pymysql", username=os.getenv("MYSQL_USER", "pmo"),
                         password=os.getenv("MYSQL_PASSWORD"), host=os.getenv("MYSQL_HOST"),
                         database=os.getenv("MYSQL_DATABASE", "pmo"), query={"charset": "utf8mb4"})
    url = url or "sqlite:///" + (folder / "pmo.db").as_posix()
    engine = create_engine(url, pool_pre_ping=True,
                           connect_args={"check_same_thread": False} if str(url).startswith("sqlite") else {})
    # Initial, versioned migration. Future revisions go in migrate() before advancing version.
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    with sessions() as db:
        version = db.scalar(select(SchemaVersion.version).order_by(SchemaVersion.version.desc()).limit(1))
        if version is None:
            db.add(SchemaVersion(version=1))
            db.commit()
        elif version != 1:
            raise RuntimeError("Unsupported database schema version")
    return engine, sessions
