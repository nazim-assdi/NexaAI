from __future__ import annotations


OLLAMA_MODEL_KEY = "qwen25-1_5b-instruct"
OLLAMA_MODEL_ID = "hf.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF:Q4_K_M"
OLLAMA_MODEL_NAME = "Qwen2.5 1.5B Instruct"
OLLAMA_MODEL_SIZE = "About 1.12 GB"

MODEL_CATALOG = {
    OLLAMA_MODEL_KEY: {
        "id": OLLAMA_MODEL_ID,
        "name": OLLAMA_MODEL_NAME,
        "description": "Small instruction-tuned Hugging Face model for multilingual chat, coding help and everyday assistance.",
        "role": "Default local assistant",
        "size_label": OLLAMA_MODEL_SIZE,
        "source": "Hugging Face · Qwen",
        "license": "Apache 2.0",
        "recommended": True,
    },
}
