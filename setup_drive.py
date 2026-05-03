"""
Setup único — cria estrutura de pastas no Google Drive
JK ARTES GRÁFICA > Cobrança > Entrada
"""

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
import json, os

CREDENCIAIS_JSON  = r"C:\Users\conta\cobranca\credenciais_google.json"
PASTA_JK_ID       = "1uSmugzsaiEzgaIFo-3hR9CbLeNDx4f8d"
PLANILHA_ID       = "1cyJcx99hr0_HoWxkYJGt6dThOJCqKuzUWqqPRiFCWzw"

SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/spreadsheets",
]

def conectar():
    creds = Credentials.from_service_account_file(CREDENCIAIS_JSON, scopes=SCOPES)
    return build("drive", "v3", credentials=creds)

def criar_pasta(service, nome, pai_id):
    # Verifica se já existe
    q = f"name='{nome}' and '{pai_id}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false"
    res = service.files().list(q=q, fields="files(id,name)").execute()
    if res["files"]:
        print(f"  Pasta '{nome}' já existe: {res['files'][0]['id']}")
        return res["files"][0]["id"]
    meta = {
        "name": nome,
        "mimeType": "application/vnd.google-apps.folder",
        "parents": [pai_id],
    }
    pasta = service.files().create(body=meta, fields="id").execute()
    print(f"  Pasta '{nome}' criada: {pasta['id']}")
    return pasta["id"]

def mover_arquivo(service, file_id, novo_pai_id):
    arquivo = service.files().get(fileId=file_id, fields="parents").execute()
    pais_atuais = ",".join(arquivo.get("parents", []))
    service.files().update(
        fileId=file_id,
        addParents=novo_pai_id,
        removeParents=pais_atuais,
        fields="id,parents",
    ).execute()
    print(f"  Planilha movida para a pasta Cobrança")

def salvar_ids(ids):
    caminho = r"C:\Users\conta\cobranca\drive_ids.json"
    with open(caminho, "w") as f:
        json.dump(ids, f, indent=2, ensure_ascii=False)
    print(f"\n  IDs salvos em: {caminho}")

def main():
    print("=" * 55)
    print("  SETUP DRIVE — JK ARTES GRÁFICA")
    print("=" * 55)

    service = conectar()

    print("\nCriando estrutura de pastas...")
    pasta_cobranca = criar_pasta(service, "Cobrança", PASTA_JK_ID)
    pasta_entrada  = criar_pasta(service, "Entrada",  pasta_cobranca)

    print("\nMovendo planilha para pasta Cobrança...")
    mover_arquivo(service, PLANILHA_ID, pasta_cobranca)

    ids = {
        "pasta_jk":        PASTA_JK_ID,
        "pasta_cobranca":  pasta_cobranca,
        "pasta_entrada":   pasta_entrada,
        "planilha_id":     PLANILHA_ID,
    }
    salvar_ids(ids)

    print("\n" + "=" * 55)
    print("  ESTRUTURA CRIADA COM SUCESSO")
    print("=" * 55)
    print(f"\n  JK ARTES GRÁFICA/")
    print(f"    Cobrança/              {pasta_cobranca}")
    print(f"      Entrada/             {pasta_entrada}")
    print(f"      Cobrança JK (sheet)  {PLANILHA_ID}")
    print(f"\n  Próximo passo: subir os arquivos na pasta Entrada")
    print(f"    - zenetti.csv")
    print(f"    - mubys.xls")
    print(f"    - cadastro_clientes.xlsx")

if __name__ == "__main__":
    main()
