import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.browser_act import BrowserTaskError, act, execute_safe_action, plan_action


async def test_plan_action_parses_model_json(monkeypatch):
    async def fake_generate(_prompt, json_mode=False):
        assert json_mode
        return json.dumps({"action": "done", "answer": "Example Domain"})

    monkeypatch.setattr("app.browser_act.generate", fake_generate)
    action = await plan_action("Read the heading", "https://example.com", "Example Domain")
    assert action["action"] == "done"
    assert action["answer"] == "Example Domain"


async def test_execute_blocks_unsafe_form_click():
    control = AsyncMock()
    control.evaluate = AsyncMock(side_effect=[True])  # inside form
    page = MagicMock()
    page.locator.return_value.first = control
    with pytest.raises(BrowserTaskError, match="Unsafe browser click"):
        await execute_safe_action(page, {"action": "click", "selector": "button"})


async def test_act_returns_plan_and_execute_trace(monkeypatch):
    plans = [
        {"action": "scroll"},
        {"action": "done", "answer": "Done"},
    ]

    async def fake_generate(_prompt, json_mode=False):
        return json.dumps(plans.pop(0))

    monkeypatch.setattr("app.browser_act.generate", fake_generate)
    monkeypatch.setattr("app.browser_act.assert_public_url", AsyncMock())

    page = AsyncMock()
    page.url = "https://example.com"
    page.content = AsyncMock(return_value="<html><body><p>Example Domain</p></body></html>")
    page.goto = AsyncMock()
    page.wait_for_timeout = AsyncMock()
    body = MagicMock()
    body.inner_text = AsyncMock(return_value="Example Domain")
    page.locator = MagicMock(return_value=body)
    page.mouse.wheel = AsyncMock()

    context = AsyncMock()
    context.pages = [page]
    context.close = AsyncMock()

    playwright = MagicMock()
    playwright.chromium.launch_persistent_context = AsyncMock(return_value=context)
    playwright.__aenter__ = AsyncMock(return_value=playwright)
    playwright.__aexit__ = AsyncMock(return_value=None)

    monkeypatch.setattr("app.browser_act.async_playwright", lambda: playwright)
    monkeypatch.setattr("app.browser_act.open_persistent_page", AsyncMock(return_value=(context, page)))

    result = await act("Read the page", "https://example.com")
    assert result["isSuccess"] is True
    assert result["result"] == "Done"
    assert [entry["phase"] for entry in result["trace"]] == ["plan", "execute", "plan", "execute"]
    assert result["trace"][0]["action"] == "scroll"
    assert result["trace"][1]["outcome"] == "executed"
    assert result["trace"][3]["outcome"] == "completed"


async def test_act_attaches_trace_when_safety_blocks(monkeypatch):
    async def fake_generate(_prompt, json_mode=False):
        return json.dumps({"action": "click", "selector": "input[type=submit]"})

    monkeypatch.setattr("app.browser_act.generate", fake_generate)
    monkeypatch.setattr("app.browser_act.assert_public_url", AsyncMock())

    control = AsyncMock()
    control.evaluate = AsyncMock(side_effect=["button", True])
    page = AsyncMock()
    page.url = "https://example.com"

    def locator(selector):
        if selector == "body":
            body = MagicMock()
            body.inner_text = AsyncMock(return_value="Example")
            return body
        target = MagicMock()
        target.first = control
        return target

    page.locator = locator
    page.content = AsyncMock(return_value="<html><body><p>Example</p></body></html>")
    page.goto = AsyncMock()
    page.wait_for_timeout = AsyncMock()

    context = AsyncMock()
    context.pages = [page]
    context.close = AsyncMock()
    playwright = MagicMock()
    playwright.chromium.launch_persistent_context = AsyncMock(return_value=context)
    playwright.__aenter__ = AsyncMock(return_value=playwright)
    playwright.__aexit__ = AsyncMock(return_value=None)
    monkeypatch.setattr("app.browser_act.async_playwright", lambda: playwright)
    monkeypatch.setattr("app.browser_act.open_persistent_page", AsyncMock(return_value=(context, page)))

    with pytest.raises(BrowserTaskError) as error:
        await act("Submit the form", "https://example.com")
    assert error.value.trace[-1]["outcome"] == "blocked"
    assert error.value.trace[0]["phase"] == "plan"


async def test_act_waits_for_human_then_continues(monkeypatch):
    async def fake_generate(_prompt, json_mode=False):
        return json.dumps({"action": "done", "answer": "Visible after login"})

    monkeypatch.setattr("app.browser_act.generate", fake_generate)
    monkeypatch.setattr("app.browser_act.assert_public_url", AsyncMock())
    monkeypatch.setattr("app.browser_act.settings.human_challenge", True)

    captcha = AsyncMock()
    captcha.url = "https://example.com/login"
    captcha.content = AsyncMock(return_value="<html><body>Just a moment...</body></html>")
    captcha.wait_for_timeout = AsyncMock()

    ready = AsyncMock()
    ready.url = "https://example.com/app"
    ready.content = AsyncMock(return_value="<html><body><p>Dashboard</p></body></html>")
    ready.wait_for_timeout = AsyncMock()
    body = MagicMock()
    body.inner_text = AsyncMock(return_value="Dashboard")
    ready.locator = MagicMock(return_value=body)

    captcha_ctx = AsyncMock()
    captcha_ctx.close = AsyncMock()
    ready_ctx = AsyncMock()
    ready_ctx.close = AsyncMock()
    opens = [(captcha_ctx, captcha), (ready_ctx, ready)]

    async def fake_open(_playwright, _url, *, headless):
        return opens.pop(0)

    async def fake_wait(page, *, timeout_secs):
        assert page is ready
        assert timeout_secs > 0
        return "<html><body><p>Dashboard</p></body></html>"

    playwright = MagicMock()
    playwright.__aenter__ = AsyncMock(return_value=playwright)
    playwright.__aexit__ = AsyncMock(return_value=None)
    monkeypatch.setattr("app.browser_act.async_playwright", lambda: playwright)
    monkeypatch.setattr("app.browser_act.open_persistent_page", fake_open)
    monkeypatch.setattr("app.browser_act.wait_until_cleared", fake_wait)

    result = await act("Read the dashboard", "https://example.com/login")
    assert result["isSuccess"] is True
    assert result["result"] == "Visible after login"
    assert opens == []

