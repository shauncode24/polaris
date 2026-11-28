"""Limits on how often a caller may ask. No database: the requests made here are
refused, or fail validation, before anything is read.
"""
import ipaddress

import pytest
from fastapi.testclient import TestClient

from app.core import rate_limit
from app.core.rate_limit import SlidingWindow, client_address
from app.core.settings import ConfigurationError, Settings, settings
from app.main import app

ORIGIN = settings.frontend_origin
PROXY = "10.0.0.1"


def networks(*entries):
    return [ipaddress.ip_network(entry) for entry in entries]


class Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


@pytest.fixture
def limits(monkeypatch):
    """Sets the limits for one test; unnamed ones are off. Counts start empty."""
    def use(*, requests=0, sign_ins=0):
        monkeypatch.setattr(rate_limit.requests, "limit", requests)
        monkeypatch.setattr(rate_limit.sign_ins, "limit", sign_ins)

    for window in (rate_limit.requests, rate_limit.sign_ins):
        window.clear()
    yield use
    for window in (rate_limit.requests, rate_limit.sign_ins):
        window.clear()


def client(address: str = "203.0.113.5") -> TestClient:
    return TestClient(app, client=(address, 50000))


def sign_in(caller, **headers):
    """An incomplete sign-in: refused as invalid without reaching the database."""
    return caller.post("/auth/login", json={}, headers=headers)


# --- the window --------------------------------------------------------------

def test_a_key_gets_its_hits_back_as_they_leave_the_window():
    clock = Clock()
    window = SlidingWindow(2, 60, clock)
    assert window.hit("a") is None
    clock.now += 20
    assert window.hit("a") is None
    assert window.hit("a") == 40  # until the first one is a minute old
    clock.now += 39.5
    assert window.hit("a") == 1  # never "try again in 0 seconds"
    clock.now += 0.5
    assert window.hit("a") is None
    assert window.hit("a") == 20


def test_refused_hits_are_not_counted():
    clock = Clock()
    window = SlidingWindow(1, 60, clock)
    window.hit("a")
    for _ in range(100):
        clock.now += 0.1
        assert window.hit("a") is not None
    clock.now += 50
    assert window.hit("a") is None


def test_each_key_is_counted_by_itself():
    window = SlidingWindow(1, 60, Clock())
    assert window.hit("a") is None
    assert window.hit("b") is None
    assert window.hit("a") is not None


@pytest.mark.parametrize("limit", [0, -1])
def test_no_limit_remembers_nothing(limit):
    window = SlidingWindow(limit, 60, Clock())
    assert all(window.hit("a") is None for _ in range(50))
    assert len(window) == 0


def test_idle_keys_are_forgotten_and_busy_ones_kept():
    clock = Clock()
    window = SlidingWindow(2, 60, clock)
    for caller in range(500):
        window.hit(caller)
    clock.now += 30
    window.hit("busy")
    window.hit("busy")
    assert len(window) == 501

    clock.now += 30  # the 500 are now a window old; "busy" is not
    window.hit("new")
    assert len(window) == 2
    assert window.hit("busy") is not None  # its count survived the clear-out


# --- who is calling ----------------------------------------------------------

def test_the_header_is_ignored_unless_the_peer_is_a_trusted_proxy():
    claimed = ["198.51.100.7"]
    assert client_address("203.0.113.5", claimed, []) == "203.0.113.5"
    assert client_address("203.0.113.5", claimed, networks(PROXY)) == "203.0.113.5"
    assert client_address(PROXY, claimed, networks(PROXY)) == "198.51.100.7"


def test_what_the_caller_wrote_left_of_the_real_address_is_not_believed():
    header = ["1.1.1.1, 2.2.2.2, 198.51.100.7"]  # the proxy added the last one
    assert client_address(PROXY, header, networks(PROXY)) == "198.51.100.7"


def test_a_chain_of_proxies_is_read_back_to_the_first_untrusted_address():
    trusted = networks("10.0.0.0/8", "192.0.2.10")
    header = ["1.1.1.1, 198.51.100.7, 192.0.2.10", "10.2.3.4"]  # two headers, read in order
    assert client_address(PROXY, header, trusted) == "198.51.100.7"
    assert client_address(PROXY, ["10.9.9.9, 10.2.3.4"], trusted) == "10.9.9.9"


