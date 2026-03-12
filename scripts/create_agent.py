"""Create ElevenLabs Conversational AI agent for Gneva."""

import json
import os
import sys

import httpx

API_KEY = os.environ.get("ELEVENLABS_API_KEY", "sk_f9f93edf18959721869c313a2ba237b09216086704f0648a")
VOICE_ID = os.environ.get("ELEVENLABS_VOICE_ID", "OUBnvvuqEKdDWtapoJFn")

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
- If someone is mid-thought, wait for them to finish"""

agent_config = {
    "name": "Gneva",
    "conversation_config": {
        "asr": {
            "quality": "high",
            "provider": "elevenlabs",
            "user_input_audio_format": "pcm_16000",
        },
        "turn": {
            "turn_timeout": 7,
            "turn_eagerness": "normal",
        },
        "tts": {
            "model_id": "eleven_turbo_v2",
            "voice_id": VOICE_ID,
            "agent_output_audio_format": "pcm_16000",
            "stability": 0.5,
            "speed": 1.0,
            "similarity_boost": 0.75,
        },
        "conversation": {
            "text_only": False,
            "max_duration_seconds": 7200,
        },
        "agent": {
            "first_message": "Hey everyone, Gneva here. I'll be listening in and tracking any action items. Just ask if you need anything.",
            "language": "en",
            "prompt": {
                "prompt": SYSTEM_PROMPT,
                "llm": "claude-3-5-sonnet",
                "temperature": 0.7,
                "max_tokens": -1,
                "tools": [
                    {
                        "type": "client",
                        "name": "create_action_item",
                        "description": "Create an action item when someone commits to a task. Call this when you hear phrases like 'I'll do that', 'let me handle', 'action item for me'.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "assignee": {"type": "string", "description": "Person responsible"},
                                "task": {"type": "string", "description": "What they committed to do"},
                                "due_date": {"type": "string", "description": "When it's due, if mentioned"},
                            },
                            "required": ["assignee", "task"],
                        },
                        "expects_response": True,
                    },
                    {
                        "type": "client",
                        "name": "search_memory",
                        "description": "Search organizational memory for context from past meetings. Use when someone asks 'what did we decide about X' or 'remind me what happened with Y'.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "query": {"type": "string", "description": "What to search for"},
                            },
                            "required": ["query"],
                        },
                        "expects_response": True,
                    },
                ],
            },
        },
    },
}

def main():
    print("Creating ElevenLabs Conversational AI agent...")
    print(f"  Voice ID: {VOICE_ID}")
    print(f"  LLM: claude-3-5-sonnet")
    print()

    resp = httpx.post(
        "https://api.elevenlabs.io/v1/convai/agents/create",
        headers={
            "Content-Type": "application/json",
            "xi-api-key": API_KEY,
        },
        json=agent_config,
        timeout=30,
    )

    if resp.status_code == 200:
        data = resp.json()
        agent_id = data.get("agent_id", "")
        print(f"Agent created successfully!")
        print(f"  Agent ID: {agent_id}")
        print()
        print(f"Add this to your .env:")
        print(f"  ELEVENLABS_AGENT_ID={agent_id}")
        print()
        print(f"Full response:")
        print(json.dumps(data, indent=2))
        return agent_id
    else:
        print(f"Error {resp.status_code}:")
        print(resp.text)
        sys.exit(1)


if __name__ == "__main__":
    main()
