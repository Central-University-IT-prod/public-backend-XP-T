import logging
import os

from dotenv import load_dotenv
from typing import Optional

from pydantic import BaseSettings

logging.basicConfig(level=logging.INFO, filename='logs.log', encoding='utf-8',
                    format='%(asctime)s %(levelname)s %(message)s')


load_dotenv()


class Settings(BaseSettings):
    """Класс общих настроек системы."""
    # asyncpg для postgres
    NAME = os.getenv('DB_NAME')
    USER = os.getenv('DB_USER')
    PASSWORD = os.getenv('DB_PASSWORD')
    HOST = os.getenv('DB_HOST')
    PORT = os.getenv('DB_PORT')
    telegram_token: str = os.getenv('TOKEN')

    database_url: str = 'sqlite+aiosqlite:///bot.db'
    #database_url: str = f'postgresql+asyncpg://{USER}:{PASSWORD}@{HOST}:{PORT}/{NAME}' # noqa
    id_key_yandex = 'secret'
    secret_key_yandex = 'secret'
    fsq_key = 'secret'
    min_password: int = 3
    type: Optional[str] = None

    class Config:
        env_file = '.env'


settings = Settings()

OSM_HEADERS = {
        'Accept-Language': 'ru-Ru'
    }

YANDEX_HEADERS = {
    'Authorization': 'secret',
    'x-folder-id': 'secret',
    'Content-Type': 'application/json'}

FSQ_HEADERS = {
        'Authorization': 'secret',
        'Accept': 'application/json',
    }