@pytest.mark.parametrize("header", [[], [""], ["unknown"], ["198.51.100.7, not-an-address"]])
def test_a_header_that_cannot_be_read_leaves_the_proxy_as_the_caller(header):
    assert client_address(PROXY, header, networks(PROXY)) == PROXY


@pytest.mark.parametrize("written, address", [
    ("198.51.100.7:443", "198.51.100.7"),
    (" 198.51.100.7 ", "198.51.100.7"),
    ("[2001:db8::1]:443", "2001:db8::1"),
    ("[2001:db8::1]", "2001:db8::1"),
    ("2001:DB8:0:0:0:0:0:1", "2001:db8::1"),
    ("::ffff:198.51.100.7", "198.51.100.7"),
])
def test_addresses_are_read_however_a_proxy_writes_them(written, address):
    assert client_address(PROXY, [written], networks(PROXY)) == address


def test_a_proxy_seen_as_an_ipv4_mapped_address_is_still_trusted():
    assert client_address(f"::ffff:{PROXY}", ["198.51.100.7"], networks(PROXY)) == "198.51.100.7"


# --- the setting -------------------------------------------------------------

def test_trusted_proxies_are_read_from_the_environment(monkeypatch):
    monkeypatch.setenv("TRUSTED_PROXIES", " 127.0.0.1, 10.0.0.0/8 ,,2001:db8::/32")
    assert Settings().trusted_proxies == networks("127.0.0.1", "10.0.0.0/8", "2001:db8::/32")
    monkeypatch.setenv("TRUSTED_PROXIES", "")
    assert Settings().trusted_proxies == []


@pytest.mark.parametrize("value", ["*", "my-proxy", "10.0.0.1/8", "0.0.0.0/0", "::/0"])
def test_a_proxy_list_that_is_wrong_or_trusts_everyone_stops_the_server(monkeypatch, value):
    monkeypatch.setenv("TRUSTED_PROXIES", value)
    with pytest.raises(ConfigurationError, match="TRUSTED_PROXIES"):
        Settings()


# --- through the app ---------------------------------------------------------

def test_sign_in_attempts_have_their_own_stricter_limit(limits):
    limits(requests=100, sign_ins=3)
    caller = client()
    assert [sign_in(caller).status_code for _ in range(3)] == [422] * 3

    refused = sign_in(caller)
    assert refused.status_code == 429
    wait = int(refused.headers["retry-after"])
    assert 1 <= wait <= settings.rate_limit_window_seconds
    assert refused.json() == {"detail": f"Too many sign-in attempts. Try again in {wait} seconds."}


@pytest.mark.parametrize("path", ["/auth/register", "/auth/google", "/auth/anything-added-later"])
def test_every_way_of_signing_in_shares_that_limit(limits, path):
    limits(sign_ins=1)
    caller = client()
    sign_in(caller)
    assert caller.post(path, json={}).status_code == 429


def test_the_sign_in_limit_leaves_other_requests_alone(limits):
    limits(sign_ins=1)
    caller = client()
    sign_in(caller)
    assert sign_in(caller).status_code == 429
    # Reading who is signed in and renewing the session happen on every page load.
    assert [caller.get("/auth/me").status_code for _ in range(5)] == [401] * 5
    assert [caller.post("/auth/refresh").status_code for _ in range(5)] == [401] * 5
    assert [caller.post("/auth/logout").status_code for _ in range(5)] == [204] * 5
    assert caller.get("/projects").status_code == 401


def test_one_address_does_not_use_up_anothers_attempts(limits):
    limits(sign_ins=1)
    sign_in(client("203.0.113.5"))
    assert sign_in(client("203.0.113.5")).status_code == 429
    assert sign_in(client("203.0.113.6")).status_code == 422


