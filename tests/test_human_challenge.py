import pytest

from app.human_challenge import chromium_args, looks_like_human_gate, wait_until_cleared


def test_chromium_args_use_software_gl_for_headed_docker(monkeypatch):
    monkeypatch.setattr("app.human_challenge.Path.exists", lambda self: str(self) == "/.dockerenv")
    args = chromium_args(headless=False)
    assert "--disable-gpu" in args
    assert "--ozone-platform=x11" in args
    assert "--disable-gpu" not in chromium_args(headless=True)


CAPTCHA_HTML = "<html><body><h1>Just a moment...</h1><p>Checking your browser</p></body></html>"
LOGIN_HTML = """
<html><body>
  <h1>Sign in</h1>
  <form><label>Password</label><input type="password" name="pass"><button>Log in</button></form>
</body></html>
"""
ARTICLE_HTML = (
    "<html><body><article><h1>Public article</h1>"
    "<p>Hypertext Transfer Protocol is an application layer protocol.</p></article></body></html>"
)
FOOTER_LOGIN_HTML = (
    "<html><body><article><p>Long public article text about cooking pasta with tomatoes and garlic.</p></article>"
    "<footer><a href='/login'>Log in</a></footer></body></html>"
)


def test_human_gate_detects_captcha_and_password_form():
    assert looks_like_human_gate(CAPTCHA_HTML, "https://example.com/")
    assert looks_like_human_gate(LOGIN_HTML, "https://example.com/login")
    assert not looks_like_human_gate(ARTICLE_HTML, "https://example.com/article")
    assert not looks_like_human_gate(FOOTER_LOGIN_HTML, "https://example.com/recipe")


async def test_wait_until_cleared_returns_page_after_human_finishes():
    htmls = [CAPTCHA_HTML, CAPTCHA_HTML, ARTICLE_HTML]

    class Page:
        url = "https://example.com/article"

        async def content(self):
            return htmls.pop(0) if htmls else ARTICLE_HTML

    html = await wait_until_cleared(Page(), timeout_secs=2, poll_secs=0)
    assert "Public article" in html


async def test_wait_until_cleared_times_out_if_gate_stays():
    class Page:
        url = "https://example.com/challenge"

        async def content(self):
            return CAPTCHA_HTML

    with pytest.raises(TimeoutError):
        await wait_until_cleared(Page(), timeout_secs=0.05, poll_secs=0)
