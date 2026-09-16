from evals.groundtruth.generation.memory import fresh_memory_path


def test_fresh_memory_path_is_distinct_per_question(tmp_path):
    a = fresh_memory_path(tmp_path, "g-01")
    b = fresh_memory_path(tmp_path, "g-02")
    assert a != b
    assert a.name == "g-01.sqlite3"
    assert b.name == "g-02.sqlite3"


def test_fresh_memory_path_removes_an_existing_file(tmp_path):
    path = fresh_memory_path(tmp_path, "g-01")
    path.write_bytes(b"stale memory")
    result = fresh_memory_path(tmp_path, "g-01")
    assert result == path
    assert not result.exists()


def test_fresh_memory_path_lives_under_a_memory_subfolder_of_runtime_dir(tmp_path):
    path = fresh_memory_path(tmp_path, "oos-03")
    assert path.parent == tmp_path / "memory"


def test_fresh_memory_path_creates_the_memory_directory(tmp_path):
    fresh_memory_path(tmp_path, "g-01")
    assert (tmp_path / "memory").is_dir()
