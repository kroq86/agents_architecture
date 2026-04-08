"""Allow ``python -m app.worker`` (same as ``python -m app.worker.main`` / ``agent-worker``)."""

from app.worker.main import main

if __name__ == "__main__":
    main()
