import base64
import os
from pathlib import Path

import requests

GITHUB_REPO = "yvesbali/Yesbali.github.io"
GITHUB_BRANCH = "main"
TOKEN_FILE = os.path.join(os.path.expanduser("~"), ".lcdmh_github_token.txt")

LOCAL_FILE = "facebook_payload_test.json"
REMOTE_DIR = "facebook"
REMOTE_FILE = "facebook_payload_test.json"


def load_token() -> str:
    token_path = Path(TOKEN_FILE)
    if not token_path.exists():
        raise FileNotFoundError(f"Token GitHub introuvable : {TOKEN_FILE}")
    return token_path.read_text(encoding="utf-8").strip()


def github_headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def read_sha(token: str, repo_path: str):
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{repo_path}"
    r = requests.get(url, headers=github_headers(token), params={"ref": GITHUB_BRANCH}, timeout=20)
    if r.status_code == 404:
        return None
    r.raise_for_status()
    return r.json().get("sha")


def upload_file(token: str, repo_path: str, content: bytes, message: str):
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{repo_path}"
    sha = read_sha(token, repo_path)

    body = {
        "message": message,
        "content": base64.b64encode(content).decode("utf-8"),
        "branch": GITHUB_BRANCH,
    }
    if sha:
        body["sha"] = sha

    r = requests.put(url, headers=github_headers(token), json=body, timeout=30)
    print(f"{repo_path} -> HTTP {r.status_code}")
    if r.status_code not in (200, 201):
        try:
            print(r.json())
        except Exception:
            print(r.text[:1000])
    return r.status_code in (200, 201)


def main():
    root = Path.cwd()
    local_path = root / LOCAL_FILE

    if not local_path.exists():
        print(f"Fichier introuvable : {LOCAL_FILE}")
        return

    token = load_token()

    keep_path = f"{REMOTE_DIR}/.garder"
    upload_file(token, keep_path, "ok\n".encode("utf-8"), "Création dossier facebook")

    remote_path = f"{REMOTE_DIR}/{REMOTE_FILE}"
    ok = upload_file(
        token,
        remote_path,
        local_path.read_bytes(),
        "Mise à jour du payload Facebook test"
    )

    if not ok:
        print("\nÉchec pendant l'upload du payload.")
        return

    print("\n✅ Payload Facebook publié sur le site")
    print(f"URL publique : https://lcdmh.com/{remote_path}")
    print("Teste cette URL dans le navigateur avant de passer à Make.")


if __name__ == "__main__":
    main()
