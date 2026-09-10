import pytest

from synapse.zeref_service import handle_request


class FakeManager:
    def status(self):
        return {"state": "READY", "runtime_ok": True}

    def doctor(self):
        return {"ok": True, "state": "READY"}

    def chat(self, message):
        return {"response": "echo:" + message, "native_trinity": {"native_enabled": True}}


def test_status_and_doctor_actions_are_bounded():
    manager = FakeManager()
    assert handle_request({"action": "status"}, manager)["state"] == "READY"
    assert handle_request({"action": "doctor"}, manager)["ok"] is True


def test_chat_requires_bounded_string_message():
    manager = FakeManager()
    assert handle_request({"action": "chat", "message": "hello"}, manager)["response"] == "echo:hello"
    with pytest.raises(ValueError, match="message"):
        handle_request({"action": "chat", "message": 42}, manager)
    with pytest.raises(ValueError, match="too large"):
        handle_request({"action": "chat", "message": "x" * 32769}, manager)


def test_unknown_action_is_rejected_not_executed():
    with pytest.raises(ValueError, match="unknown resident action"):
        handle_request({"action": "shell", "message": "id"}, FakeManager())