def test_a_new_forwarded_header_does_not_get_a_caller_new_attempts(limits):
    limits(sign_ins=2)
    caller = client()
    statuses = [sign_in(caller, **{"X-Forwarded-For": f"198.51.100.{n}"}).status_code for n in range(4)]
    assert statuses == [422, 422, 429, 429]


def test_behind_a_trusted_proxy_each_caller_is_counted_separately(limits, monkeypatch):
    limits(sign_ins=1)
    monkeypatch.setattr(settings, "trusted_proxies", networks(PROXY))
    proxy = client(PROXY)
    assert sign_in(proxy, **{"X-Forwarded-For": "198.51.100.1"}).status_code == 422
    assert sign_in(proxy, **{"X-Forwarded-For": "198.51.100.2"}).status_code == 422
    # The same caller again, with something invented in front.
    assert sign_in(proxy, **{"X-Forwarded-For": "9.9.9.9, 198.51.100.1"}).status_code == 429


def test_addresses_in_one_ipv6_subnet_are_counted_together(limits):
    limits(sign_ins=1)
    assert sign_in(client("2001:db8:1:2::1")).status_code == 422
    assert sign_in(client("2001:db8:1:2:ffff:ffff:ffff:ffff")).status_code == 429
    assert sign_in(client("2001:db8:1:3::1")).status_code == 422


def test_all_requests_from_an_address_are_limited_except_the_health_check(limits):
    limits(requests=2)
    caller = client()
    assert [caller.get("/projects").status_code for _ in range(2)] == [401] * 2
    refused = caller.get("/projects")
    assert refused.status_code == 429
    assert refused.json()["detail"].startswith("Too many requests. Try again in ")
    assert caller.get("/health").status_code == 200


def test_the_browser_can_read_a_refusal(limits):
    limits(sign_ins=1)
    caller = client()
    sign_in(caller, Origin=ORIGIN)
    refused = sign_in(caller, Origin=ORIGIN)
    assert refused.status_code == 429
    assert refused.headers["access-control-allow-origin"] == ORIGIN


def test_the_browser_can_read_a_refusal_of_an_oversized_request(limits, monkeypatch):
    limits()
    monkeypatch.setattr(settings, "max_request_body_bytes", 10)
    refused = client().post("/auth/login", content=b"x" * 11, headers={"Origin": ORIGIN})
    assert refused.status_code == 413
    assert refused.headers["access-control-allow-origin"] == ORIGIN


def test_preflight_requests_are_not_counted(limits):
    limits(requests=1, sign_ins=1)
    caller = client()
    preflight = {"Origin": ORIGIN, "Access-Control-Request-Method": "POST"}
    assert [caller.options("/auth/login", headers=preflight).status_code for _ in range(5)] == [200] * 5
    assert sign_in(caller).status_code == 422


# --- session settings --------------------------------------------------------

@pytest.mark.parametrize("origin, samesite, secure", [
    ("http://localhost:5173", "lax", False),
    ("https://polaris.example", "lax", True),
    ("https://polaris.example", "Strict", True),
    ("http://localhost:5173", "none", True),  # browsers require it
])
def test_when_the_sign_in_cookie_is_https_only(monkeypatch, origin, samesite, secure):
    monkeypatch.setenv("FRONTEND_ORIGIN", origin)
    monkeypatch.setenv("COOKIE_SAMESITE", samesite)
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")  # required with https
    monkeypatch.setenv("MAIL_FROM", "polaris@example.com")
    assert Settings().cookie_secure is secure
    assert Settings().cookie_samesite == samesite.lower()


@pytest.mark.parametrize("name, value", [
    ("COOKIE_SAMESITE", "sometimes"), ("ACCESS_TOKEN_MINUTES", "0"), ("REFRESH_TOKEN_DAYS", "-1"),
])
def test_a_session_setting_that_would_break_sign_in_stops_the_server(monkeypatch, name, value):
    monkeypatch.setenv(name, value)
    with pytest.raises(ConfigurationError, match=name):
        Settings()


def test_the_old_week_long_setting_is_ignored(monkeypatch):
    monkeypatch.setenv("JWT_EXPIRE_MINUTES", "10080")
    assert Settings().access_token_minutes == 15
