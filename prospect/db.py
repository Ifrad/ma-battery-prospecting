"""Database connection, configured by the same variables as docker-compose.yml."""

import os

import psycopg


def connect(**kwargs) -> psycopg.Connection:
    return psycopg.connect(
        host=os.environ.get("DB_HOST", "127.0.0.1"),
        port=os.environ.get("DB_PORT", "5432"),
        user=os.environ.get("POSTGRES_USER", "prospect"),
        password=os.environ.get("POSTGRES_PASSWORD", "prospect"),
        dbname=kwargs.pop("dbname", os.environ.get("POSTGRES_DB", "prospect")),
        connect_timeout=5,
        **kwargs,
    )
