import os
import hashlib
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from agora_token_builder import RtcTokenBuilder


app = FastAPI()


class TokenRequest(BaseModel):
    appId: str
    appCertificate: str | None = None
    channelName: str
    uid: int
    expireSeconds: int = 3600


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/token")
async def create_token(req: TokenRequest):
    app_id = req.appId or os.getenv("AGORA_APP_ID", "")
    app_cert = req.appCertificate or os.getenv("AGORA_APP_CERT", "")
    if not app_id or not app_cert:
        raise HTTPException(status_code=400, detail="Missing App ID or App Certificate")

    try:
        # Role 1 = publisher in agora-token-builder defaults
        token = RtcTokenBuilder.buildTokenWithUid(
            app_id,
            app_cert,
            req.channelName,
            req.uid,
            1,
            req.expireSeconds,
        )
        return {"token": token}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to build token: {e}")


def generate_deterministic_uid_from_string(value: str) -> int:
    # Produce a stable 32-bit unsigned int within Agora UID range
    digest = hashlib.sha256(value.encode()).digest()
    uid = int.from_bytes(digest[:4], "big")
    # Avoid zero UID
    return uid or 1


