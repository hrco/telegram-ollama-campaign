import asyncio
import logging
from datetime import datetime, timezone, timedelta
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


# ==================== GLOBAL SCHEDULER API ====================

# Global instance — set by main.py at startup via init_scheduler()
campaign_scheduler: Optional[CampaignScheduler] = None


def init_scheduler(bot):
    """Initialize the global scheduler instance"""
    global campaign_scheduler
    campaign_scheduler = CampaignScheduler(bot)
    return campaign_scheduler


async def start_scheduler():
    """Start the scheduler"""
    global campaign_scheduler
    if campaign_scheduler is None:
        logger.warning("Scheduler not initialized with bot yet")
        return
    campaign_scheduler.start()


async def stop_scheduler():
    """Stop the scheduler"""
    global campaign_scheduler
    if campaign_scheduler:
        campaign_scheduler.stop()


async def reconcile_pending_posts() -> int:
    """Re-register every pending scheduled post with the live scheduler.

    APScheduler jobs live in memory only, so on restart the DB still knows
    about pending posts but the scheduler does not. Call this once at startup,
    after the scheduler is started, so nothing scheduled before a restart is
    lost. Past-due posts are nudged a few seconds out so they still fire.
    """
    global campaign_scheduler
    if campaign_scheduler is None:
        logger.warning("reconcile_pending_posts called before scheduler init")
        return 0

    from database import list_pending_scheduled_posts

    posts = await list_pending_scheduled_posts()
    count = 0
    now = datetime.now(timezone.utc)
    for post in posts:
        cron = post.get("recurring_cron")
        if cron:
            campaign_scheduler.schedule_recurring(post["id"], cron)
            count += 1
            continue
        try:
            run_at = datetime.fromisoformat(post["scheduled_at"])
        except (TypeError, ValueError):
            logger.error(f"Post {post['id']} has unparseable scheduled_at={post['scheduled_at']!r}; skipping")
            continue
        if run_at.tzinfo is None:
            run_at = run_at.replace(tzinfo=timezone.utc)
        if run_at <= now:
            run_at = now + timedelta(seconds=5)
        campaign_scheduler.schedule_post(post["id"], run_at)
        count += 1
    logger.info(f"Reconciled {count} pending scheduled post(s)")
    return count
