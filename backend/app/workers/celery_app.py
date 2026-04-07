"""
Celery application factory.

Why Celery over asyncio background tasks:
- FastAPI's BackgroundTasks run in the same process/event loop — heavy work blocks
- Celery workers are separate processes — AI calls don't affect request latency
- Task queue survives server restarts (tasks don't get lost)
- Built-in retry, rate limiting, and result storage
- Scales independently (run more Celery workers without more API workers)

Tasks that go to Celery:
- Title generation (LLM call, ~1s)
- Conversation summarization (LLM call, ~3s)
- Memory extraction (LLM call, ~2s)
- Document embedding (vector generation, ~5s for large docs)
- Email notifications (network call)

Tasks that stay synchronous (in-request):
- DB reads (fast async queries)
- Cache lookups
- Token counting (CPU-bound but <1ms)

Task routing: all tasks use the 'default' queue in Phase 1.
Phase 3: separate queues for priority levels (high/default/low).
"""

from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "lumina",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=[
        "app.workers.tasks.title_generation",
        "app.workers.tasks.memory_extraction",
        "app.workers.tasks.summarization",
        "app.workers.tasks.document_indexing",
    ],
)

celery_app.conf.update(
    # Serialization
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,

    # Task behavior
    task_acks_late=True,            # Ack after task completes, not when received
    task_reject_on_worker_lost=True,  # Re-queue if worker crashes mid-task
    task_track_started=True,

    # Retry defaults
    task_max_retries=3,
    task_default_retry_delay=60,    # 1 minute between retries

    # Result expiry
    result_expires=3600,            # 1 hour

    # Rate limits (per worker)
    task_annotations={
        "app.workers.tasks.title_generation.generate_title_task": {"rate_limit": "30/m"},
        "app.workers.tasks.memory_extraction.extract_memory_task": {"rate_limit": "20/m"},
    },

    # Beat schedule (Phase 2: periodic tasks)
    # beat_schedule={
    #     "cleanup-old-generations": {
    #         "task": "app.workers.tasks.cleanup.cleanup_old_data",
    #         "schedule": crontab(hour=3, minute=0),  # 3am UTC daily
    #     }
    # }
)
