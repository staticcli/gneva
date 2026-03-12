"""Phase 8 — Autonomous Agent Actions.

Agents can monitor conditions and take proactive actions:
- Auto-summarize when conversation reaches a natural break
- Alert when security/compliance issues are detected
- Track and remind about time-sensitive topics
- Detect when conversation is going in circles
- Auto-capture decisions and action items
"""

import asyncio
import logging
import time
from datetime import datetime
from typing import Any, Callable, Coroutine

logger = logging.getLogger(__name__)


class TriggerCondition:
    """A condition that, when met, fires an autonomous action."""

    def __init__(self, name: str, check_fn: Callable[..., bool],
                 action_fn: Callable[..., Coroutine],
                 cooldown_sec: float = 60,
                 max_fires: int = 5,
                 priority: str = "normal"):
        self.name = name
        self.check = check_fn
        self.action = action_fn
        self.cooldown_sec = cooldown_sec
        self.max_fires = max_fires
        self.priority = priority

        self.fire_count = 0
        self.last_fired: float = 0
        self.enabled = True

    @property
    def can_fire(self) -> bool:
        if not self.enabled:
            return False
        if self.fire_count >= self.max_fires:
            return False
        if (time.time() - self.last_fired) < self.cooldown_sec:
            return False
        return True

    def record_fire(self):
        self.fire_count += 1
        self.last_fired = time.time()


