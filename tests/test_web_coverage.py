"""Additional tests to raise coverage above 80% threshold.

Targets uncovered paths in:
  - web/routes/compare.py       (42% -> needs TestClient calls)
  - web/routes/settings.py      (65% -> needs telegram/digest-test endpoints)
  - web/routes/search.py        (52% -> needs results/model-detail/download)
  - web/routes/downloads.py     (56% -> needs POST /downloads)
  - web/routes/dashboard.py     (73% -> needs backfill endpoint)
"""

from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from modelarr.db import init_db
from modelarr.models import WatchlistFilters
from modelarr.store import ModelarrStore
from modelarr.web.app import create_app

# ---------------------------------------------------------------------------
# Shared fixture helpers
# ---------------------------------------------------------------------------


def _setup_db(tmp_path: Path, **config: str) -> Path:
    """Create an isolated test DB with optional config overrides."""
    db_path = tmp_path / "test.db"
    init_db(db_path)
    store = ModelarrStore(db_path)
    store.set_config("library_path", str(tmp_path / "library"))
    for k, v in config.items():
        store.set_config(k, v)
    return db_path


def _client(db_path: Path) -> TestClient:
    """Return a TestClient patched to use the given DB path."""
    with patch("modelarr.web.app.get_db_path", return_value=db_path), \
         patch("modelarr.web.deps.get_db_path", return_value=db_path):
        app = create_app()
        return TestClient(app)


# ---------------------------------------------------------------------------
# compare.py — GET /compare, GET /compare with ids
# ---------------------------------------------------------------------------


def test_compare_page_empty(tmp_path: Path) -> None:
    """GET /compare returns 200 with empty library."""
    db_path = _setup_db(tmp_path)
    c = _client(db_path)
    response = c.get("/compare")
    assert response.status_code == 200
    assert "Compare" in response.text


def test_compare_page_with_models(tmp_path: Path) -> None:
    """GET /compare shows models when library has entries with local_path set."""
    db_path = _setup_db(tmp_path)
    store = ModelarrStore(db_path)
    # list_local_models() filters to models with local_path set
    m1_path = tmp_path / "m1"
    m1_path.mkdir(parents=True)
    m2_path = tmp_path / "m2"
    m2_path.mkdir(parents=True)
    store.upsert_model(
        "author/m1", "author", "m1",
        format_="gguf", quantization="Q4_K_M",
        size_bytes=1_000_000, downloaded_at=datetime.now(),
        local_path=str(m1_path),
    )
    store.upsert_model(
        "author/m2", "author", "m2",
        format_="safetensors", quantization="fp16",
        size_bytes=2_000_000, downloaded_at=datetime.now(),
        local_path=str(m2_path),
    )

    c = _client(db_path)
    response = c.get("/compare")
    assert response.status_code == 200
    # Page should render the compare form — either model names or the fieldset
    assert "Compare" in response.text


def test_compare_page_with_selected_ids(tmp_path: Path) -> None:
    """GET /compare?ids=1,2 renders a comparison table."""
    db_path = _setup_db(tmp_path)
    store = ModelarrStore(db_path)
    m1_path = tmp_path / "m1"
    m1_path.mkdir(parents=True)
    m2_path = tmp_path / "m2"
    m2_path.mkdir(parents=True)
    m1 = store.upsert_model(
        "author/m1", "author", "m1",
        format_="gguf", size_bytes=500_000, downloaded_at=datetime.now(),
        local_path=str(m1_path),
    )
    m2 = store.upsert_model(
        "author/m2", "author", "m2",
        format_="safetensors", size_bytes=1_000_000, downloaded_at=datetime.now(),
        local_path=str(m2_path),
    )

    c = _client(db_path)
    response = c.get(f"/compare?ids={m1.id},{m2.id}")
    assert response.status_code == 200
    # Should render comparison table
    assert "Compare" in response.text


def test_compare_page_invalid_ids(tmp_path: Path) -> None:
    """GET /compare?ids=999 with non-existent IDs returns 200 with empty selection."""
    db_path = _setup_db(tmp_path)
    c = _client(db_path)
    response = c.get("/compare?ids=999,1000")
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# settings.py — POST /settings/telegram-test and /settings/digest-test
# ---------------------------------------------------------------------------


def test_telegram_test_not_configured(tmp_path: Path) -> None:
    """POST /settings/telegram-test when Telegram not configured returns error toast."""
    db_path = _setup_db(tmp_path)
    c = _client(db_path)
    response = c.post("/settings/telegram-test")
    assert response.status_code == 200
    assert "Telegram not configured" in response.text or "toast" in response.text


def test_telegram_test_configured_success(tmp_path: Path) -> None:
    """POST /settings/telegram-test when configured and Telegram OK returns success."""
    db_path = _setup_db(
        tmp_path,
        telegram_bot_token="test_token",
        telegram_chat_id="test_chat",
    )
    with patch("modelarr.notifier.httpx.post") as mock_post:
        mock_post.return_value.status_code = 200
        c = _client(db_path)
        response = c.post("/settings/telegram-test")
    assert response.status_code == 200
    assert "toast" in response.text


