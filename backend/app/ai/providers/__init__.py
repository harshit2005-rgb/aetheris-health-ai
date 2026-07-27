"""LLM provider adapters behind one interface.

The **only** place in the codebase permitted to import a vendor SDK
(Anthropic, OpenAI, Groq, Ollama). Everything else goes through
:mod:`app.ai.services`.
"""
