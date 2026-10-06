"""Conector opcional de Google Drive para evidencias y backups.

Inactivo por defecto: sin `GOOGLE_OAUTH_CLIENT_ID`/`GOOGLE_OAUTH_CLIENT_SECRET`
configurados, todos los metodos que requieren la integracion rechazan con un
error claro en vez de fallar de forma confusa. Usa REST directo via `httpx`
en vez de `google-api-python-client` para mantener las dependencias del
backend livianas. Los tokens OAuth se guardan cifrados (Fernet) en
`StorageProfile.oauth_tokens_encrypted`, una columna que nunca se expone en
`StorageProfileRead`.
"""

import hashlib
import hmac
import json
import secrets
import time
from urllib.parse import quote
from urllib.parse import urlencode

import httpx
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import decrypt_text, encrypt_text
from app.models.storage import StorageProfile
from app.schemas.storage import StorageProfileRead
from app.services.storage_service import to_read

AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
UPLOAD_URL = "https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart"
RESUMABLE_URL = "https://www.googleapis.com/upload/drive/v3/files?uploadType=resumable"
DOWNLOAD_URL = "https://www.googleapis.com/drive/v3/files"
DRIVE_SCOPE = "https://www.googleapis.com/auth/drive.file"
TOKEN_EXPIRY_SAFETY_MARGIN_SECONDS = 60


