"""Tests for the init (setup wizard) CLI command."""

from typer.testing import CliRunner

import modelarr.cli
from modelarr.cli import app
from modelarr.db import init_db
from modelarr.store import ModelarrStore

runner = CliRunner()


def _make_mock_store(db_path):
    """Create a mock _get_store that returns a store backed by tmp db."""
    def mock_get_store():
        return ModelarrStore(db_path)
    return mock_get_store


def test_init_sets_library_path(tmp_path):
    """Test init wizard sets library_path with defaults."""
    db_path = tmp_path / "test.db"
    init_db(db_path)

    original = modelarr.cli._get_store
    modelarr.cli._get_store = _make_mock_store(db_path)

    try:
        # Accept default path, decline all optional features, accept default interval
        # decline Ollama
        result = runner.invoke(app, ["init"], input="/tmp/test-models\nn\nn\nn\n60\nn\nn\n")
        assert result.exit_code == 0
        assert "Welcome to modelarr" in result.stdout
        assert "Setup complete" in result.stdout

        store = ModelarrStore(db_path)
        assert store.get_config("library_path") == "/tmp/test-models"
        assert store.get_config("interval_minutes") == "60"
    finally:
        modelarr.cli._get_store = original


def test_init_sets_storage_limit(tmp_path):
    """Test init wizard configures storage limit and auto-prune."""
    db_path = tmp_path / "test.db"
    init_db(db_path)

    original = modelarr.cli._get_store
    modelarr.cli._get_store = _make_mock_store(db_path)

    try:
        # Path, yes to storage limit, 500 GB, yes to auto-prune
        # no HF, no telegram, interval, no Ollama
        result = runner.invoke(
            app, ["init"], input="/tmp/models\ny\n500\ny\nn\nn\n30\nn\nn\n"
        )
        assert result.exit_code == 0
        assert "Storage limit: 500 GB" in result.stdout

        store = ModelarrStore(db_path)
        assert store.get_config("max_storage_gb") == "500"
        assert store.get_config("storage_auto_prune") == "true"
        assert store.get_config("interval_minutes") == "30"
    finally:
        modelarr.cli._get_store = original


def test_init_sets_telegram(tmp_path):
    """Test init wizard configures Telegram notifications."""
    db_path = tmp_path / "test.db"
    init_db(db_path)

    original = modelarr.cli._get_store
    modelarr.cli._get_store = _make_mock_store(db_path)

    try:
        # Path, no storage, no HF, yes telegram, bot token, chat id, interval, no Ollama
        result = runner.invoke(
            app, ["init"], input="/tmp/models\nn\nn\ny\nbot123\nchat456\n60\nn\nn\n"
        )
        assert result.exit_code == 0
        assert "Telegram notifications configured" in result.stdout

        store = ModelarrStore(db_path)
        assert store.get_config("telegram_bot_token") == "bot123"
        assert store.get_config("telegram_chat_id") == "chat456"
    finally:
        modelarr.cli._get_store = original


def test_init_sets_huggingface_token(tmp_path):
    """Test init wizard configures HuggingFace token."""
    db_path = tmp_path / "test.db"
    init_db(db_path)

    original = modelarr.cli._get_store
    modelarr.cli._get_store = _make_mock_store(db_path)

    try:
        # Path, no storage, yes HF, token, no telegram, interval, no Ollama
        result = runner.invoke(
            app, ["init"], input="/tmp/models\nn\ny\nhf_secret_token\nn\n60\nn\nn\n"
        )
        assert result.exit_code == 0
        assert "HuggingFace token saved" in result.stdout

        store = ModelarrStore(db_path)
        assert store.get_config("huggingface_token") == "hf_secret_token"
    finally:
        modelarr.cli._get_store = original


def test_init_rerun_declined(tmp_path):
    """Test that re-running init on configured system can be declined."""
    db_path = tmp_path / "test.db"
    init_db(db_path)

    store = ModelarrStore(db_path)
    store.set_config("library_path", "/existing/path")

    original = modelarr.cli._get_store
    modelarr.cli._get_store = _make_mock_store(db_path)

    try:
        # Decline re-run
        result = runner.invoke(app, ["init"], input="n\n")
        assert result.exit_code == 0
        assert "already configured" in result.stdout

        # Original config unchanged
        store2 = ModelarrStore(db_path)
        assert store2.get_config("library_path") == "/existing/path"
    finally:
        modelarr.cli._get_store = original


def test_init_rerun_accepted(tmp_path):
    """Test that re-running init on configured system updates config."""
    db_path = tmp_path / "test.db"
    init_db(db_path)

    store = ModelarrStore(db_path)
    store.set_config("library_path", "/old/path")

    original = modelarr.cli._get_store
    modelarr.cli._get_store = _make_mock_store(db_path)

    try:
        # Accept re-run, new path, skip everything, no Ollama
        result = runner.invoke(app, ["init"], input="y\n/new/path\nn\nn\nn\n60\nn\nn\n")
        assert result.exit_code == 0
        assert "Setup complete" in result.stdout

        store2 = ModelarrStore(db_path)
        assert store2.get_config("library_path") == "/new/path"
    finally:
        modelarr.cli._get_store = original


def test_init_all_options(tmp_path):
    """Test init wizard with all options enabled."""
    db_path = tmp_path / "test.db"
    init_db(db_path)

    original = modelarr.cli._get_store
    modelarr.cli._get_store = _make_mock_store(db_path)

    try:
        # Yes to everything including Ollama
        result = runner.invoke(
            app,
            ["init"],
            input="/tmp/all-models\ny\n1000\ny\ny\nhf_tok\ny\nbot_tok\n12345\n15\ny\n2\n100\ny\nhttp://ollama:11434\n",
        )
        assert result.exit_code == 0
        assert "Setup complete" in result.stdout

        store = ModelarrStore(db_path)
        assert store.get_config("library_path") == "/tmp/all-models"
        assert store.get_config("max_storage_gb") == "1000"
        assert store.get_config("storage_auto_prune") == "true"
        assert store.get_config("huggingface_token") == "hf_tok"
        assert store.get_config("telegram_bot_token") == "bot_tok"
        assert store.get_config("telegram_chat_id") == "12345"
        assert store.get_config("interval_minutes") == "15"
        assert store.get_config("max_download_workers") == "2"
        assert store.get_config("min_free_memory_mb") == "100"
        assert store.get_config("ollama_host") == "http://ollama:11434"
    finally:
        modelarr.cli._get_store = original
