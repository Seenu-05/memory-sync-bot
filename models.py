from sqlalchemy import Column, BigInteger, Integer, String, DateTime
from database import Base
import datetime

class Memory(Base):

    __tablename__ = "memories"

    id = Column(Integer, primary_key = True, index = True)
    user_id = Column(BigInteger, index = True)
    memory_type = Column(String, nullable = True)
    encrypted_text = Column(String, nullable = False)
    created_at = Column(DateTime, default = datetime.datetime.utcnow)

class User(Base):

    __tablename__ = "users"

    telegram_id = Column(BigInteger, primary_key = True, index = True)
    partner_id = Column(BigInteger, index = True, nullable = True)

class DeadLetter(Base):
    __tablename__ = "dead_letters"

    id = Column(Integer, primary_key=True, index=True)
    chat_id = Column(BigInteger, index=True)
    payload = Column(String, nullable=False)
    error_reason = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)