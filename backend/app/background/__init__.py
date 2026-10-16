"""Background job worker and scheduler.

Long-running work never happens inline in a request. Jobs live in
``app/background/jobs/``; the worker entry point and periodic scheduler live
beside them.
"""
