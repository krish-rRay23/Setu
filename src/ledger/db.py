import os
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker, scoped_session

Base = declarative_base()

DEFAULT_DB_URL = os.getenv("DATABASE_URL", "sqlite:///ledger.db")


def get_engine(db_url: str = None):
    url = db_url or DEFAULT_DB_URL
    connect_args = {}
    if url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
        connect_args["timeout"] = 30
    engine = create_engine(url, connect_args=connect_args, echo=False)
    return engine


def init_db(engine=None, db_url: str = None):
    if engine is None:
        engine = get_engine(db_url)
    Base.metadata.create_all(bind=engine)
    return engine


def get_session_factory(engine):
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)
