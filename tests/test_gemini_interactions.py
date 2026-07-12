import json
from types import SimpleNamespace

from app.services import ai_chat


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


def test_interactions_response_parsing(monkeypatch):
    monkeypatch.setattr(ai_chat, "settings", SimpleNamespace(gemini_api_key="A" * 30))
    seen = {}

    def fake_urlopen(req, timeout):
        seen["url"] = req.full_url
        seen["headers"] = dict(req.header_items())
        seen["payload"] = json.loads(req.data.decode("utf-8"))
        return FakeResponse(
            {
                "status": "completed",
                "steps": [
                    {
                        "type": "model_output",
                        "content": [{"type": "text", "text": "الاتصال يعمل"}],
                    }
                ],
            }
        )

    monkeypatch.setattr(ai_chat.urllib.request, "urlopen", fake_urlopen)
    result = ai_chat._post_gemini(
        "gemini-3.5-flash",
        "system",
        [{"role": "user", "parts": [{"text": "hello"}]}],
        {"temperature": 0.2, "maxOutputTokens": 100},
    )
    assert result.ok is True
    assert result.text == "الاتصال يعمل"
    assert seen["url"].endswith("/interactions")
    assert seen["payload"]["store"] is False
    assert seen["payload"]["model"] == "gemini-3.5-flash"
