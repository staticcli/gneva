"""Update ElevenLabs agent voice ID."""
import httpx
import json

API_KEY = "sk_f9f93edf18959721869c313a2ba237b09216086704f0648a"
AGENT_ID = "agent_1701kkgaeywtfamabqkm33781nvy"
NEW_VOICE_ID = "3gsg3cxXyFLcGIfNbM6C"

resp = httpx.patch(
    f"https://api.elevenlabs.io/v1/convai/agents/{AGENT_ID}",
    headers={
        "Content-Type": "application/json",
        "xi-api-key": API_KEY,
    },
    json={
        "conversation_config": {
            "tts": {
                "voice_id": NEW_VOICE_ID,
            },
        },
    },
    timeout=30,
)

print(f"Status: {resp.status_code}")
if resp.status_code == 200:
    print(f"Voice updated to {NEW_VOICE_ID}")
    print(json.dumps(resp.json(), indent=2)[:500])
else:
    print(resp.text)
