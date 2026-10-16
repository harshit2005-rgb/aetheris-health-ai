"""Backend test suite.

Layout mirrors ``docs/11-TESTING_STRATEGY.md``:

- ``unit/`` — services with mocked repositories, plus utils and AI helpers. No DB.
- ``repository/`` — real DB, transactional rollback per test. Every repository
  method needs at least one test that verifies ``hospital_id`` filtering.
- ``api/`` — real app + real DB, transactional rollback. Auth via test JWT helper.
- ``integration/`` — cross-module flows.
- ``ai_eval/`` — prompt evaluation against golden sets.
"""
