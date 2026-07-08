from paper_agent.memory.repository import MemoryRepository


def test_memory_repository_creates_parent_directory(tmp_path):
    db_path = tmp_path / "nested" / "paper_agent.db"

    repo = MemoryRepository(db_path=db_path)

    assert db_path.exists()
    assert repo.get_user_memory("new-user")["preferred_language"] == "zh"
