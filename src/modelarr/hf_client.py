"""HuggingFace API client for model search and metadata retrieval."""

import re

from huggingface_hub import HfApi
from huggingface_hub import ModelInfo as HFModelInfo

from modelarr.models import ModelInfo


class HFClient:
    """Wrapper around huggingface_hub HfApi for model operations."""

    def __init__(self, token: str | None = None) -> None:
        """Initialize the HuggingFace API client.

        Args:
            token: Optional HuggingFace API token for authenticated requests
        """
        self.api = HfApi(token=token)
        self.token = token

    def search_models(
        self,
        query: str,
        author: str | None = None,
        sort: str = "downloads",
        limit: int = 20,
    ) -> list[ModelInfo]:
        """Search for models on HuggingFace.

        Args:
            query: Search query string
            author: Optional author filter
            sort: Sort field (downloads, recent, trending, default: downloads)
            limit: Maximum number of results

        Returns:
            List of ModelInfo objects matching the search
        """
        search_filter = None
        if author:
            search_filter = {"author": author}

        results = self.api.list_models(
            search=query,
            filter=search_filter,
            sort=sort,  # type: ignore[arg-type]
            limit=limit,
        )

        models = []
        for item in results:
            model_info = self._hf_model_to_modelinfo(item)
            if model_info:
                models.append(model_info)

        return models

    def get_model_info(self, repo_id: str) -> ModelInfo:
        """Get detailed information about a model.

        Args:
            repo_id: HuggingFace repo ID (e.g., "mlx-community/Qwen2.5-7B-MLX")

        Returns:
            ModelInfo with full details about the model
        """
        hf_info = self.api.model_info(repo_id)
        model_info = self._hf_model_to_modelinfo(hf_info)

        if not model_info:
            # Fallback if conversion failed
            repo_id_split = repo_id.split("/")
            model_info = ModelInfo(
                repo_id=repo_id,
                author=repo_id_split[0] if len(repo_id_split) > 0 else "unknown",
                name=repo_id_split[1] if len(repo_id_split) > 1 else repo_id,
            )

        return model_info

    def get_repo_files(self, repo_id: str) -> list[dict]:
        """List all files in a model repository.

        Args:
            repo_id: HuggingFace repo ID

        Returns:
            List of dicts with file information {name, size}
        """
        files = []
        try:
            file_refs = self.api.list_repo_files(repo_id)
            for file_ref in file_refs:
                files.append({"name": file_ref, "size": 0})
        except Exception:
            # If list_repo_files fails, try via model_info
            try:
                hf_info = self.api.model_info(repo_id)
                if hf_info.siblings:
                    for sibling in hf_info.siblings:
                        files.append(
                            {
                                "name": sibling.rfilename,
                                "size": sibling.size or 0,
                            }
                        )
            except Exception:
                pass

        return files

    def get_latest_commit(self, repo_id: str) -> str:
        """Get the latest commit SHA for a model repository.

        Args:
            repo_id: HuggingFace repo ID

        Returns:
            Latest commit SHA, or empty string if not available
        """
        try:
            info = self.api.model_info(repo_id)
            if hasattr(info, "last_modified") and info.last_modified:
                # Return a hash based on last_modified for consistency
                return info.last_modified.isoformat()
            return ""
        except Exception:
            return ""

    def list_author_models(self, author: str) -> list[ModelInfo]:
        """List all models by a specific author.

        Args:
            author: Author/organization name

        Returns:
            List of ModelInfo objects by the author
        """
        results = self.api.list_models(author=author)

        models = []
        for item in results:
            model_info = self._hf_model_to_modelinfo(item)
            if model_info:
                models.append(model_info)

        return models

    @staticmethod
    def detect_format(files: list[dict]) -> str | None:
        """Detect model format from file list.

        Args:
            files: List of file dicts with 'name' key

        Returns:
            Detected format (GGUF, MLX, safetensors) or None
        """
        filenames = [f.get("name", "").lower() for f in files]

        # Check for GGUF
        if any(f.endswith(".gguf") for f in filenames):
            return "GGUF"

        # Check for MLX
        has_safetensors = any(f.endswith(".safetensors") for f in filenames)
        has_mlx_config = any("config.json" in f for f in filenames)
        if has_safetensors and has_mlx_config:
            return "MLX"

        # Check for safetensors
        if has_safetensors:
            return "safetensors"

        # Check for PyTorch
        if any(f.endswith((".bin", ".pt", ".pth")) for f in filenames):
            return "PyTorch"

        return None

    @staticmethod
    def detect_quantization(filename: str) -> str | None:
        """Detect quantization from filename patterns.

        Args:
            filename: Model filename to analyze

        Returns:
            Detected quantization level or None
        """
        filename_lower = filename.lower()

        # Common quantization patterns
        patterns = [
            (r"q(\d+)_k_m", lambda m: f"Q{m.group(1)}_K_M"),
            (r"q(\d+)_k_s", lambda m: f"Q{m.group(1)}_K_S"),
            (r"q(\d+)_0", lambda m: f"Q{m.group(1)}_0"),
            (r"q(\d+)_1", lambda m: f"Q{m.group(1)}_1"),
            (r"(\d+)bit", lambda m: f"{m.group(1)}bit"),
            (r"fp16", lambda m: "fp16"),
            (r"bf16", lambda m: "bf16"),
            (r"float16", lambda m: "float16"),
            (r"float32", lambda m: "float32"),
        ]

        for pattern, handler in patterns:
            match = re.search(pattern, filename_lower)
            if match:
                return handler(match)

        return None

    @staticmethod
    def calculate_size(files: list[dict]) -> int:
        """Calculate total model size from file list.

        Args:
            files: List of file dicts with 'size' key (in bytes)

        Returns:
            Total size in bytes
        """
        return sum(f.get("size", 0) for f in files)

    @staticmethod
    def _hf_model_to_modelinfo(hf_info: HFModelInfo) -> ModelInfo | None:
        """Convert HuggingFace ModelInfo to our ModelInfo.

        Args:
            hf_info: HuggingFace ModelInfo object

        Returns:
            Our ModelInfo object or None if conversion fails
        """
        try:
            repo_id = hf_info.id if hasattr(hf_info, "id") else None
            if not repo_id:
                return None

            repo_split = repo_id.split("/")
            author = repo_split[0] if len(repo_split) > 0 else "unknown"
            name = repo_split[1] if len(repo_split) > 1 else repo_id

            # Get files and calculate size
            files = []
            total_size = 0

            if hf_info.siblings:
                for sibling in hf_info.siblings:
                    files.append(
                        {
                            "name": sibling.rfilename,
                            "size": sibling.size or 0,
                        }
                    )
                    total_size += sibling.size or 0

            # Detect format and quantization
            format_ = HFClient.detect_format(files)

            # Get quantization from largest model file if available
            quantization = None
            if files:
                largest_file = max(files, key=lambda f: int(str(f.get("size", 0))))
                quantization = HFClient.detect_quantization(str(largest_file.get("name", "")))

            # Extract tags
            tags = []
            if hasattr(hf_info, "tags") and hf_info.tags:
                tags = list(hf_info.tags)

            # Get download count
            downloads = None
            if hasattr(hf_info, "downloads"):
                downloads = hf_info.downloads

            # Get last modified
            last_modified = None
            if hasattr(hf_info, "last_modified") and hf_info.last_modified:
                last_modified = hf_info.last_modified

            return ModelInfo(
                repo_id=repo_id,
                author=author,
                name=name,
                files=files,
                last_modified=last_modified,
                tags=tags,
                downloads=downloads,
                format=format_,
                quantization=quantization,
                size_bytes=total_size if total_size > 0 else None,
            )

        except Exception:
            return None
