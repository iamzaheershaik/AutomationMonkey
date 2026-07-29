"""Pytest configuration and shared fixtures."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.database import Base


@pytest.fixture(scope="session")
def engine():
    """Session-scoped in-memory SQLite engine for tests."""
    eng = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=eng)
    yield eng
    Base.metadata.drop_all(bind=eng)


@pytest.fixture
def session(engine):
    """Function-scoped database session with rollback."""
    Session = sessionmaker(bind=engine)
    s = Session()
    yield s
    s.rollback()
    s.close()
