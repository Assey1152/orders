import os

POSTGRES_USER = os.getenv("POSTGRES_USER", "app")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", 1234)
POSTGRES_DB = os.getenv("POSTGRES_DB", "orders")
POSTGRES_HOST = os.getenv("POSTGRES_HOST", '127.0.0.1')
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")


PG_DSN = (f'postgresql+asyncpg://'
          f'{POSTGRES_USER}:{POSTGRES_PASSWORD}@'
          f'{POSTGRES_HOST}:{POSTGRES_PORT}/'
          f'{POSTGRES_DB}')
