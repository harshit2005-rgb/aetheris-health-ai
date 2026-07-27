"""Versioned prompt registry.

Prompts are data, not code: templates live under ``templates/<module>/<name>.yaml``
and are resolved by key through the registry so they can be versioned, diffed,
and evaluated independently of application releases.
"""
