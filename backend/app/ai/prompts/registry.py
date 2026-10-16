"""Versioned prompt template registry.

Prompts are data, not code. Templates live as YAML files under
``templates/<module>/<name>.yaml`` so they can be versioned, diffed,
reviewed, and evaluated independently of application releases.

The registry loads templates at startup, validates their schema, and
provides a typed resolution API for service code.

See ``docs/08-AI_ARCHITECTURE.md`` §4 for the full design.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import structlog
import yaml

logger = structlog.get_logger(__name__)


class PromptNotFoundError(KeyError):
    """Raised when a requested prompt template does not exist in the registry."""

    def __init__(self, prompt_id: str) -> None:
        self.prompt_id = prompt_id
        super().__init__(f"Prompt template '{prompt_id}' not found.")


class PromptValidationError(ValueError):
    """Raised when a prompt template fails schema validation."""

    def __init__(self, prompt_id: str, reason: str) -> None:
        self.prompt_id = prompt_id
        super().__init__(f"Prompt '{prompt_id}' validation failed: {reason}")


@dataclass(frozen=True)
class RenderedPrompt:
    """A fully rendered prompt ready to send to a provider.

    :param system: The system prompt text.
    :param messages: The conversation messages.
    :param prompt_id: The template ID used.
    :param prompt_version: The template version used.
    """

    system: str
    messages: list[dict[str, str]]
    prompt_id: str
    prompt_version: str


@dataclass
class PromptTemplate:
    """A single versioned prompt template loaded from a YAML file.

    :param id: Stable identifier (e.g. ``patient.summarize``).
    :param version: Semver version (e.g. ``1.2.0``).
    :param description: Human-readable description.
    :param model_hint: The capability hint this template prefers.
    :param system: The system prompt template string (Jinja2-style).
    :param user: The user prompt template string.
    :param input_schema: JSON Schema for the template's input variables.
    """

    id: str
    version: str
    description: str = ""
    model_hint: str = "fast"
    system: str = ""
    user: str = ""
    input_schema: dict[str, Any] = field(default_factory=dict)

    def render(self, **variables: Any) -> RenderedPrompt:
        """Render this template with the provided variables.

        :param variables: Template variable values.
        :returns: A :class:`RenderedPrompt` with the expanded text.
        """
        rendered_system = self._render_template(self.system, variables)
        rendered_user = self._render_template(self.user, variables)

        messages = []
        if rendered_system:
            messages.append({"role": "system", "content": rendered_system})
        messages.append({"role": "user", "content": rendered_user})

        return RenderedPrompt(
            system=rendered_system,
            messages=messages,
            prompt_id=self.id,
            prompt_version=self.version,
        )

    @staticmethod
    def _render_template(template: str, variables: dict[str, Any]) -> str:
        """Simple template rendering with ``{{ variable }}`` substitution.

        Uses basic string replacement. For complex templates, consider
        switching to Jinja2.
        """
        result = template
        for key, value in variables.items():
            placeholder = "{{ " + key + " }}"
            result = result.replace(placeholder, str(value))
            # Also handle {{key}} without spaces.
            result = result.replace("{{" + key + "}}", str(value))
        return result

    @classmethod
    def from_yaml(cls, path: Path) -> PromptTemplate:
        """Load a prompt template from a YAML file.

        :param path: Path to the YAML file.
        :returns: A :class:`PromptTemplate` instance.
        :raises PromptValidationError: If the YAML structure is invalid.
        """
        with open(path) as f:
            data = yaml.safe_load(f)

        if not isinstance(data, dict):
            raise PromptValidationError(path.stem, "YAML root is not a mapping.")

        required = {"id", "system", "user"}
        missing = required - set(data.keys())
        if missing:
            raise PromptValidationError(
                data.get("id", path.stem),
                f"Missing required fields: {', '.join(sorted(missing))}",
            )

        return cls(
            id=str(data["id"]),
            version=str(data.get("version", "0.1.0")),
            description=str(data.get("description", "")),
            model_hint=str(data.get("model_hint", "fast")),
            system=str(data["system"]),
            user=str(data["user"]),
            input_schema=data.get("input_schema", {}),
        )


class PromptRegistry:
    """Registry that loads, validates, and resolves prompt templates.

    Usage::

        registry = PromptRegistry()
        registry.load_all(templates_dir=Path(\"app/ai/prompts/templates\"))
        rendered = registry.render(\"patient.summarize\", patient=patient_data)
    """

    def __init__(self) -> None:
        self._templates: dict[str, PromptTemplate] = {}

    def load_all(self, templates_dir: str | Path) -> int:
        """Load all YAML prompt templates from a directory tree.

        :param templates_dir: Root directory to scan recursively.
        :returns: The number of templates loaded.
        :raises PromptValidationError: If any template is invalid.
        """
        base = Path(templates_dir)
        if not base.exists():
            logger.warning("prompt_templates_dir_not_found", path=str(base))
            return 0

        count = 0
        for yaml_path in sorted(base.rglob("*.yaml")):
            try:
                template = PromptTemplate.from_yaml(yaml_path)
                self.register(template)
                count += 1
            except PromptValidationError as exc:
                logger.error("prompt_template_load_failed", path=str(yaml_path), error=str(exc))
                raise
            except yaml.YAMLError as exc:
                raise PromptValidationError(
                    yaml_path.stem,
                    f"YAML parse error: {exc!s}",
                ) from exc

        logger.info("prompt_templates_loaded", count=count, directory=str(base))
        return count

    def register(self, template: PromptTemplate) -> None:
        """Register a single template.

        :param template: The template to register.
        """
        self._templates[template.id] = template
        logger.debug("prompt_template_registered", id=template.id, version=template.version)

    def get(self, prompt_id: str) -> PromptTemplate:
        """Retrieve a template by its ID.

        :param prompt_id: The stable template identifier.
        :returns: The :class:`PromptTemplate`.
        :raises PromptNotFoundError: If the ID is not registered.
        """
        template = self._templates.get(prompt_id)
        if template is None:
            raise PromptNotFoundError(prompt_id)
        return template

    def render(self, prompt_id: str, **variables: Any) -> RenderedPrompt:
        """Render a prompt template with variables.

        :param prompt_id: The stable template identifier.
        :param variables: Template variable values.
        :returns: The rendered prompt.
        """
        template = self.get(prompt_id)
        return template.render(**variables)

    @property
    def registered_ids(self) -> list[str]:
        """Return all registered prompt template IDs."""
        return list(self._templates.keys())


# Module-level singleton.
registry = PromptRegistry()


__all__ = [
    "PromptNotFoundError",
    "PromptRegistry",
    "PromptTemplate",
    "PromptValidationError",
    "RenderedPrompt",
    "registry",
]