class AutonomousEngine:
    """Monitors meeting state and fires autonomous agent actions.

    Runs as a background loop during meetings, checking trigger conditions
    and executing actions when thresholds are met.
    """

    def __init__(self, meeting_id: str, agent_router, conversation_engine=None):
        self.meeting_id = meeting_id
        self._router = agent_router
        self._conversation = conversation_engine
        self._triggers: list[TriggerCondition] = []
        self._running = False
        self._task: asyncio.Task | None = None
        self._action_log: list[dict] = []

        # Meeting state tracking
        self._transcript_len = 0
        self._last_decision_check = 0
        self._topic_history: list[str] = []
        self._circle_detection_window: list[str] = []

        # Register default triggers
        self._register_defaults()

    def _register_defaults(self):
        """Register built-in autonomous triggers."""

        # 1. Auto-capture decisions when confident language is detected
        self.add_trigger(TriggerCondition(
            name="decision_capture",
            check_fn=self._check_decision_language,
            action_fn=self._action_capture_decision,
            cooldown_sec=30,
            max_fires=20,
            priority="normal",
        ))

        # 2. Detect circular conversation (same topic revisited 3+ times)
        self.add_trigger(TriggerCondition(
            name="circle_detection",
            check_fn=self._check_circular,
            action_fn=self._action_flag_circular,
            cooldown_sec=120,
            max_fires=3,
            priority="high",
        ))

        # 3. Time check — remind about meeting duration at intervals
        self.add_trigger(TriggerCondition(
            name="time_check",
            check_fn=self._check_time_warning,
            action_fn=self._action_time_warning,
            cooldown_sec=300,
            max_fires=3,
            priority="low",
        ))

        # 4. Action item detection — auto-capture when someone commits to something
        self.add_trigger(TriggerCondition(
            name="action_item_capture",
            check_fn=self._check_action_language,
            action_fn=self._action_capture_action_item,
            cooldown_sec=20,
            max_fires=30,
            priority="normal",
        ))

        # 5. Parking lot — detect when topics are deferred
        self.add_trigger(TriggerCondition(
            name="parking_lot",
            check_fn=self._check_parking_lot,
            action_fn=self._action_add_parking_lot,
            cooldown_sec=30,
            max_fires=10,
            priority="low",
        ))

    def add_trigger(self, trigger: TriggerCondition):
        self._triggers.append(trigger)

    async def start(self):
        """Start the autonomous monitoring loop."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._monitor_loop())
        self._task.add_done_callback(
            lambda t: t.exception() if not t.cancelled() and t.exception() else None
        )
        logger.info(f"Autonomous engine started for meeting {self.meeting_id}")

    async def stop(self):
        """Stop the monitoring loop."""
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info(f"Autonomous engine stopped for meeting {self.meeting_id}")

    def get_transcript_buffer(self) -> list[dict]:
        """Get the current transcript buffer from the conversation engine."""
        if self._conversation and hasattr(self._conversation, '_transcript_buffer'):
            return self._conversation._transcript_buffer
        return []

    def get_meeting_start_time(self) -> float:
        if self._conversation and hasattr(self._conversation, '_meeting_start_time'):
            return self._conversation._meeting_start_time or time.time()
        return time.time()

    async def _monitor_loop(self):
        """Main monitoring loop — checks triggers every few seconds."""
        while self._running:
            try:
                await asyncio.sleep(5)

                transcript = self.get_transcript_buffer()
                if not transcript:
                    continue

                # Check if transcript has grown
                if len(transcript) <= self._transcript_len:
                    continue
                self._transcript_len = len(transcript)

                # Check all triggers
                for trigger in self._triggers:
                    if not trigger.can_fire:
                        continue
                    try:
                        if trigger.check(transcript):
                            logger.info(f"Autonomous trigger fired: {trigger.name}")
                            result = await trigger.action(transcript)
                            trigger.record_fire()
                            self._action_log.append({
                                "trigger": trigger.name,
                                "result": result,
                                "timestamp": datetime.utcnow().isoformat(),
                            })
                    except Exception as e:
                        logger.debug(f"Trigger {trigger.name} error: {e}")

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Autonomous monitor error: {e}")
                await asyncio.sleep(10)

    # ── Condition Checkers ────────────────────────────────────────────────

    def _check_decision_language(self, transcript: list[dict]) -> bool:
        """Check if recent transcript contains decision language."""
        if len(transcript) < 3:
            return False
        recent = " ".join(s.get("text", "") for s in transcript[-5:]).lower()
        decision_phrases = [
            "let's go with", "we've decided", "the decision is",
            "we're going to", "agreed, we'll", "final answer is",
            "let's do", "so we'll", "the plan is",
            "we're committing to", "motion carries", "approved",
        ]
        return any(p in recent for p in decision_phrases)

    def _check_circular(self, transcript: list[dict]) -> bool:
        """Detect if conversation is going in circles."""
        if len(transcript) < 20:
            return False
        # Simple: check if the same key phrases appear in distant segments
        early = " ".join(s.get("text", "") for s in transcript[-20:-10]).lower()
        late = " ".join(s.get("text", "") for s in transcript[-10:]).lower()

        # Extract significant words (>4 chars)
        early_words = set(w for w in early.split() if len(w) > 4)
        late_words = set(w for w in late.split() if len(w) > 4)

        if not early_words or not late_words:
            return False

        overlap = len(early_words & late_words) / max(len(early_words | late_words), 1)
        return overlap > 0.5  # >50% word overlap suggests circular

    def _check_time_warning(self, transcript: list[dict]) -> bool:
        """Check if meeting has been running long."""
        elapsed = time.time() - self.get_meeting_start_time()
        # Warn at 45min, 60min, 90min
        thresholds = [2700, 3600, 5400]
        for t in thresholds:
            if elapsed > t and elapsed < t + 30:  # 30-second window to fire
                return True
        return False

    def _check_action_language(self, transcript: list[dict]) -> bool:
        """Check if someone just committed to an action."""
        if len(transcript) < 2:
            return False
        recent = transcript[-1].get("text", "").lower()
        action_phrases = [
            "i'll", "i will", "i'm going to", "let me",
            "i'll take that", "i can do that", "i'll handle",
            "i'll follow up", "i'll send", "i'll schedule",
            "by friday", "by end of", "by tomorrow", "next week",
        ]
        return any(p in recent for p in action_phrases)

    def _check_parking_lot(self, transcript: list[dict]) -> bool:
        """Check if a topic is being deferred."""
        if len(transcript) < 2:
            return False
        recent = transcript[-1].get("text", "").lower()
        defer_phrases = [
            "let's table that", "park that", "come back to",
            "not now", "another time", "offline", "follow up later",
            "take that offline", "separate meeting", "parking lot",
        ]
        return any(p in recent for p in defer_phrases)

    # ── Actions ───────────────────────────────────────────────────────────

    async def _action_capture_decision(self, transcript: list[dict]) -> str:
        """Auto-capture a detected decision."""
        recent_text = " ".join(s.get("text", "") for s in transcript[-5:])
        speaker = transcript[-1].get("speaker", "Unknown")

        from gneva.services import llm_create
        try:
            response = await llm_create(
                model="claude-haiku-4-5-20251001",
                max_tokens=100,
                system="Extract the decision from this meeting transcript snippet. Return just the decision in one sentence.",
                messages=[{"role": "user", "content": recent_text}],
            )
            decision = response.content[0].text.strip() if response.content else ""
            if decision:
                # Store via tools
                try:
                    from gneva.bot.tools import execute_tool
                    await execute_tool(
                        "log_decision",
                        {"decision": decision, "made_by": speaker, "context": recent_text[:200]},
                        org_id=self._router.org_id if self._router else None,
                        meeting_id=self.meeting_id,
                    )
                except Exception:
                    pass
                return f"Decision captured: {decision}"
        except Exception as e:
            logger.debug(f"Decision capture failed: {e}")
        return "Decision detection triggered but capture failed"

    async def _action_flag_circular(self, transcript: list[dict]) -> str:
        """Flag that conversation appears to be going in circles."""
        return "circular_conversation_detected"

    async def _action_time_warning(self, transcript: list[dict]) -> str:
        """Generate a time warning."""
        elapsed_min = int((time.time() - self.get_meeting_start_time()) / 60)
        return f"time_warning_{elapsed_min}min"

    async def _action_capture_action_item(self, transcript: list[dict]) -> str:
        """Auto-capture a detected action item."""
        last = transcript[-1]
        speaker = last.get("speaker", "Unknown")
        text = last.get("text", "")

        from gneva.services import llm_create
        try:
            response = await llm_create(
                model="claude-haiku-4-5-20251001",
                max_tokens=80,
                system="Extract the action item from this statement. Return: ASSIGNEE: name | ACTION: description | DUE: date_or_none. One line only.",
                messages=[{"role": "user", "content": f"{speaker} said: {text}"}],
            )
            result = response.content[0].text.strip() if response.content else ""
            return f"Action item captured: {result}"
        except Exception as e:
            logger.debug(f"Action item capture failed: {e}")
        return "Action item detection triggered"

    async def _action_add_parking_lot(self, transcript: list[dict]) -> str:
        """Add a deferred topic to the parking lot."""
        text = transcript[-1].get("text", "")
        # Look at previous context for the actual topic
        if len(transcript) >= 3:
            context = " ".join(s.get("text", "") for s in transcript[-3:-1])
        else:
            context = text
        return f"parking_lot_item: {context[:200]}"

    def get_action_log(self) -> list[dict]:
        return list(self._action_log)

    def get_stats(self) -> dict:
        return {
            "running": self._running,
            "triggers": [
                {
                    "name": t.name,
                    "enabled": t.enabled,
                    "fire_count": t.fire_count,
                    "can_fire": t.can_fire,
                }
                for t in self._triggers
            ],
            "total_actions_fired": len(self._action_log),
        }
