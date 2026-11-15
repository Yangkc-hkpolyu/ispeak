from dataclasses import replace

from fastapi.testclient import TestClient

from backend.speaking.app import create_app
from backend.speaking.config import Settings
from backend.speaking.provider import ProviderError


class FakeConsultProvider:
    def __init__(self):
        self.calls = []
        self.fail = False

    async def complete(self, system, data, **options):
        self.calls.append((system, data, options))
        if self.fail:
            raise ProviderError("The API key or model access is unavailable. Bearer sample-secret")
        return "Start with a short daily speaking plan."


def test_consult_preserves_context_and_uses_configured_model(tmp_path):
    provider = FakeConsultProvider()
    settings = replace(Settings(), runtime=tmp_path, api_key="sample-secret", chat_model="test-model")
    app = create_app(settings=settings, provider=provider)
    messages = [{"role": "user", "content": "How should I prepare?"},
                {"role": "assistant", "content": "What exam?"},
                {"role": "user", "content": "IELTS speaking."}]
    with TestClient(app) as client:
        result = client.post("/api/speaking/consult", json={"messages": messages, "exam": "ielts"})
    assert result.status_code == 200
    assert result.json() == {"reply": "Start with a short daily speaking plan.", "model": "test-model"}
    system, payload, options = provider.calls[0]
    assert payload["messages"] == messages
    assert payload["exam"] == "ielts" and payload["task"] == "exam_preparation_consultation"
    assert options["json_mode"] is False
    assert "not claim" in system.lower()
    assert "sample-secret" not in result.text


def test_consult_rejects_invalid_history_and_redacts_provider_error(tmp_path):
    provider = FakeConsultProvider()
    settings = replace(Settings(), runtime=tmp_path, api_key="sample-secret")
    app = create_app(settings=settings, provider=provider)
    with TestClient(app) as client:
        assert client.post("/api/speaking/consult", json={"messages": []}).status_code == 422
        assert client.post("/api/speaking/consult", json={"messages": [{"role": "system", "content": "test"}]}).status_code == 422
        assert client.post("/api/speaking/consult", json={"messages": [{"role": "assistant", "content": "test"}]}).status_code == 422
        assert client.post("/api/speaking/consult", json={"messages": [{"role": "user", "content": "  "}]}).status_code == 422
        assert client.post("/api/speaking/consult", json={"messages": [{"role": "user", "content": "x" * 4001}]}).status_code == 422
        assert client.post("/api/speaking/consult", json={"messages": [{"role": "user", "content": "ok"}]}, headers={"Origin": "https://foreign.example"}).status_code == 403
        provider.fail = True
        result = client.post("/api/speaking/consult", json={"messages": [{"role": "user", "content": "hello"}]})
    assert result.status_code == 502
    assert "sample-secret" not in result.text
    assert "[redacted]" in result.text
