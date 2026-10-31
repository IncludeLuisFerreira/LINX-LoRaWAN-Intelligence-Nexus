from linx_shared.db.base import engine
from sqlalchemy import inspect


def test_device_routes_table_is_removed():
    assert inspect(engine).has_table("device_routes") is False
