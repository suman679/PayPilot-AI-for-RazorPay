import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import User
from app.seed import CATALOG
from app.models import Product


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    for p in CATALOG:
        session.add(Product(**p))
    session.add(User(id="user_test", name="Test User", email="test@example.com"))
    session.commit()
    try:
        yield session
    finally:
        session.close()
