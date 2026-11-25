from __future__ import annotations


OLLAMA_MODEL_KEY = "gemma3-1b"
OLLAMA_MODEL_ID = "gemma3:1b"
OLLAMA_MODEL_NAME = "Gemma 3 1B"
OLLAMA_MODEL_SIZE = "About 806 MB"

MODEL_CATALOG = {
    OLLAMA_MODEL_KEY: {
        "id": OLLAMA_MODEL_ID,
        "name": OLLAMA_MODEL_NAME,
        "description": "Small multilingual local assistant for fast chat, lightweight coding and automation planning.",
        "role": "Fast all-rounder",
        "size_label": OLLAMA_MODEL_SIZE,
        "source": "Ollama library · Google Gemma",
        "license": "Gemma Terms",
        "recommended": True,
    },
}
