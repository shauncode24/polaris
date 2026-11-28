"""Reading a typed phone number or LinkedIn address, finding phone numbers in a
resume, and telling spellings of one name apart. No model, no database.
"""
import pytest

from app.services.resume.analysis.shared_signals import has_email, has_linkedin, has_phone
from app.services.resume.contact import linkedin_profile_url, phone_number
from app.services.resume.skill_names import same_name

PHONES = [
    "+1 555 123 4567", "+1 (555) 123-4567", "(555) 123 4567", "555.123.4567", "9876543210",
    "98765 43210", "+91 98765 43210", "+91-98765-43210", "+44 20 7946 0958", "+65 9123 4567",
]


@pytest.mark.parametrize("number", PHONES)
def test_common_ways_of_writing_a_phone_number_are_read_and_found(number):
    assert phone_number(f"  {number} ") == number
    assert has_phone(f"Sam Rivera\nsam@x.test | {number} | Pune")
    assert has_phone(f"Ph.{number}")
    assert has_email(f"sam@x.test | {number}")


@pytest.mark.parametrize("text", [
    "2019-2023", "2019 - 2023", "2019 – 2023", "Jun 2019–Dec 2023", "01.06.2023", "GPA 8.4/10",
    "2019\n2023\n2024", "Served 1,000,000 users", "Version 1.2.3", "ID AB1234567890",
])
def test_dates_and_figures_are_not_phone_numbers(text):
    assert not has_phone(text)


@pytest.mark.parametrize("value", ["12345678", "call me", "+91 98765 43210 ext 4", "1" * 16, "98765 / 43210"])
def test_something_else_is_not_saved_as_a_phone_number(value):
    with pytest.raises(ValueError, match="phone number"):
        phone_number(value)


@pytest.mark.parametrize("typed", [
    "linkedin.com/in/sam-rivera", "www.linkedin.com/in/sam-rivera/", "https://linkedin.com/in/sam-rivera",
    "HTTPS://WWW.LinkedIn.com/in/sam-rivera?utm=x", " https://in.linkedin.com/in/sam-rivera ",
])
def test_a_linkedin_address_is_stored_in_one_form(typed):
    saved = linkedin_profile_url(typed)

    assert saved == "https://www.linkedin.com/in/sam-rivera"
    assert has_linkedin(saved)


@pytest.mark.parametrize("typed", [
    "sam-rivera", "javascript:alert(1)//linkedin.com/in/x", "https://evil.test/linkedin.com/in/x",
    "https://linkedin.com.evil.test/in/x", "https://notlinkedin.com/in/x", "linkedin.com/company/acme",
    "linkedin.com/in/", "linkedin.com/in/a b", "linkedin.com/in/sam/details",
])
def test_anything_but_a_linkedin_profile_is_refused(typed):
    with pytest.raises(ValueError, match="LinkedIn"):
        linkedin_profile_url(typed)


@pytest.mark.parametrize("blank", [None, "", "   "])
def test_a_blank_removes_the_detail(blank):
    assert phone_number(blank) is None
    assert linkedin_profile_url(blank) is None


@pytest.mark.parametrize(("first", "second"), [
    ("Postgres", "PostgreSQL"), ("k8s", "Kubernetes"), ("REST API", "RESTful API"), ("Node JS", "node.js"),
    ("python", "Python"),
])
def test_spellings_of_one_name(first, second):
    assert same_name(first, second)


@pytest.mark.parametrize(("first", "second"), [
    ("version control", "Git"), ("REST API", "REST APIs"), ("SQL", "PostgreSQL"), ("Java", "JavaScript"),
    ("Node", "Node.js"), ("unit testing", "testing"),
])
def test_different_names(first, second):
    assert not same_name(first, second)
