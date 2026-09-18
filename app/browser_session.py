"""Explicit operator-owned browser sessions.

The API may open a headed Chromium window, but the operator is responsible for
typing credentials and completing CAPTCHA challenges.  A session keeps its
Playwright context alive between requests and persists only Playwright's
storage state locally so a later scrape can use the same cookies and local
storage without exposing them through the API.
"""
from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from playwright.async_api import Error as PlaywrightError
from playwright.async_api import async_playwright

from app.config import settings
from app.human_challenge import chromium_args, looks_like_human_gate

SESSION_ID_RE = re.compile(r"^local_browser_session_[0-9a-f]{32}$")


class BrowserSessionError(Exception):
    def __init__(self, message: str, *, code: str = "browser_session_failed", status_code: int = 502):
        super().__init__(message)
        self.code = code
        self.status_code = status_code


class BrowserSessionNotFound(BrowserSessionError):
    def __init__(self, session_id: str):
        super().__init__(
            f"Browser session {session_id} does not exist or has expired.",
            code="browser_session_not_found",
            status_code=404,
        )


class BrowserSessionNotReady(BrowserSessionError):
    def __init__(self, session_id: str):
        super().__init__(
            f"Complete login or the human challenge in the headed browser for session {session_id}, then retry.",
            code="browser_session_not_ready",
            status_code=409,
        )


@dataclass
class BrowserSession:
    session_id: str
    start_url: str
    current_url: str
    created_at: str
    updated_at: str
    storage_path: Path
    context: Any
    browser: Any
    playwright: Any
    page: Any
    status: str = "awaiting_operator"
    operation_lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    def output(self) -> dict[str, object]:
        output = {
            "sessionId": self.session_id,
            "startUrl": self.start_url,
            "currentUrl": self.current_url,
            "status": self.status,
            "ready": self.status == "ready",
            "createdAt": self.created_at,
            "updatedAt": self.updated_at,
        }
        if self.status == "awaiting_operator":
            output["instructions"] = (
                "Complete login or the CAPTCHA in the headed Chromium window, "
                "then call the resume scrape endpoint."
            )
        return output


