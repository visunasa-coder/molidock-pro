import sys
from pathlib import Path

from fastapi.testclient import TestClient


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.main import app


def main() -> None:
    with TestClient(app) as client:
        health = client.get("/health")
        print(f"health_status={health.status_code}")
        print(f"health_body={health.text}")

        email = "runtime-check@example.com"
        password = "runtime-check-password"
        register = client.post(
            "/auth/register",
            json={"email": email, "password": password, "full_name": "Runtime Check"},
        )
        print(f"register_status={register.status_code}")
        print(f"register_body={register.text}")

        token = client.post("/auth/token", data={"username": email, "password": password})
        print(f"token_status={token.status_code}")
        print(f"token_body={token.text}")

        if token.status_code == 200:
            access_token = token.json()["access_token"]
            me = client.get("/auth/me", headers={"Authorization": f"Bearer {access_token}"})
            print(f"me_status={me.status_code}")
            print(f"me_body={me.text}")


if __name__ == "__main__":
    main()
