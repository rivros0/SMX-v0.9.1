"""Impostazioni pubbliche del sistema di aggiornamento SMX."""

GITHUB_REPOSITORY = "rivros0/SMX-v0.9.1"
GITHUB_API_URL = "https://api.github.com"

RELEASE_ASSETS = {
    "win32": {
        "archive": "SMX-windows-x64.zip",
        "binary": "SMX/SMX.exe",
    },
    "linux": {
        "archive": "SMX-linux-x64.tar.gz",
        "binary": "SMX/SMX",
    },
}

CHECKSUM_ASSET = "SHA256SUMS.txt"
KEYRING_SERVICE = "SMX-GitHub-Releases"
KEYRING_ACCOUNT = "github-readonly-token"
