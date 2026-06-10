import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger

logger = logging.getLogger(__name__)


class CampaignScheduler:
    def __init__(self, bot):
        self.bot = bot
        self.scheduler = AsyncIOScheduler(timezone="UTC")

    def start(self):
        self.scheduler.start()
        logger.info("Scheduler started")

    def stop(self):
        self.scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")

    def schedule_post(self, post_id: int, run_at: datetime) -> str:
        job_id = f"post_{post_id}"
        self.scheduler.add_job(
            self._execute_post,
            trigger=DateTrigger(run_date=run_at),
            args=[post_id],
            id=job_id,
            replace_existing=True,
        )
        logger.info(f"Scheduled post {post_id} at {run_at}")
        return job_id

    def schedule_recurring(self, post_id: int, cron_expr: str) -> str:
        job_id = f"recurring_{post_id}"
        minute, hour, dom, month, dow = cron_expr.split()
        self.scheduler.add_job(
            self._execute_post,
            trigger=CronTrigger(minute=minute, hour=hour, day=dom, month=month, day_of_week=dow),
            args=[post_id],
            id=job_id,
            replace_existing=True,
        )
        logger.info(f"Scheduled recurring post {post_id} cron={cron_expr}")
        return job_id

    def cancel_job(self, job_id: str) -> bool:
        job = self.scheduler.get_job(job_id)
        if job:
            job.remove()
            return True
        return False

    def get_upcoming_jobs(self, limit: int = 20) -> list:
        jobs = self.scheduler.get_jobs()
        return [
            {
                "job_id": job.id,
                "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
            }
            for job in jobs[:limit]
        ]

    async def _execute_post(self, post_id: int):
        from database import get_scheduled_post, get_channel, update_post_status, record_send_analytics
        from broadcaster import send_with_retry

        post = await get_scheduled_post(post_id)
        if not post:
            logger.error(f"Post {post_id} not found for execution")
            return

        channel = await get_channel(post["channel_id"])
        if not channel:
            logger.error(f"Channel {post['channel_id']} not found")
            await update_post_status(post_id, "failed", error="Channel not found")
            return

        now = datetime.now(timezone.utc).isoformat()
        try:
            msg_id = await send_with_retry(self.bot, channel["chat_id"], post["content"])
            await update_post_status(post_id, "sent", sent_at=now)
            await record_send_analytics(post_id, msg_id, "sent")
            logger.info(f"Post {post_id} sent to {channel['chat_id']}, message_id={msg_id}")
        except Exception as e:
            await update_post_status(post_id, "failed", error=str(e))
            await record_send_analytics(post_id, None, "failed")
            logger.error(f"Post {post_id} failed: {e}")


# Global instance — set by main.py at startup
campaign_scheduler: Optional[CampaignScheduler] = None