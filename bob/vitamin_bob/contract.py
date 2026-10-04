"""The Stuart <-> Bob contract, version 0.2, as code.

One description of every message, used in two places so they can never drift apart:
  * Bob validates every incoming event and every action list it returns.
  * The fake Stuart validates every response and request Bob sends it.
Only Meet changes the contract; proposals go in bob/CONTRACT_NOTES.md.
"""

import json
import re
from typing import Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError

VERSION = "0.2"
HEADER = "X-VB-Contract"
MAX_LISTEN_MS = 25000
MAX_SYNC_PAYLOAD_BYTES = 200
E164 = r"^\+[1-9]\d{6,14}$"


class _Msg(BaseModel):
    model_config = ConfigDict(extra="allow")  # tolerate additions; required fields are enforced


# --- 7.2 Events: Stuart -> Bob ---------------------------------------------------------------
class _Event(_Msg):
    event_id: str = Field(min_length=1)
    at: str = Field(min_length=10)


class MissedCall(_Event):
    type: Literal["missed_call"]
    missed_call_id: str
    phone: str = Field(pattern=E164)
    line_id: str


class CallStarted(_Event):
    type: Literal["call_started"]
    call_id: str
    missed_call_id: str
    phone: str = Field(pattern=E164)
    line_id: str


class ActionResult(_Event):
    type: Literal["action_result"]
    call_id: str
    action_id: str
    status: Literal["ok", "timeout", "no_input", "caller_hung_up", "error"]
    digits: str | None = None
    recording_path: str | None = None
    duration_ms: int | None = None


class CallEnded(_Event):
    type: Literal["call_ended"]
    call_id: str
    reason: Literal["completed", "caller_hung_up", "no_answer", "failed"]


class CallbackFailed(_Event):
    type: Literal["callback_failed"]
    missed_call_id: str
    phone: str = Field(pattern=E164)
    attempts: int


class SmsReceived(_Event):
    type: Literal["sms_received"]
    message_id: str
    phone: str = Field(pattern=E164)
    line_id: str
    text: str


class SmsStatus(_Event):
    type: Literal["sms_status"]
    message_id: str
    status: Literal["sent", "delivered", "failed"]


class SyncStatus(_Event):
    type: Literal["sync_status"]
    record_id: str
    status: Literal["queued", "sent", "acked", "failed"]


Event = Annotated[
    Union[MissedCall, CallStarted, ActionResult, CallEnded, CallbackFailed, SmsReceived, SmsStatus, SyncStatus],
    Field(discriminator="type"),
]
EVENT = TypeAdapter(Event)

# --- 7.3 Call actions: Bob -> Stuart -----------------------------------------------------------


class Play(_Msg):
    type: Literal["play"]
    action_id: str
    audio_path: str


class Keypad(_Msg):
    type: Literal["keypad"]
    action_id: str
    max_digits: int = Field(ge=1)
    timeout_ms: int = Field(ge=1)
    terminator: Literal["#"] | None


class Listen(_Msg):
    type: Literal["listen"]
    action_id: str
    max_ms: int = Field(ge=1, le=MAX_LISTEN_MS)
    end_silence_ms: int = Field(ge=1)


class Hangup(_Msg):
    type: Literal["hangup"]
    action_id: str


Action = Annotated[Union[Play, Keypad, Listen, Hangup], Field(discriminator="type")]
ACTION = TypeAdapter(Action)


def action_list_problems(body: dict, check_files: bool = True) -> list[str]:
    """Everything wrong with an action list. Empty list means valid under 7.3."""
    from pathlib import Path

    from . import audio

    actions = body.get("actions") if isinstance(body, dict) else None
    if not isinstance(actions, list) or not actions:
        return ["`actions` must be a non-empty list"]
    problems = []
    for i, a in enumerate(actions):
        try:
            ACTION.validate_python(a)
        except ValidationError as e:
            problems.append(f"action {i}: {e.errors()[0]['msg']} ({e.errors()[0]['loc']})")
            continue
        last = i == len(actions) - 1
        if a["type"] == "play":
            if last:
                problems.append("a list must end with keypad, listen or hangup, not play")
            if check_files:
                p = Path(a["audio_path"])
                if not p.is_absolute():
                    problems.append(f"action {i}: audio_path must be absolute: {p}")
                elif not p.exists():
                    problems.append(f"action {i}: audio file missing: {p}")
                elif err := audio.check(p):
                    problems.append(f"action {i}: {p.name}: {err}")
        elif not last:
            problems.append(f"action {i}: {a['type']} must be the final action")
    ids = [a.get("action_id") for a in actions]
    if len(set(ids)) != len(ids):
        problems.append("action_ids within a list must be unique")
    return problems


# --- 7.4 Messaging: Bob -> Stuart --------------------------------------------------------------


class SmsRequest(_Msg):
    message_id: str
    to: str = Field(pattern=E164)
    text: str = Field(min_length=1)
    priority: Literal["urgent", "normal", "bulk"]


class SyncRecord(_Msg):
    record_id: str
    kind: str = Field(min_length=1, max_length=24)
    payload: dict


class SyncRequest(_Msg):
    records: list[SyncRecord] = Field(min_length=1)


_PHONE_LIKE = re.compile(r"\+?\d{10,}")


def compact(payload: dict) -> str:
    return json.dumps(payload, separators=(",", ":"), ensure_ascii=False)


def sync_payload_problems(payload: dict) -> list[str]:
    """7.4: at most 200 bytes compact, and nothing that looks like a raw phone number."""
    problems = []
    size = len(compact(payload).encode())
    if size > MAX_SYNC_PAYLOAD_BYTES:
        problems.append(f"payload is {size} bytes compact (max {MAX_SYNC_PAYLOAD_BYTES})")
    if _PHONE_LIKE.search(compact(payload)):
        problems.append("payload contains a phone-number-like digit run")
    return problems
