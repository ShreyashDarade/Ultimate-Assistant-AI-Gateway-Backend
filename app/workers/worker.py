"""arq worker settings + task registry."""

from arq.connections import RedisSettings

from app.core.config import settings
from app.workers.tasks.video_generation import generate_video
from app.workers.tasks.batch_transcribe import batch_transcribe
from app.workers.tasks.file_processing import process_file


class WorkerSettings:
    functions = [generate_video, batch_transcribe, process_file]
    redis_settings = RedisSettings.from_dsn(settings.REDIS_URL)
    max_jobs = 10
    job_timeout = 600  # 10 min max per job
