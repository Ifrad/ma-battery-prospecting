import pytest

from prospect.migrate import MIGRATIONS, pending


def write(directory, *names):
    for name in names:
        (directory / name).write_text("SELECT 1;")


def test_pending_in_number_order_skipping_applied(tmp_path):
    write(tmp_path, "0002_b.sql", "0001_a.sql", "0010_c.sql")
    names = [p.stem for p in pending({"0001_a"}, tmp_path)]
    assert names == ["0002_b", "0010_c"]


def test_rejects_bad_names(tmp_path):
    write(tmp_path, "1_a.sql")
    with pytest.raises(ValueError, match="bad migration name"):
        pending(set(), tmp_path)


def test_rejects_duplicate_numbers(tmp_path):
    write(tmp_path, "0001_a.sql", "0001_b.sql")
    with pytest.raises(ValueError, match="duplicate"):
        pending(set(), tmp_path)


def test_repo_migrations_are_valid():
    assert pending(set(), MIGRATIONS)
