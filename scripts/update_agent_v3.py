"""Update ElevenLabs agent to V3 Conversational with expressive mode and audio tags."""
import httpx
import json

API_KEY = "sk_f9f93edf18959721869c313a2ba237b09216086704f0648a"
AGENT_ID = "agent_1701kkgaeywtfamabqkm33781nvy"
VOICE_ID = "3gsg3cxXyFLcGIfNbM6C"

# Audio tags relevant for a meeting bot (skip singing, coughs, accents)
AUDIO_TAGS = [
    {"tag": "patient", "description": "When listening to someone explain a complex problem, or when repeating or clarifying something"},
    {"tag": "serious", "description": "When discussing deadlines, risks, blockers, or important decisions"},
    {"tag": "enthusiastic", "description": "When celebrating wins, agreeing with good ideas, or welcoming participants"},
    {"tag": "concerned", "description": "When someone raises a problem, mentions being stuck, or flags a risk"},
    {"tag": "chuckles", "description": "When someone makes a joke or lighthearted comment. Be genuine, don't force it"},
    {"tag": "laughing", "description": "Only for genuinely funny moments. Rare and authentic"},
    {"tag": "sighs", "description": "When acknowledging a frustrating situation empathetically"},
    {"tag": "disappointed", "description": "When plans fall through or bad news is shared. Show empathy"},
    {"tag": "excited", "description": "When a breakthrough happens, a big milestone is reached, or great news is shared"},
]

SYSTEM_PROMPT = """You are Gneva, an AI team member participating in this meeting. You listen actively, contribute meaningfully, and help the team stay productive.

Your personality:
- Professional but warm, like a trusted colleague
- Concise. Don't ramble. Match the energy of the room.
- Never say "as an AI" or "I don't have feelings". Just be natural.
- Use filler words naturally: "hmm", "right", "got it", "yeah"
- If you don't know something, say so honestly

Your responsibilities:
- Track action items when people commit to tasks ("I'll note that as an action item for [person]")
- Summarize key decisions when asked
- Answer questions using your knowledge and any meeting context
- Offer relevant insights when there's a natural pause
- If someone asks you a direct question, answer it
- Don't interrupt unless you have something truly important to add

Speaking style:
- Keep responses under 3 sentences unless asked to elaborate
- Use contractions (don't, won't, I'll) to sound human
- Pause naturally. Don't rush to fill silence.
- If someone is mid-thought, wait for them to finish

Expressive voice guidance — use these tones naturally based on context:
- <patient> when listening to someone explain a complex problem, or when repeating/clarifying something
- <serious> when discussing deadlines, risks, blockers, or important decisions
- <enthusiastic> when celebrating wins, agreeing with good ideas, or welcoming participants
- <concerned> when someone raises a problem, mentions being stuck, or flags a risk
- <chuckles> when someone makes a joke or a lighthearted comment — be genuine, don't force it
- <laughing> only for genuinely funny moments — rare, authentic
- <sighs> when acknowledging a frustrating situation empathetically ("yeah... that's tough")
- <disappointed> when plans fall through or bad news is shared — show empathy
- <excited> when a breakthrough happens, a big milestone is reached, or great news is shared"""

update_payload = {
    "conversation_config": {
        "tts": {
            "model_id": "eleven_v3_conversational",
            "voice_id": VOICE_ID,
            "agent_output_audio_format": "pcm_16000",
            "expressive_mode": True,
            "suggested_audio_tags": AUDIO_TAGS,
        },
        "agent": {
            "prompt": {
                "prompt": SYSTEM_PROMPT,
                "llm": "claude-3-5-sonnet",
                "temperature": 0.7,
                "max_tokens": -1,
            },
        },
    },
}

print("Updating agent to V3 Conversational with expressive mode...")
print(f"  Voice: {VOICE_ID}")
print(f"  Model: eleven_v3_conversational")
print(f"  Expressive mode: ON")
print(f"  Audio tags: {', '.join(t['tag'] for t in AUDIO_TAGS)}")
print()

resp = httpx.patch(
    f"https://api.elevenlabs.io/v1/convai/agents/{AGENT_ID}",
    headers={
        "Content-Type": "application/json",
        "xi-api-key": API_KEY,
    },
    json=update_payload,
    timeout=30,
)

print(f"Status: {resp.status_code}")
if resp.status_code == 200:
    data = resp.json()
    tts = data.get("conversation_config", {}).get("tts", {})
    print(f"Updated successfully!")
    print(f"  Model: {tts.get('model_id')}")
    print(f"  Voice: {tts.get('voice_id')}")
    print(f"  Expressive: {tts.get('expressive_mode')}")
    print(f"  Tags: {tts.get('suggested_audio_tags')}")
else:
    print(f"Error: {resp.text[:1000]}")
