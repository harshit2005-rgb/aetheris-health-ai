"""Pydantic DTOs used at the API boundary.

Request and response models only — never SQLAlchemy models. Every inbound
payload is validated here before it reaches a service
(``docs/07-SECURITY.md``, rule 5).

Placement rule (``docs/09-PROJECT_STRUCTURE.md``): a new schema goes in
``app/schemas/<domain>.py``; shared pagination/envelope/error shapes go in
``app/schemas/common.py``.
"""
