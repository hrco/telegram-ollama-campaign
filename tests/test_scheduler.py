import asyncio
import os
import pytest

os.environ["DB_PATH"] = ":memory:"


@pytest.fixture(scope="function")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.mark.asyncio
async def test_scheduler_starts_and_stops():
    from scheduler import CampaignScheduler
    sched = CampaignScheduler(bot=None)
    sched.start()
    assert sched.scheduler.running
    sched.stop()
    # Just verify it doesn't crash on stop
    assert True


@pytest.mark.asyncio
async def test_schedule_one_shot_returns_job_id():
    from scheduler import CampaignScheduler
    from datetime import datetime, timedelta, timezone
    sched = CampaignScheduler(bot=None)
    sched.start()
    run_at = datetime.now(timezone.utc) + timedelta(hours=1)
    job_id = sched.schedule_post(post_id=1, run_at=run_at)
    assert job_id is not None
    sched.cancel_job(job_id)
    sched.stop()


@pytest.mark.asyncio
async def test_cancel_nonexistent_job_returns_false():
    from scheduler import CampaignScheduler
    sched = CampaignScheduler(bot=None)
    sched.start()
    result = sched.cancel_job("nonexistent-job-id")
    assert result is False
    sched.stop()