class GoogleDriveStorageService:
    def is_configured(self) -> bool:
        return bool(settings.google_oauth_client_id and settings.google_oauth_client_secret and settings.google_oauth_redirect_uri)

    def _require_configured(self) -> None:
        if not self.is_configured():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El conector de Google Drive no esta configurado en este servidor")

    def sign_state(self, project_id: str) -> str:
        signature = hmac.new(settings.secret_key.encode("utf-8"), project_id.encode("utf-8"), hashlib.sha256).hexdigest()
        return f"{project_id}:{signature}"

    def verify_state(self, state: str) -> str:
        try:
            project_id, signature = state.split(":", 1)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Estado de autorizacion invalido") from exc
        expected = hmac.new(settings.secret_key.encode("utf-8"), project_id.encode("utf-8"), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, signature):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Estado de autorizacion invalido")
        return project_id

    def build_authorization_url(self, project_id: str) -> str:
        self._require_configured()
        params = {
            "client_id": settings.google_oauth_client_id,
            "redirect_uri": settings.google_oauth_redirect_uri,
            "response_type": "code",
            "scope": DRIVE_SCOPE,
            "access_type": "offline",
            "prompt": "consent",
            "state": self.sign_state(project_id),
        }
        return f"{AUTHORIZE_URL}?{urlencode(params)}"

    def exchange_code_for_tokens(self, code: str) -> dict[str, object]:
        self._require_configured()
        response = httpx.post(
            TOKEN_URL,
            data={
                "code": code,
                "client_id": settings.google_oauth_client_id,
                "client_secret": settings.google_oauth_client_secret,
                "redirect_uri": settings.google_oauth_redirect_uri,
                "grant_type": "authorization_code",
            },
            timeout=15,
        )
        if response.status_code != 200:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="No fue posible completar la autorizacion con Google Drive")
        return response.json()

    def connect_profile(self, db: Session, project_id: str, tokens: dict[str, object]) -> StorageProfileRead:
        profile = (
            db.query(StorageProfile)
            .filter(StorageProfile.project_id == project_id, StorageProfile.provider == "gdrive")
            .first()
        )
        if profile is None:
            profile = StorageProfile(project_id=project_id, name="Google Drive", provider="gdrive")
            db.add(profile)
        elif profile.oauth_tokens_encrypted and not tokens.get("refresh_token"):
            previous = json.loads(decrypt_text(profile.oauth_tokens_encrypted))
            if previous.get("refresh_token"):
                tokens = {**tokens, "refresh_token": previous["refresh_token"]}
        profile.oauth_tokens_encrypted = encrypt_text(json.dumps(self._tokens_with_expiry(tokens)))
        profile.status = "active"
        db.commit()
        db.refresh(profile)
        return to_read(profile)

    def upload_file(self, db: Session, profile: StorageProfile, filename: str, content: bytes, mime_type: str) -> dict[str, object]:
        self._require_configured()
        tokens = self._valid_access_tokens(db, profile)
        media_type = mime_type or "application/octet-stream"
        metadata = json.dumps({"name": filename}, ensure_ascii=False).encode("utf-8")
        authorization = {"Authorization": f"Bearer {tokens['access_token']}"}
        if len(content) <= 5 * 1024 * 1024:
            boundary = f"infomatt360-{secrets.token_hex(12)}"
            body = (f"--{boundary}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n".encode()
                    + metadata + f"\r\n--{boundary}\r\nContent-Type: {media_type}\r\n\r\n".encode()
                    + content + f"\r\n--{boundary}--\r\n".encode())
            response = httpx.post(UPLOAD_URL, headers={**authorization, "Content-Type": f"multipart/related; boundary={boundary}"}, content=body, timeout=60)
        else:
            initiation = httpx.post(RESUMABLE_URL, headers={**authorization, "Content-Type": "application/json; charset=UTF-8", "X-Upload-Content-Type": media_type, "X-Upload-Content-Length": str(len(content))}, content=metadata, timeout=30)
            upload_url = initiation.headers.get("Location", "") if initiation.status_code == 200 else ""
            if not upload_url.startswith("https://www.googleapis.com/"):
                raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="No fue posible iniciar la subida a Google Drive")
            response = httpx.put(upload_url, headers={**authorization, "Content-Type": media_type, "Content-Length": str(len(content))}, content=content, timeout=120)
        if response.status_code not in (200, 201):
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="No fue posible subir el archivo a Google Drive")
        result = response.json()
        if not isinstance(result.get("id"), str) or not result["id"]:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Google Drive no devolvió el identificador del archivo")
        return result

    def get_file(self, db: Session, profile: StorageProfile, file_id: str) -> bytes:
        if not file_id or "/" in file_id:
            raise HTTPException(status_code=404, detail="Archivo de Drive no encontrado")
        tokens = self._valid_access_tokens(db, profile)
        response = httpx.get(f"{DOWNLOAD_URL}/{quote(file_id, safe='')}", params={"alt": "media"}, headers={"Authorization": f"Bearer {tokens['access_token']}"}, timeout=60)
        if response.status_code != 200:
            raise HTTPException(status_code=502, detail="No fue posible descargar el archivo desde Google Drive")
        return response.content

    def _tokens_with_expiry(self, tokens: dict[str, object]) -> dict[str, object]:
        expires_in = tokens.get("expires_in", 3600)
        return {**tokens, "expires_at": time.time() + float(expires_in)}

    def _valid_access_tokens(self, db: Session, profile: StorageProfile) -> dict[str, object]:
        if not profile.oauth_tokens_encrypted:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Este proyecto no tiene una cuenta de Google Drive conectada")
        tokens = json.loads(decrypt_text(profile.oauth_tokens_encrypted))
        if float(tokens.get("expires_at", 0)) > time.time() + TOKEN_EXPIRY_SAFETY_MARGIN_SECONDS:
            return tokens
        refresh_token = tokens.get("refresh_token")
        if not refresh_token:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="La conexion con Google Drive vencio; debe reconectarse")
        response = httpx.post(
            TOKEN_URL,
            data={
                "client_id": settings.google_oauth_client_id,
                "client_secret": settings.google_oauth_client_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            },
            timeout=15,
        )
        if response.status_code != 200:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="No fue posible refrescar la conexion con Google Drive")
        refreshed = response.json()
        tokens["access_token"] = refreshed["access_token"]
        tokens["expires_at"] = time.time() + float(refreshed.get("expires_in", 3600))
        profile.oauth_tokens_encrypted = encrypt_text(json.dumps(tokens))
        db.commit()
        return tokens


gdrive_storage_service = GoogleDriveStorageService()

