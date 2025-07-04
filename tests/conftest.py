import pytest
from unittest.mock import patch


@pytest.fixture(autouse=True)
def mock_send_mail_task(monkeypatch):
    class MockTask:
        def delay(self, *args, **kwargs):
            return None

    with patch('backend.tasks.send_mail_task', new=MockTask()):
        yield
