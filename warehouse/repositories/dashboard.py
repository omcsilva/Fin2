"""Parameterized read-only queries. One connection per request, no migrations."""
from contextlib import contextmanager
import duckdb
from warehouse.database import WRITE_LOCK


class Unavailable(Exception):
    pass


@contextmanager
def reader(path):
    with WRITE_LOCK:
        if not path.is_file():
            raise Unavailable("Warehouse not initialized")
        try:
            connection = duckdb.connect(str(path), read_only=True)
        except duckdb.Error as error:
            raise Unavailable("Warehouse unavailable") from error
        try:
            yield connection
        except duckdb.Error as error:
            raise Unavailable("Warehouse schema unavailable") from error
        finally:
            connection.close()


def query(connection, sql, parameters=()):
    cursor = connection.execute(sql, parameters)
    names = [col[0] for col in cursor.description]
    return [dict(zip(names, row)) for row in cursor.fetchall()]
