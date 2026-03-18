import unittest
from uuid import UUID, uuid4
from unittest.mock import AsyncMock, patch

from httpx import ASGITransport, AsyncClient
from sqlalchemy.engine import make_url
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.v1.routes import snippet as snippet_routes
from app.core.config import settings
from app.db.base import Base
from app.db.database import get_async_session
from app.main import app
from app.models.snippet import Snippet
from app.models.snippet_version import SnippetVersion
from app.models.user import User


def _candidate_database_urls() -> list[str]:
	candidates: list[str] = [settings.DATABASE_URL]

	try:
		url = make_url(settings.DATABASE_URL)
		if url.host in {"db", "postgres", "postgresql"}:
			localhost_url = url.set(host="localhost").render_as_string(
				hide_password=False
			)
			if localhost_url not in candidates:
				candidates.append(localhost_url)
	except Exception:
		if "@db:" in settings.DATABASE_URL:
			candidates.append(settings.DATABASE_URL.replace("@db:", "@localhost:"))

	return candidates


class SnippetApiIntegrationTests(unittest.IsolatedAsyncioTestCase):
	async def asyncSetUp(self):
		self.engine = None
		last_exception = None

		for db_url in _candidate_database_urls():
			candidate_engine = create_async_engine(db_url, echo=False)
			try:
				async with candidate_engine.begin() as conn:
					await conn.run_sync(Base.metadata.create_all)
				self.engine = candidate_engine
				break
			except Exception as exc:
				last_exception = exc
				await candidate_engine.dispose()

		if self.engine is None:
			self.skipTest(f"Integration DB is unavailable: {last_exception}")

		self.connection = await self.engine.connect()

		self.schema_name = f"test_{uuid4().hex[:10]}"
		await self.connection.execute(text(f'CREATE SCHEMA "{self.schema_name}"'))
		await self.connection.execute(text(f'SET search_path TO "{self.schema_name}"'))
		await self.connection.commit()
		await self.connection.run_sync(Base.metadata.create_all)
		await self.connection.commit()

		self.session_factory = async_sessionmaker(
			bind=self.connection,
			class_=AsyncSession,
			expire_on_commit=False,
		)

		async with self.session_factory() as session:
			self.user = User(
				email=f"snippet-int-{uuid4().hex}@example.com",
				username=f"snippet-user-{uuid4().hex[:10]}",
				hashed_password="integration-test-only",
				is_active=True,
				is_superuser=False,
				is_verified=True,
			)
			session.add(self.user)
			await session.commit()
			await session.refresh(self.user)

		async def override_get_async_session():
			async with self.session_factory() as session:
				yield session

		async def override_current_user():
			return self.user

		async def override_optional_user():
			return None

		app.dependency_overrides[get_async_session] = override_get_async_session
		app.dependency_overrides[snippet_routes.current_user] = override_current_user
		app.dependency_overrides[snippet_routes.optional_user] = override_optional_user

		self.redis_mock = AsyncMock()
		self.redis_mock.get = AsyncMock(return_value=None)
		self.redis_mock.setex = AsyncMock(return_value=True)
		self.redis_mock.zadd = AsyncMock(return_value=1)
		self.redis_mock.incr = AsyncMock(return_value=1)

		self.patchers = [
			patch("app.rate_limiter.decorator.rate_limiter", new=AsyncMock()),
			patch(
				"app.services.snippet_service.enqueue",
				new=AsyncMock(return_value="job-id"),
			),
			patch(
				"app.services.snippet_service.get_redis",
				return_value=self.redis_mock,
			),
		]

		for patcher in self.patchers:
			patcher.start()

		self.client = AsyncClient(
			transport=ASGITransport(app=app),
			base_url="http://testserver",
		)

	async def asyncTearDown(self):
		if hasattr(self, "client"):
			await self.client.aclose()

		if hasattr(self, "patchers"):
			for patcher in reversed(self.patchers):
				patcher.stop()

		app.dependency_overrides.clear()

		if hasattr(self, "connection"):
			if hasattr(self, "schema_name"):
				try:
					await self.connection.rollback()
				except Exception:
					pass

				try:
					await self.connection.execute(
						text(f'DROP SCHEMA IF EXISTS "{self.schema_name}" CASCADE')
					)
					await self.connection.commit()
				except Exception:
					pass

			await self.connection.close()
		if hasattr(self, "engine"):
			await self.engine.dispose()

	async def _create_snippet(self, title: str, content: str, visibility: str = "public"):
		response = await self.client.post(
			"/v1/api/snippet/",
			json={
				"title": title,
				"content": content,
				"visibility": visibility,
			},
		)
		self.assertEqual(response.status_code, 201, response.text)
		return response.json()

	async def test_create_snippet_persists_in_database(self):
		created = await self._create_snippet(
			title="First Snippet",
			content="print('create path')",
			visibility="public",
		)

		snippet_id = UUID(created["id"])

		async with self.session_factory() as session:
			snippet = (
				await session.execute(select(Snippet).where(Snippet.id == snippet_id))
			).scalar_one()

			version = (
				await session.execute(
					select(SnippetVersion).where(
						SnippetVersion.snippet_id == snippet_id,
						SnippetVersion.version == 1,
					)
				)
			).scalar_one()

		self.assertEqual(snippet.title, "First Snippet")
		self.assertEqual(snippet.author_id, self.user.id)
		self.assertEqual(snippet.views, 0)
		self.assertEqual(version.content, "print('create path')")
		self.assertEqual(created["current_version"]["version"], 1)

	async def test_update_snippet_creates_new_version_and_updates_counter(self):
		created = await self._create_snippet(
			title="Version One",
			content="print('v1')",
			visibility="public",
		)

		snippet_id = UUID(created["id"])

		update_response = await self.client.put(
			f"/v1/api/snippet/{snippet_id}",
			json={
				"title": "Version Two",
				"content": "print('v2')",
			},
		)

		self.assertEqual(update_response.status_code, 200, update_response.text)
		updated = update_response.json()

		async with self.session_factory() as session:
			snippet = (
				await session.execute(select(Snippet).where(Snippet.id == snippet_id))
			).scalar_one()

			version_count = (
				await session.execute(
					select(func.count(SnippetVersion.id)).where(
						SnippetVersion.snippet_id == snippet_id
					)
				)
			).scalar_one()

		self.assertEqual(snippet.title, "Version Two")
		self.assertEqual(snippet.version_counter, 2)
		self.assertEqual(version_count, 2)
		self.assertEqual(updated["latest_version"], 2)
		self.assertEqual(updated["current_version"]["version"], 2)
		self.assertEqual(updated["current_version"]["content"], "print('v2')")

	async def test_get_shared_public_snippet_returns_latest_payload(self):
		created = await self._create_snippet(
			title="Read Me",
			content="print('read')",
			visibility="public",
		)

		short_id = created["short_id"]
		response = await self.client.get(f"/v1/api/snippet/{short_id}")

		self.assertEqual(response.status_code, 200, response.text)
		body = response.json()
		self.assertEqual(body["short_id"], short_id)
		self.assertEqual(body["current_version"]["content"], "print('read')")

	async def test_get_shared_private_snippet_denies_anonymous_access(self):
		created = await self._create_snippet(
			title="Private Snippet",
			content="print('private')",
			visibility="private",
		)

		response = await self.client.get(f"/v1/api/snippet/{created['short_id']}")

		self.assertEqual(response.status_code, 403, response.text)
		payload = response.json()
		self.assertEqual(payload["error"]["code"], "SNIPPET_ACCESS_RESTRICTION")

	async def test_delete_snippet_soft_deletes_row(self):
		created = await self._create_snippet(
			title="Delete Me",
			content="print('delete')",
			visibility="public",
		)

		snippet_id = UUID(created["id"])
		delete_response = await self.client.delete(f"/v1/api/snippet/{snippet_id}")
		self.assertEqual(delete_response.status_code, 204, delete_response.text)

		async with self.session_factory() as session:
			visible = (
				await session.execute(select(Snippet).where(Snippet.id == snippet_id))
			).scalar_one_or_none()
			include_deleted_stmt = (
				select(Snippet)
				.execution_options(include_deleted=True)
				.where(Snippet.id == snippet_id)
			)
			deleted = (await session.execute(include_deleted_stmt)).scalar_one_or_none()

		self.assertIsNone(visible)
		self.assertIsNotNone(deleted)
		self.assertIsNotNone(deleted.deleted_at)

