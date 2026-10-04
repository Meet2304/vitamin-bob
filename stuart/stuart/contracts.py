import json
import re
from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, field_validator, model_validator

CONTRACT = "0.2"


def normalize_phone(value, country_code='+91'):
    """Convert carrier-formatted numeric senders to the contract's E.164 form."""
    if not isinstance(value,str):
        raise ValueError('Numeric sender required')
    number=re.sub(r'[\s().-]','',value)
    if number.startswith('00'):
        number='+'+number[2:]
    elif not number.startswith('+'):
        prefix=country_code.lstrip('+')
        # NANP often supplies its 11-digit international number without the +.
        if prefix=='1' and len(number)==11 and number.startswith('1'):
            number='+'+number
        elif prefix=='91' and len(number)==12 and number.startswith('91'):
            number='+'+number
        else:
            number=country_code+number.lstrip('0')
    if not re.fullmatch(r'\+[1-9]\d{6,14}',number):
        raise ValueError('Numeric E.164 sender required')
    return number


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Play(Model):
    type: Literal["play"]
    action_id: str = Field(min_length=1)
    audio_path: str


class Keypad(Model):
    type: Literal["keypad"]
    action_id: str = Field(min_length=1)
    max_digits: int = Field(ge=1, le=32)
    timeout_ms: int = Field(gt=0, le=120000)
    terminator: Literal["#"] | None


class Listen(Model):
    type: Literal["listen"]
    action_id: str = Field(min_length=1)
    max_ms: int = Field(gt=0, le=25000)
    end_silence_ms: int = Field(gt=0, le=25000)


class Hangup(Model):
    type: Literal["hangup"]
    action_id: str = Field(min_length=1)


Action = Annotated[Play | Keypad | Listen | Hangup, Field(discriminator="type")]


class Actions(Model):
    actions: list[Action]

    @model_validator(mode="after")
    def check_order(self):
        if not self.actions or isinstance(self.actions[-1], Play):
            raise ValueError("Exactly one terminal keypad/listen/hangup action is required")
        if any(not isinstance(a, Play) for a in self.actions[:-1]):
            raise ValueError("Only play actions may precede the terminal action")
        if len({a.action_id for a in self.actions}) != len(self.actions):
            raise ValueError("Action IDs in a list must be unique")
        return self


class Sms(Model):
    message_id: str = Field(min_length=1)
    to: str = Field(pattern=r"^\+[1-9]\d{6,14}$")
    text: str = Field(min_length=1, max_length=10000)
    priority: Literal["urgent", "normal", "bulk"]


class Record(Model):
    record_id: str = Field(min_length=1, max_length=128)
    kind: str = Field(min_length=1, max_length=32)
    payload: dict

    @field_validator("payload")
    @classmethod
    def check_size(cls, payload):
        if len(compact(payload).encode("utf-8")) > 200:
            raise ValueError("Compact UTF-8 payload exceeds 200 bytes")
        return payload


class Sync(Model):
    records: list[Record] = Field(min_length=1, max_length=100)


class Missed(Model):
    phone: str = Field(pattern=r"^\+[1-9]\d{6,14}$")
    line_id: str = "sim-1"
    source_id: str | None = None


class Input(Model):
    digits: str = Field(pattern=r"^[0-9*#]{0,32}$")


class IncomingSms(Model):
    message_id: str
    phone: str = Field(pattern=r"^\+[1-9]\d{6,14}$")
    line_id: str = "sim-1"
    text: str


def compact(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def safe_wav(path, root):
    candidate = Path(path)
    if not candidate.is_absolute():
        raise ValueError("Audio paths must be absolute")
    candidate = candidate.resolve()
    if not candidate.is_relative_to(Path(root).resolve()):
        raise ValueError("Prompt path lies outside the prompts directory")
    import wave
    with wave.open(str(candidate), "rb") as f:
        if (f.getframerate(), f.getnchannels(), f.getsampwidth(), f.getcomptype()) != (16000, 1, 2, "NONE"):
            raise ValueError("Expected WAV 16kHz mono PCM16")
    return candidate


def validate_event(event):
    # Fake Bob and the transport share validation, without sharing Bob's business logic.
    base = {"event_id", "type", "at"}
    shapes = {
        "missed_call": {"missed_call_id", "phone", "line_id"},
        "call_started": {"call_id", "missed_call_id", "phone", "line_id"},
        "action_result": {"call_id", "action_id", "status"},
        "call_ended": {"call_id", "reason"},
        "callback_failed": {"missed_call_id", "phone", "attempts"},
        "sms_received": {"message_id", "phone", "line_id", "text"},
        "sms_status": {"message_id", "status"},
        "sync_status": {"record_id", "status"},
    }
    typ = event.get("type")
    required = base | shapes.get(typ, set())
    optional = {"digits", "recording_path", "duration_ms"} if typ == "action_result" else set()
    if typ not in shapes or not required <= event.keys() or event.keys() - required - optional:
        raise ValueError("Event fields do not match contract 0.2")
    from datetime import datetime
    if datetime.fromisoformat(event["at"].replace("Z", "+00:00")).tzinfo is None:
        raise ValueError("Timestamp must have timezone")
    for key in required - {"type", "at", "attempts"}:
        if not isinstance(event[key], str) or not event[key]:
            raise ValueError(f"{key} must be a nonempty string")
    allowed = {
        "action_result": {"ok", "timeout", "no_input", "caller_hung_up", "error"},
        "call_ended": {"completed", "caller_hung_up", "no_answer", "failed"},
        "sms_status": {"sent", "delivered", "failed"},
        "sync_status": {"queued", "sent", "acked", "failed"},
    }
    value_key = "reason" if typ == "call_ended" else "status"
    if typ in allowed and event[value_key] not in allowed[typ]:
        raise ValueError("Invalid status/reason")
    return event
