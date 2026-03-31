"""Ollama API client for pushing models and managing Modelfiles."""

import logging
from pathlib import Path

import httpx

from modelarr.models import ModelRecord

logger = logging.getLogger(__name__)


class OllamaClient:
    """Client for interacting with Ollama API."""

    def __init__(self, host: str = "http://localhost:11434"):
        """Initialize Ollama client.

        Args:
            host: Ollama API host URL (default: http://localhost:11434)
        """
        self.host = host.rstrip("/")
        self.timeout = 10.0

    def generate_modelfile(self, model: ModelRecord) -> str:
        """Generate a Modelfile for the given model.

        Finds the largest .gguf file in the model's local_path and uses it
        as the FROM path in the Modelfile.

        Args:
            model: ModelRecord with local_path set

        Returns:
            Modelfile content as string

        Raises:
            ValueError: If no .gguf file found or local_path not set
        """
        if not model.local_path:
            raise ValueError(f"Model {model.repo_id} has no local_path set")

        local_path = Path(model.local_path)
        if not local_path.exists():
            raise ValueError(f"Model path does not exist: {local_path}")

        # Find largest .gguf file
        gguf_files = list(local_path.glob("**/*.gguf"))
        if not gguf_files:
            raise ValueError(f"No .gguf files found in {local_path}")

        largest = max(gguf_files, key=lambda f: f.stat().st_size)
        return f"FROM {largest.absolute()}\n"

    def push_model(
        self, model: ModelRecord, model_name: str | None = None
    ) -> bool:
        """Push a model to Ollama.

        Generates a Modelfile and sends it to the Ollama API. Never raises,
        returns False on failure.

        Args:
            model: ModelRecord to push
            model_name: Custom name for model in Ollama (default: modelarr/{author}-{name})

        Returns:
            True if successful, False otherwise
        """
        try:
            if not model_name:
                model_name = f"modelarr/{model.author}-{model.name}"

            modelfile = self.generate_modelfile(model)

            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(
                    f"{self.host}/api/create",
                    json={"name": model_name, "modelfile": modelfile},
                )
                response.raise_for_status()

            logger.info(f"Pushed model to Ollama: {model_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to push model to Ollama: {e}")
            return False

    def list_models(self) -> list[dict]:  # type: ignore[type-arg]
        """List all models currently in Ollama.

        Returns:
            List of model dicts (or empty list on failure)
        """
        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.get(f"{self.host}/api/tags")
                response.raise_for_status()
                data = response.json()
                models: list[dict] = data.get("models", [])  # type: ignore[assignment]
                return models
        except Exception as e:
            logger.error(f"Failed to list Ollama models: {e}")
            return []

    def delete_model(self, name: str) -> bool:
        """Delete a model from Ollama.

        Args:
            name: Name of model to delete

        Returns:
            True if successful, False otherwise
        """
        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.request(
                    "DELETE",
                    f"{self.host}/api/delete",
                    json={"name": name},
                )
                response.raise_for_status()
            logger.info(f"Deleted model from Ollama: {name}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete Ollama model: {e}")
            return False

    def is_connected(self) -> bool:
        """Check if Ollama is running and accessible.

        Returns:
            True if Ollama is reachable, False otherwise
        """
        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.get(f"{self.host}/api/tags")
                return response.status_code == 200
        except Exception:
            return False
