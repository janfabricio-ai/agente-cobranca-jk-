"""
Upload de arquivos para o Google Drive.
Substitui versao anterior do mesmo nome (mesma pasta) para nao acumular duplicatas.
"""

import os
import json

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

BASE_DIR         = os.path.dirname(os.path.abspath(__file__))
CREDENCIAIS_JSON = os.path.join(BASE_DIR, "credenciais_google.json")
DRIVE_IDS_JSON   = os.path.join(BASE_DIR, "drive_ids.json")

SCOPES = ["https://www.googleapis.com/auth/drive"]


def _service():
    creds = Credentials.from_service_account_file(CREDENCIAIS_JSON, scopes=SCOPES)
    return build("drive", "v3", credentials=creds)


def carregar_ids():
    with open(DRIVE_IDS_JSON, encoding="utf-8") as f:
        return json.load(f)


def upload_arquivo(caminho_local, pasta_id, mimetype="application/pdf"):
    """Faz upload do arquivo para a pasta_id. Substitui se ja existir mesmo nome."""
    service = _service()
    nome = os.path.basename(caminho_local)

    q = f"name='{nome}' and '{pasta_id}' in parents and trashed=false"
    res = service.files().list(
        q=q, fields="files(id,name)",
        supportsAllDrives=True, includeItemsFromAllDrives=True,
    ).execute()
    for arq in res.get("files", []):
        service.files().delete(fileId=arq["id"], supportsAllDrives=True).execute()

    media = MediaFileUpload(caminho_local, mimetype=mimetype, resumable=False)
    meta = {"name": nome, "parents": [pasta_id]}
    arq = service.files().create(
        body=meta, media_body=media, fields="id,webViewLink",
        supportsAllDrives=True,
    ).execute()
    return arq["webViewLink"]


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Uso: python upload_drive.py <caminho_arquivo> [pasta_id]")
        sys.exit(1)
    caminho = sys.argv[1]
    ids = carregar_ids()
    pasta = sys.argv[2] if len(sys.argv) > 2 else ids["pasta_cobranca"]
    link = upload_arquivo(caminho, pasta)
    print(f"Upload OK: {link}")
