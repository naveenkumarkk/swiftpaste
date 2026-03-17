import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from app.jobs.tasks import (
    CLEANUP_EXPIRED_DELAY_SECONDS,
    RECOVER_STUCK_JOBS_DELAY_SECONDS,
    cleanup_expired,
    recover_stuck_jobs,
)


class JobTaskTests(unittest.IsolatedAsyncioTestCase):
    async def test_cleanup_expired_reschedules_when_no_entries_exist(self):
        redis = AsyncMock()
        redis.zrangebyscore.return_value = []

        with (
            patch("app.jobs.tasks.get_redis", return_value=redis),
            patch("app.jobs.tasks.enqueue", new=AsyncMock()) as enqueue_mock,
        ):
            await cleanup_expired()

        enqueue_mock.assert_awaited_once_with(
            "cleanup_expired",
            {},
            delay=CLEANUP_EXPIRED_DELAY_SECONDS,
        )

    async def test_cleanup_expired_invalidates_short_id_cache_keys(self):
        redis = MagicMock()
        redis.zrangebyscore = AsyncMock(return_value=["snippet:abcd1234:2"])
        pipe = MagicMock()
        pipe.zrem = MagicMock()
        pipe.delete = MagicMock()
        pipe.execute = AsyncMock()
        redis.pipeline.return_value = pipe

        with (
            patch("app.jobs.tasks.get_redis", return_value=redis),
            patch("app.jobs.tasks._resolve_legacy_short_ids", new=AsyncMock(return_value={})),
            patch("app.jobs.tasks.enqueue", new=AsyncMock()) as enqueue_mock,
        ):
            await cleanup_expired()

        pipe.zrem.assert_called_once_with("snippets:expiry", "snippet:abcd1234:2")
        pipe.delete.assert_any_call("snippet:abcd1234:v2")
        pipe.delete.assert_any_call("snippet:abcd1234:vlatest")
        pipe.execute.assert_awaited_once()
        enqueue_mock.assert_awaited_once_with(
            "cleanup_expired",
            {},
            delay=CLEANUP_EXPIRED_DELAY_SECONDS,
        )

    async def test_recover_stuck_jobs_reschedules_when_no_jobs_are_stuck(self):
        redis = AsyncMock()
        redis.lrange.return_value = []

        with (
            patch("app.jobs.tasks.get_redis", return_value=redis),
            patch("app.jobs.tasks.enqueue", new=AsyncMock()) as enqueue_mock,
        ):
            await recover_stuck_jobs()

        enqueue_mock.assert_awaited_once_with(
            "recover_stuck_jobs",
            {},
            delay=RECOVER_STUCK_JOBS_DELAY_SECONDS,
        )