from app.config import Settings


def test_render_defaults_to_production(monkeypatch) -> None:
    monkeypatch.setenv("RENDER", "true")
    monkeypatch.delenv("ENVIRONMENT", raising=False)

    settings = Settings(_env_file=None)

    assert settings.environment == "production"


def test_generated_secret_is_unpredictable(monkeypatch) -> None:
    monkeypatch.delenv("SECRET_KEY", raising=False)

    first = Settings(_env_file=None)
    second = Settings(_env_file=None)

    assert len(first.secret_key) >= 48
    assert first.secret_key != second.secret_key
