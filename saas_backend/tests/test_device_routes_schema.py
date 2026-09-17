from sqlalchemy import inspect

from linx.db.base import engine


def test_device_routes_table_has_expected_columns():
    columns = {
        column["name"]
        for column in inspect(engine).get_columns("device_routes")
    }
    assert {
        "id",
        "dev_eui",
        "app_id",
        "agent_endpoint",
        "created_at",
        "updated_at",
    } <= columns


def test_device_routes_dev_eui_is_not_nullable():
    columns = {
        column["name"]: column
        for column in inspect(engine).get_columns("device_routes")
    }
    assert columns["dev_eui"]["nullable"] is False
    assert columns["app_id"]["nullable"] is False
    assert columns["agent_endpoint"]["nullable"] is True


def test_device_routes_dev_eui_has_unique_index():
    indexes = [
        index
        for index in inspect(engine).get_indexes("device_routes")
        if index["column_names"] == ["dev_eui"]
    ]
    assert len(indexes) == 1
    assert indexes[0]["unique"] is True


def test_device_routes_app_id_has_index():
    indexes = [
        index
        for index in inspect(engine).get_indexes("device_routes")
        if index["column_names"] == ["app_id"]
    ]
    assert len(indexes) == 1
    assert indexes[0]["unique"] is False


def test_device_routes_app_id_foreign_key_targets_application():
    foreign_keys = [
        fk
        for fk in inspect(engine).get_foreign_keys("device_routes")
        if fk["constrained_columns"] == ["app_id"]
    ]
    assert len(foreign_keys) == 1
    assert foreign_keys[0]["referred_table"] == "application"
    assert foreign_keys[0]["referred_columns"] == ["id"]


def test_device_routes_app_id_foreign_key_cascades_on_delete():
    foreign_keys = [
        fk
        for fk in inspect(engine).get_foreign_keys("device_routes")
        if fk["constrained_columns"] == ["app_id"]
    ]
    assert len(foreign_keys) == 1
    assert foreign_keys[0]["options"].get("ondelete") == "CASCADE"