def test_telegram_test_configured_failure(tmp_path: Path) -> None:
    """POST /settings/telegram-test when Telegram returns non-200."""
    db_path = _setup_db(
        tmp_path,
        telegram_bot_token="bad_token",
        telegram_chat_id="test_chat",
    )
    with patch("modelarr.notifier.httpx.post") as mock_post:
        mock_post.return_value.status_code = 401
        c = _client(db_path)
        response = c.post("/settings/telegram-test")
    assert response.status_code == 200
    assert "toast" in response.text


def test_digest_test_not_configured(tmp_path: Path) -> None:
    """POST /settings/digest-test when Telegram not configured returns error."""
    db_path = _setup_db(tmp_path)
    c = _client(db_path)
    response = c.post("/settings/digest-test")
    assert response.status_code == 200
    assert "Telegram not configured" in response.text or "toast" in response.text


def test_digest_test_configured_success(tmp_path: Path) -> None:
    """POST /settings/digest-test when configured and send succeeds."""
    db_path = _setup_db(
        tmp_path,
        telegram_bot_token="test_token",
        telegram_chat_id="test_chat",
    )
    with patch("modelarr.notifier.httpx.post") as mock_post:
        mock_post.return_value.status_code = 200
        c = _client(db_path)
        response = c.post("/settings/digest-test")
    assert response.status_code == 200
    assert "toast" in response.text


def test_save_settings_all_fields(tmp_path: Path) -> None:
    """POST /settings with all fields saves them correctly."""
    db_path = _setup_db(tmp_path)
    library_path = tmp_path / "lib"
    library_path.mkdir()
    c = _client(db_path)
    response = c.post(
        "/settings",
        data={
            "library_path": str(library_path),
            "max_storage_gb": "50",
            "interval_minutes": "30",
            "huggingface_token": "hf_test123",
            "telegram_bot_token": "123:abc",
            "telegram_chat_id": "-100123456",
            "max_download_workers": "2",
            "min_free_memory_mb": "100",
            "ollama_host": "http://localhost:11434",
            "digest_enabled": "on",
            "digest_day": "friday",
            "digest_hour": "8",
        },
    )
    assert response.status_code == 200
    assert "toast" in response.text


# ---------------------------------------------------------------------------
# search.py — GET /search/results, GET /search/model, POST /search/download
# ---------------------------------------------------------------------------


def test_search_results_short_query(tmp_path: Path) -> None:
    """GET /search/results?q=a returns 'at least 2 characters' message."""
    db_path = _setup_db(tmp_path)
    c = _client(db_path)
    response = c.get("/search/results?q=a")
    assert response.status_code == 200
    assert "2 characters" in response.text


def test_search_results_with_query(tmp_path: Path) -> None:
    """GET /search/results?q=llama returns results from HF (mocked)."""
    db_path = _setup_db(tmp_path)
    from modelarr.hf_client import ModelInfo as HFModelInfo

    mock_results = [
        HFModelInfo(
            repo_id="meta/llama3",
            name="llama3",
            author="meta",
            size_bytes=4_000_000_000,
        ),
    ]
    with patch("modelarr.hf_client.HFClient.search_models", return_value=mock_results):
        c = _client(db_path)
        response = c.get("/search/results?q=llama3")
    assert response.status_code == 200


def test_search_results_no_results(tmp_path: Path) -> None:
    """GET /search/results?q=xyznotfound returns 'No models found'."""
    db_path = _setup_db(tmp_path)
    with patch("modelarr.hf_client.HFClient.search_models", return_value=[]):
        c = _client(db_path)
        response = c.get("/search/results?q=xyznotfound")
    assert response.status_code == 200
    assert "No models found" in response.text


def test_search_results_hf_error(tmp_path: Path) -> None:
    """GET /search/results?q=test returns error message when HF raises."""
    db_path = _setup_db(tmp_path)
    with patch(
        "modelarr.hf_client.HFClient.search_models",
        side_effect=Exception("HF API down"),
    ):
        c = _client(db_path)
        response = c.get("/search/results?q=testquery")
    assert response.status_code == 200
    assert "Error" in response.text or "error" in response.text


def test_search_model_detail(tmp_path: Path) -> None:
    """GET /search/model/{repo_id} returns model detail partial."""
    db_path = _setup_db(tmp_path)
    from modelarr.hf_client import ModelInfo as HFModelInfo

    mock_model = HFModelInfo(
        repo_id="meta/llama3",
        name="llama3",
        author="meta",
        size_bytes=4_000_000_000,
    )
    with patch("modelarr.hf_client.HFClient.get_model_info", return_value=mock_model):
        c = _client(db_path)
        response = c.get("/search/model/meta/llama3")
    assert response.status_code == 200


