import re

from sqlalchemy import Column, Integer
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import declarative_base, declared_attr, sessionmaker

from core.config import settings


class PreBase:
    """Класс базовой модели с переводом имени таблицы в snake_case"""

    @declared_attr
    def __tablename__(cls):
        snake_name = re.sub(r'(?<!^)(?=[A-Z])', '_', cls.__name__).lower()
        return f'{snake_name}s'

    id = Column(Integer, primary_key=True)


Base = declarative_base(cls=PreBase)
engine = create_async_engine(settings.database_url)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession)
