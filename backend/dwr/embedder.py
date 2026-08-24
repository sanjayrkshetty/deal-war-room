"""Embedder singleton (`dwr/embedder.py`).

Model + revision are env-pinned; the revision is recorded on every embedding
row so silent upstream model updates can never invalidate stored vectors.
"""

from __future__ import annotations

import threading

import numpy as np

from dwr.config import get_settings

_MODEL_LOCK = threading.Lock()
_model = None
_loaded_revision: str | None = None


class EmbedderUnavailable(RuntimeError):
    pass


def _load():
    global _model, _loaded_revision
    with _MODEL_LOCK:
        if _model is not None:
            return _model
        from sentence_transformers import SentenceTransformer

        settings = get_settings()
        kwargs: dict = {"device": "cpu"}
        if settings.embed_model_revision:
            kwargs["revision"] = settings.embed_model_revision
        try:
            model = SentenceTransformer(settings.embed_model_name, **kwargs)
        except Exception as exc:
            raise EmbedderUnavailable(f"embedder init failed: {exc}") from exc
        _model = model
        _loaded_revision = settings.embed_model_revision or "unpinned"
        return _model


def try_init_embedder() -> bool:
    try:
        _load()
        return True
    except Exception:
        return False


def embedder_ready() -> bool:
    return _model is not None


def loaded_model_tag() -> str:
    settings = get_settings()
    revision = _loaded_revision or settings.embed_model_revision or "unpinned"
    return f"{settings.embed_model_name}@{revision}"


def encode_texts(texts: list[str]) -> np.ndarray:
    model = _model
    if model is None:
        raise EmbedderUnavailable("embedder not initialized")
    vectors = model.encode(
        texts,
        batch_size=32,
        convert_to_numpy=True,
        normalize_embeddings=True,
        show_progress_bar=False,
    )
    return np.asarray(vectors, dtype=np.float32)
