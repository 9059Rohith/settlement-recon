"""Generate local-only credentials without printing them or overwriting existing config."""

import secrets
from pathlib import Path

path = Path(".env")
if path.exists():
    raise SystemExit(".env already exists; kept existing configuration")
path.write_text(
    f"API_TOKEN={secrets.token_urlsafe(40)}\nPOSTGRES_PASSWORD={secrets.token_urlsafe(32)}\n"
)
path.chmod(0o600)
print("Created .env with unique local credentials. Keep it private.")
