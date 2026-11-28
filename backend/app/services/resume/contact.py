"""The contact details a user types for their resume. Each function returns what
to store, None for a blank, and raises `ValueError` with a message for the user.
"""
import re

from app.services.resume.analysis.shared_signals import PHONE_PATTERN

_LINKEDIN_PROFILE = re.compile(
    r"(?:https?://)?(?:[a-z]{2,3}\.)?linkedin\.com/in/(?P<name>[^/?#\s\"'<>]+)/?(?:[?#]\S*)?", re.IGNORECASE,
)


def phone_number(value: str | None) -> str | None:
    number = " ".join((value or "").split())
    if not number:
        return None
    # The same rule the ATS checks use, so a saved number is one they find.
    if not PHONE_PATTERN.fullmatch(number):
        raise ValueError("Enter a phone number of 9 to 15 digits, with its country code if it is shorter.")
    return number


def linkedin_profile_url(value: str | None) -> str | None:
    """The profile's address in one form. Anything but a LinkedIn profile is
    refused, since this becomes a link on the resume.
    """
    address = (value or "").strip()
    if not address:
        return None
    match = _LINKEDIN_PROFILE.fullmatch(address)
    if match is None:
        raise ValueError("Enter your LinkedIn profile link, like linkedin.com/in/your-name.")
    return f"https://www.linkedin.com/in/{match['name']}"