class BrowserSessionManager:
    def __init__(self) -> None:
        self._sessions: dict[str, BrowserSession] = {}
        self._registry_lock = asyncio.Lock()

    @staticmethod
    def _session_dir() -> Path:
        path = Path(settings.data_dir) / "browser-sessions"
        path.mkdir(parents=True, exist_ok=True)
        return path

    @classmethod
    def _storage_path(cls, session_id: str) -> Path:
        return cls._session_dir() / f"{session_id}.state.json"

    @classmethod
    def _metadata_path(cls, session_id: str) -> Path:
        return cls._session_dir() / f"{session_id}.json"

    @staticmethod
    def _now() -> str:
        return datetime.now(UTC).isoformat()

    @staticmethod
    def _status_for(html: str, url: str) -> str:
        return "awaiting_operator" if looks_like_human_gate(html, url) else "ready"

    @staticmethod
    def _validate_id(session_id: str) -> None:
        if not SESSION_ID_RE.fullmatch(session_id):
            raise BrowserSessionNotFound(session_id)

    async def _save_storage(self, session: BrowserSession) -> None:
        await session.context.storage_state(path=str(session.storage_path))
        try:
            session.storage_path.chmod(0o600)
        except OSError:
            # The state is still inside the configured local data directory;
            # chmod is best effort on filesystems that do not support it.
            pass

    async def _save_metadata(self, session: BrowserSession) -> None:
        metadata_path = self._metadata_path(session.session_id)
        metadata_path.write_text(
            json.dumps(
                {
                    "sessionId": session.session_id,
                    "startUrl": session.start_url,
                    "createdAt": session.created_at,
                    "updatedAt": session.updated_at,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        try:
            metadata_path.chmod(0o600)
        except OSError:
            pass

    @staticmethod
    async def _cleanup_resources(context: Any, browser: Any, playwright: Any) -> None:
        if context is not None:
            await context.close()
        elif browser is not None:
            await browser.close()
        if playwright is not None:
            await playwright.stop()

    async def _refresh_locked(self, session: BrowserSession) -> None:
        try:
            html = await session.page.content()
            session.current_url = session.page.url
        except PlaywrightError as error:
            session.status = "closed"
            raise BrowserSessionError(
                "The browser session is no longer available.",
                code="browser_session_closed",
                status_code=410,
            ) from error
        session.status = self._status_for(html, session.current_url)
        session.updated_at = self._now()
        await self._save_storage(session)
        await self._save_metadata(session)

    async def _register(self, session: BrowserSession) -> None:
        async with self._registry_lock:
            self._sessions[session.session_id] = session

    async def create(self, start_url: str) -> dict[str, object]:
        from app.scraper import assert_public_url

        await assert_public_url(start_url)
        session_id = f"local_browser_session_{uuid4().hex}"
        storage_path = self._storage_path(session_id)
        playwright = None
        browser = None
        context = None
        try:
            playwright = await async_playwright().start()
            browser = await playwright.chromium.launch(
                headless=False,
                args=chromium_args(headless=False),
            )
            context = await browser.new_context(
                user_agent=settings.user_agent,
                viewport={"width": 1280, "height": 900},
            )
            page = await context.new_page()
            await page.goto(
                start_url,
                wait_until="domcontentloaded",
                timeout=int(settings.request_timeout_secs * 1000),
            )
            await page.wait_for_timeout(400)
            html = await page.content()
            current_url = page.url
            await assert_public_url(current_url)
            now = self._now()
            session = BrowserSession(
                session_id=session_id,
                start_url=start_url,
                current_url=current_url,
                created_at=now,
                updated_at=now,
                storage_path=storage_path,
                context=context,
                browser=browser,
                playwright=playwright,
                page=page,
                status=self._status_for(html, current_url),
            )
            await self._save_storage(session)
            await self._save_metadata(session)
            await self._register(session)
            return session.output()
        except BrowserSessionError:
            await self._cleanup_resources(context, browser, playwright)
            raise
        except PlaywrightError as error:
            await self._cleanup_resources(context, browser, playwright)
            raise BrowserSessionError("Could not open the headed browser session.") from error
        except Exception:
            await self._cleanup_resources(context, browser, playwright)
            raise

    async def _find_or_restore(self, session_id: str) -> BrowserSession:
        self._validate_id(session_id)
        async with self._registry_lock:
            session = self._sessions.get(session_id)
        if session is not None:
            return session

        metadata_path = self._metadata_path(session_id)
        storage_path = self._storage_path(session_id)
        if not metadata_path.exists() or not storage_path.exists():
            raise BrowserSessionNotFound(session_id)
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            start_url = metadata["startUrl"]
            created_at = metadata["createdAt"]
        except (OSError, ValueError, KeyError) as error:
            raise BrowserSessionNotFound(session_id) from error

        from app.scraper import FetchFailure, assert_public_url

        try:
            await assert_public_url(start_url)
        except FetchFailure as error:
            raise BrowserSessionError(
                "The persisted browser session points at an invalid public URL.",
                code="browser_session_invalid",
                status_code=410,
            ) from error
        playwright = None
        browser = None
        context = None
        try:
            playwright = await async_playwright().start()
            browser = await playwright.chromium.launch(
                headless=False,
                args=chromium_args(headless=False),
            )
            context = await browser.new_context(
                storage_state=str(storage_path),
                user_agent=settings.user_agent,
                viewport={"width": 1280, "height": 900},
            )
            page = await context.new_page()
            await page.goto(
                start_url,
                wait_until="domcontentloaded",
                timeout=int(settings.request_timeout_secs * 1000),
            )
            await page.wait_for_timeout(400)
            now = self._now()
            session = BrowserSession(
                session_id=session_id,
                start_url=start_url,
                current_url=page.url,
                created_at=created_at,
                updated_at=now,
                storage_path=storage_path,
                context=context,
                browser=browser,
                playwright=playwright,
                page=page,
            )
            await self._refresh_locked(session)
            await self._register(session)
            return session
        except BrowserSessionError:
            await self._cleanup_resources(context, browser, playwright)
            raise
        except PlaywrightError as error:
            await self._cleanup_resources(context, browser, playwright)
            raise BrowserSessionError("Could not restore the browser session.") from error

    async def get(self, session_id: str) -> dict[str, object]:
        session = await self._find_or_restore(session_id)
        async with session.operation_lock:
            await self._refresh_locked(session)
            return session.output()

    async def require_ready(self, session_id: str) -> BrowserSession:
        session = await self._find_or_restore(session_id)
        async with session.operation_lock:
            await self._refresh_locked(session)
            if session.status != "ready":
                raise BrowserSessionNotReady(session_id)
        return session

    async def render(self, session_id: str, url: str) -> tuple[str, str]:
        from app.scraper import assert_public_url, FetchFailure

        await assert_public_url(url)
        session = await self._find_or_restore(session_id)
        async with session.operation_lock:
            await self._refresh_locked(session)
            if session.status != "ready":
                raise BrowserSessionNotReady(session_id)
            try:
                await session.page.goto(
                    url,
                    wait_until="domcontentloaded",
                    timeout=int(settings.request_timeout_secs * 1000),
                )
                await session.page.wait_for_timeout(400)
                html = await session.page.content()
                final_url = session.page.url
                await assert_public_url(final_url)
                session.current_url = final_url
                session.status = self._status_for(html, final_url)
                session.updated_at = self._now()
                await self._save_storage(session)
                await self._save_metadata(session)
            except PlaywrightError as error:
                raise FetchFailure("fetch_error", "Browser session navigation failed") from error
            if session.status != "ready":
                raise BrowserSessionNotReady(session_id)
            return html, final_url

    async def close(self, session_id: str) -> bool:
        session = await self._find_or_restore(session_id)
        async with session.operation_lock:
            try:
                await session.context.close()
            finally:
                await session.playwright.stop()
        async with self._registry_lock:
            self._sessions.pop(session_id, None)
        for path in (session.storage_path, self._metadata_path(session_id)):
            try:
                path.unlink()
            except FileNotFoundError:
                pass
        return True

    async def close_all(self) -> None:
        async with self._registry_lock:
            session_ids = list(self._sessions)
        for session_id in session_ids:
            try:
                await self.close(session_id)
            except BrowserSessionError:
                pass


browser_sessions = BrowserSessionManager()