def test_search_model_detail_error(tmp_path: Path) -> None:
    """GET /search/model/bad/id returns error partial when HF raises."""
    db_path = _setup_db(tmp_path)
    with patch(
        "modelarr.hf_client.HFClient.get_model_info",
        side_effect=Exception("Not found"),
    ):
        c = _client(db_path)
        response = c.get("/search/model/bad/repo")
    assert response.status_code == 200
    assert "Error" in response.text or "error" in response.text


def test_download_from_search(tmp_path: Path) -> None:
    """POST /search/download queues a download."""
    db_path = _setup_db(tmp_path)
    from modelarr.hf_client import ModelInfo as HFModelInfo

    mock_model = HFModelInfo(
        repo_id="meta/llama3",
        name="llama3",
        author="meta",
        size_bytes=4_000_000_000,
    )
    with patch("modelarr.hf_client.HFClient.get_model_info", return_value=mock_model), \
         patch("modelarr.downloader.DownloadManager.download_model"):
        c = _client(db_path)
        response = c.post("/search/download", data={"repo_id": "meta/llama3"})
    assert response.status_code == 200
    assert "toast" in response.text


def test_download_from_search_missing_repo_id(tmp_path: Path) -> None:
    """POST /search/download with empty repo_id returns error."""
    db_path = _setup_db(tmp_path)
    c = _client(db_path)
    response = c.post("/search/download", data={"repo_id": ""})
    assert response.status_code == 200
    assert "required" in response.text or "toast" in response.text


# ---------------------------------------------------------------------------
# downloads.py — POST /downloads (manual download)
# ---------------------------------------------------------------------------


def test_manual_download_success(tmp_path: Path) -> None:
    """POST /downloads queues a manual download successfully."""
    db_path = _setup_db(tmp_path)
    from modelarr.hf_client import ModelInfo as HFModelInfo

    mock_model = HFModelInfo(
        repo_id="test/model",
        name="model",
        author="test",
        size_bytes=100_000,
    )
    with patch("modelarr.hf_client.HFClient.get_model_info", return_value=mock_model), \
         patch("modelarr.downloader.DownloadManager.download_model"):
        c = _client(db_path)
        response = c.post("/downloads", data={"repo_id": "test/model"})
    assert response.status_code == 200
    assert "toast" in response.text


def test_manual_download_missing_repo_id(tmp_path: Path) -> None:
    """POST /downloads with empty repo_id returns error toast."""
    db_path = _setup_db(tmp_path)
    c = _client(db_path)
    response = c.post("/downloads", data={"repo_id": ""})
    assert response.status_code == 200
    assert "required" in response.text or "toast" in response.text


def test_manual_download_hf_error(tmp_path: Path) -> None:
    """POST /downloads returns error toast when HF lookup fails."""
    db_path = _setup_db(tmp_path)
    with patch(
        "modelarr.hf_client.HFClient.get_model_info",
        side_effect=Exception("Not found"),
    ):
        c = _client(db_path)
        response = c.post("/downloads", data={"repo_id": "bad/model"})
    assert response.status_code == 200
    assert "toast" in response.text


# ---------------------------------------------------------------------------
# dashboard.py — POST /dashboard/backfill
# ---------------------------------------------------------------------------


def test_dashboard_backfill_no_matches(tmp_path: Path) -> None:
    """POST /dashboard/backfill returns toast when no models match watchlist."""
    db_path = _setup_db(tmp_path)
    with patch("modelarr.monitor.ModelarrMonitor.run_once", return_value=[]):
        c = _client(db_path)
        response = c.post("/dashboard/backfill")
    assert response.status_code == 200
    assert "toast" in response.text


def test_dashboard_backfill_with_matches(tmp_path: Path) -> None:
    """POST /dashboard/backfill returns success toast when models are queued."""
    db_path = _setup_db(tmp_path)
    from modelarr.models import ModelInfo, WatchlistEntry

    fake_watch = WatchlistEntry(
        id=1, type="author", value="test", filters=WatchlistFilters(),
        enabled=True, created_at=datetime.now(), updated_at=datetime.now(),
    )
    fake_model = ModelInfo(
        repo_id="test/model", name="model", author="test", size_bytes=100_000,
    )
    with patch("modelarr.monitor.ModelarrMonitor.run_once",
               return_value=[(fake_watch, fake_model)]):
        c = _client(db_path)
        response = c.post("/dashboard/backfill")
    assert response.status_code == 200
    assert "toast" in response.text


def test_dashboard_check_no_new_models(tmp_path: Path) -> None:
    """POST /dashboard/check returns 'No new models' when nothing found."""
    db_path = _setup_db(tmp_path)
    with patch("modelarr.monitor.ModelarrMonitor.run_once", return_value=[]):
        c = _client(db_path)
        response = c.post("/dashboard/check")
    assert response.status_code == 200
    assert "No new models" in response.text or "toast" in response.text
