import unittest
from datetime import datetime, timezone
from uuid import uuid4
from unittest.mock import AsyncMock, patch

from app.core.config import settings
from app.core.enum import VisibilityType
from app.schemas.snippet import SnippetResponse, SnippetVersionResponse
from app.schemas.user import UserMeta
from app.services import snippet_service


def _build_snippet_response(
    short_id: str,
    visibility: VisibilityType = VisibilityType.PUBLIC,
) -> SnippetResponse:
    now = datetime.now(timezone.utc)
    return SnippetResponse(
        id=uuid4(),
        short_id=short_id,
        title="Sample snippet",
        author=UserMeta(
            id=uuid4(),
            email="integration.user@example.com",
            username="integration-user",
        ),
        created_at=now,
        views=3,
        latest_version=2,
        current_version=SnippetVersionResponse(
            version=2,
            content="print('hello world')",
            visibility=visibility,
            expires_at=None,
            view=3,
        ),
    )


class SnippetServiceUnitTests(unittest.IsolatedAsyncioTestCase):
    def test_cache_key_uses_latest_when_version_missing(self):
        self.assertEqual(
            snippet_service._cache_key("AbCd1234"),
            "snippet:AbCd1234:vlatest",
        )
        self.assertEqual(
            snippet_service._cache_key("AbCd1234", 7),
            "snippet:AbCd1234:v7",
        )

    def test_payload_serialization_round_trip(self):
        payload = {"short_id": "AbCd1234", "title": "naïve café"}

        encoded = snippet_service._serialize_payload(payload)
        decoded = snippet_service._deserialize_payload(encoded)

        self.assertIsInstance(encoded, bytes)
        self.assertEqual(decoded, payload)

    async def test_redis_get_with_retry_returns_none_after_failures(self):
        redis = AsyncMock()
        redis.get = AsyncMock(side_effect=[RuntimeError("down"), RuntimeError("still down")])

        with patch("app.services.snippet_service.asyncio.sleep", new=AsyncMock()) as sleep_mock:
            result = await snippet_service.redis_get_with_retry(redis, "snippet:missing")

        self.assertIsNone(result)
        self.assertEqual(redis.get.await_count, 2)
        self.assertEqual(sleep_mock.await_count, 2)

    async def test_get_snippet_cached_returns_cached_payload_without_db_query(self):
        cached_snippet = _build_snippet_response("AbCd1234")
        cached_payload = snippet_service._serialize_payload(
            cached_snippet.model_dump(mode="json")
        )

        redis = AsyncMock()
        redis.setex = AsyncMock()

        with (
            patch("app.services.snippet_service.get_redis", return_value=redis),
            patch(
                "app.services.snippet_service.redis_get_with_retry",
                new=AsyncMock(return_value=cached_payload),
            ),
            patch(
                "app.services.snippet_service.snippet_out_view",
                new=AsyncMock(),
            ) as snippet_out_view_mock,
        ):
            result = await snippet_service.get_snippet_cached(
                short_id="AbCd1234",
                version=None,
                db_session=AsyncMock(),
                user=None,
            )

        self.assertEqual(result.short_id, "AbCd1234")
        snippet_out_view_mock.assert_not_awaited()
        redis.setex.assert_not_awaited()

    async def test_get_snippet_cached_miss_caches_public_payload(self):
        redis = AsyncMock()
        redis.setex = AsyncMock(return_value=True)

        db_snippet = _build_snippet_response("EfGh5678", visibility=VisibilityType.PUBLIC)

        with (
            patch("app.services.snippet_service.get_redis", return_value=redis),
            patch(
                "app.services.snippet_service.redis_get_with_retry",
                new=AsyncMock(return_value=None),
            ),
            patch(
                "app.services.snippet_service.snippet_out_view",
                new=AsyncMock(return_value=db_snippet),
            ),
        ):
            result = await snippet_service.get_snippet_cached(
                short_id="EfGh5678",
                version=None,
                db_session=AsyncMock(),
                user=None,
            )

        self.assertEqual(result.short_id, "EfGh5678")
        redis.setex.assert_awaited_once()
        setex_key, setex_ttl, setex_payload = redis.setex.await_args.args
        self.assertEqual(setex_key, "snippet:EfGh5678:vlatest")
        self.assertEqual(setex_ttl, settings.CACHE_TTL_SECONDS)
        self.assertEqual(
            snippet_service._deserialize_payload(setex_payload)["short_id"],
            "EfGh5678",
        )

    async def test_get_snippet_cached_miss_does_not_cache_private_payload(self):
        redis = AsyncMock()
        redis.setex = AsyncMock(return_value=True)

        db_snippet = _build_snippet_response("IjKl9012", visibility=VisibilityType.PRIVATE)

        with (
            patch("app.services.snippet_service.get_redis", return_value=redis),
            patch(
                "app.services.snippet_service.redis_get_with_retry",
                new=AsyncMock(return_value=None),
            ),
            patch(
                "app.services.snippet_service.snippet_out_view",
                new=AsyncMock(return_value=db_snippet),
            ),
        ):
            result = await snippet_service.get_snippet_cached(
                short_id="IjKl9012",
                version=None,
                db_session=AsyncMock(),
                user=None,
            )

        self.assertEqual(result.short_id, "IjKl9012")
        redis.setex.assert_not_awaited()
