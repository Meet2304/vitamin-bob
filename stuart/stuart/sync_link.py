import base64
import json
import os
import re
import sqlite3
import threading
import zlib
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from .contracts import Record, compact
from .storage import now


def load_key(runtime):
    configured = os.getenv("VB_SYNC_KEY_HEX")
    if configured:
        key = bytes.fromhex(configured)
        if len(key) != 32:
            raise ValueError("VB_SYNC_KEY_HEX must encode 32 bytes")
        return key
    path = Path(runtime)/"demo-sync.key"
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        try:
            with path.open("xb") as f:
                f.write(os.urandom(32))
        except FileExistsError:
            pass
    return path.read_bytes()


class Codec:
    def __init__(self, key, hub="kevin-demo"):
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,16}", hub):
            raise ValueError("Hub ID must be 1-16 ASCII letters/digits/_/-")
        self.cipher, self.hub = AESGCM(key), hub

    def frames(self, seq, records):
        raw = compact({"h": self.hub, "s": seq, "r": records}).encode("utf-8")
        compressed = zlib.compress(raw)
        body = (b"Z"+compressed) if len(compressed) < len(raw) else (b"J"+raw)
        nonce = os.urandom(12)
        aad = f"VB1|{self.hub}|{seq}".encode("ascii")
        encoded = base64.b64encode(nonce+self.cipher.encrypt(nonce,body,aad)).decode("ascii")
        # Fixed chunk size guarantees each self-contained GSM-7 frame is <=160 characters.
        chunks = [encoded[i:i+95] for i in range(0,len(encoded),95)]
        if len(chunks) > 99:
            raise ValueError("Sync batch exceeds 99 frames")
        frames = [f"VB1|{self.hub}|{seq}|{i+1}|{len(chunks)}|{chunk}" for i,chunk in enumerate(chunks)]
        if any(len(f)>160 for f in frames):
            raise ValueError("Frame exceeds single SMS")
        return frames

    def decode(self, hub, seq, body):
        raw = base64.b64decode(body, validate=True)
        plain = self.cipher.decrypt(raw[:12], raw[12:], f"VB1|{hub}|{seq}".encode("ascii"))
        if plain[:1] == b"Z":
            decoder = zlib.decompressobj()
            decoded = decoder.decompress(plain[1:], 65537)
            if len(decoded)>65536 or decoder.unconsumed_tail or not decoder.eof:
                raise ValueError("Oversized/incomplete compressed payload")
        elif plain[:1] == b"J":
            decoded = plain[1:]
        else:
            raise ValueError("Unknown payload encoding")
        result = json.loads(decoded)
        if result["h"] != hub or result["s"] != seq:
            raise ValueError("Envelope does not match authenticated header")
        for record in result["r"]:
            Record.model_validate(record)
        return result["r"]

    def ack(self, hub, seq):
        nonce = os.urandom(12)
        header = f"VBA1|{hub}|{seq}"
        token = base64.b64encode(nonce+self.cipher.encrypt(nonce,b"ACK",header.encode("ascii"))).decode("ascii")
        return header+"|"+token

    def verify_ack(self, text):
        version, hub, seq, token = text.split("|")
        if version != "VBA1" or hub != self.hub:
            raise ValueError("ACK has wrong hub/version")
        raw = base64.b64decode(token,validate=True)
        if self.cipher.decrypt(raw[:12],raw[12:],f"VBA1|{hub}|{seq}".encode("ascii")) != b"ACK":
            raise ValueError("Wrong acknowledgement")
        return int(seq)


class Receiver:
    def __init__(self, path, codec):
        Path(path).parent.mkdir(parents=True,exist_ok=True)
        self.codec = codec
        self.lock=threading.RLock()
        self.db = sqlite3.connect(str(path),check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.executescript("""
        PRAGMA journal_mode=WAL;
        CREATE TABLE IF NOT EXISTS fragments(hub TEXT, seq INTEGER, idx INTEGER, total INTEGER, body TEXT,
            PRIMARY KEY(hub,seq,idx));
        CREATE TABLE IF NOT EXISTS records(hub TEXT, id TEXT, kind TEXT, payload TEXT, at TEXT,
            PRIMARY KEY(hub,id));
        CREATE TABLE IF NOT EXISTS batches(hub TEXT,seq INTEGER,PRIMARY KEY(hub,seq));
        """)
        self.db.commit()

    def receive(self,text):
        with self.lock:
            return self._receive(text)

    def _receive(self,text):
        version,hub,seq_s,index_s,total_s,body = text.split("|",5)
        seq,index,total = int(seq_s),int(index_s),int(total_s)
        if version!="VB1" or len(text)>160 or not re.fullmatch(r"[A-Za-z0-9_-]{1,16}",hub) or not 1<=index<=total<=99 or seq<1:
            raise ValueError("Invalid frame header")
        if self.db.execute("SELECT 1 FROM batches WHERE hub=? AND seq=?",(hub,seq)).fetchone():
            return self.codec.ack(hub,seq)
        existing = self.db.execute("SELECT body,total FROM fragments WHERE hub=? AND seq=? AND idx=?",(hub,seq,index)).fetchone()
        if existing and (existing["body"]!=body or existing["total"]!=total):
            raise ValueError("Conflicting fragment")
        self.db.execute("INSERT OR IGNORE INTO fragments VALUES(?,?,?,?,?)",(hub,seq,index,total,body))
        self.db.commit()
        parts=self.db.execute("SELECT * FROM fragments WHERE hub=? AND seq=? ORDER BY idx",(hub,seq)).fetchall()
        if len(parts)!=total:
            return None
        if any(p["total"]!=total for p in parts):
            raise ValueError("Inconsistent fragment count")
        try:
            records=self.codec.decode(hub,seq,"".join(p["body"] for p in parts))
        except Exception:
            self.db.execute('DELETE FROM fragments WHERE hub=? AND seq=?',(hub,seq))
            self.db.commit()
            raise
        try:
            for record in records:
                prior=self.db.execute("SELECT kind,payload FROM records WHERE hub=? AND id=?",(hub,record["record_id"])).fetchone()
                payload=compact(record["payload"])
                if prior and (prior["kind"]!=record["kind"] or prior["payload"]!=payload):
                    raise ValueError("Conflicting record ID")
                self.db.execute("INSERT OR IGNORE INTO records VALUES(?,?,?,?,?)",(hub,record["record_id"],record["kind"],payload,now()))
            self.db.execute("INSERT INTO batches VALUES(?,?)",(hub,seq))
            self.db.execute("DELETE FROM fragments WHERE hub=? AND seq=?",(hub,seq))
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return self.codec.ack(hub,seq)

    def rows(self):
        with self.lock:
            return [dict(r) for r in self.db.execute("SELECT * FROM records ORDER BY at DESC")]
