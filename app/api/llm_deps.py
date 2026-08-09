"""FastAPI dependencies for injectable adapters (LLM, etc.)."""

from app.adapters.llm import LLMAdapter, get_llm_adapter


def get_llm() -> LLMAdapter:
    """Production path: Groq. Tests override this dependency with FakeLLMAdapter."""
    return get_llm_adapter()
