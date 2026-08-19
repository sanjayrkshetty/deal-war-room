"""
Unit Tests for RAG Memory Store (`tests/test_rag.py`)
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from engine.rag_store import RAGStore


def test_rag_store_initialization_and_chunk_addition(tmp_path):
    db_file = tmp_path / "test_memory.db"
    store = RAGStore(db_path=db_file)

    chunk_id = store.add_chunk(
        bu_tag="dfir",
        service_line="ca",
        title="Test Compromise Assessment",
        content="Endpoint IOC sweep for Acme Corp at test@sisa.com",
    )

    assert chunk_id > 0

    # Verify search retrieves anonymized content
    results = store.search_memory("endpoint ioc sweep", bu_tag="dfir")
    assert len(results) > 0
    assert "Acme Corp" not in results[0]["content"]
    assert "[CLIENT_NAME]" in results[0]["content"] or "[ORGANIZATION]" in results[0]["content"] or "Test Compromise Assessment" in results[0]["title"]


def test_rag_store_fallback_mechanism(tmp_path):
    db_file = tmp_path / "test_fallback.db"
    store = RAGStore(db_path=db_file)

    # Search for an un-indexed topic to trigger fallback
    results = store.search_memory("xyz_unmatched_query", bu_tag="vapt")
    assert len(results) > 0
    assert results[0]["is_fallback"] is True
    assert "OWASP" in results[0]["title"] or "PTES" in results[0]["title"]
