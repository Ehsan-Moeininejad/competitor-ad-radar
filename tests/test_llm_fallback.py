"""Checks the 'busy or timeout → next model' rule with a fake HTTP layer."""
import os, sys, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "radar"))
os.environ.update({"GITHUB_TOKEN": "x", "GROQ_API_KEY": "y", "LLM_CHAIN": "github,groq"})
import requests, llm

calls = []
class R:
    def __init__(s, code, body): s.status_code, s._b, s.text, s.headers = code, body, json.dumps(body), {}
    def json(s): return s._b
def fake_post(url, headers=None, json=None, timeout=None, allow_redirects=True, params=None):
    m = json["model"]; calls.append(m)
    if m == "openai/gpt-4.1-mini": return R(429, {"error": "busy"})
    if m == "openai/gpt-4o-mini": raise requests.Timeout("slow")
    if "github" in url: return R(503, {"error": "down"})
    return R(200, {"choices": [{"message": {"content": '```json\n{"ok": true, "model": "%s"}\n```' % m}}]})
requests.post = fake_post
c = llm.LLM()
out = c.json("sys", "user")
print("order tried:", calls)
print("result:", out, "| used:", c.summary)
assert out["ok"] and out["model"] == "llama-3.3-70b-versatile"
# second call: failing models are pushed to the back after 2 failures
calls.clear(); c.json("sys", "user"); calls.clear(); out = c.json("sys", "user")
print("third call order:", calls)
assert calls[0] == "llama-3.3-70b-versatile"
print("OK")
