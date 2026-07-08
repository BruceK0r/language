from fastapi.testclient import TestClient

from main import app


def test_root_page_points_to_demo_and_docs():
    client = TestClient(app)

    response = client.get("/")

    assert response.status_code == 200
    assert "Paper Radar Agent" in response.text
    assert "/docs" in response.text
    assert "8501" in response.text
