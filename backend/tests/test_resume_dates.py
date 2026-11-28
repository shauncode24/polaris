"""Reading dates as resumes and LinkedIn write them."""
from datetime import date

import pytest

from app.services.resume.dates import date_columns, is_ongoing, last_day


@pytest.mark.parametrize("written, first, last", [
    ("Jun 2025", date(2025, 6, 1), date(2025, 6, 30)),
    ("June 2025", date(2025, 6, 1), date(2025, 6, 30)),
    ("Sept. 2024", date(2024, 9, 1), date(2024, 9, 30)),
    ("Feb, 2024", date(2024, 2, 1), date(2024, 2, 29)),
    ("Jun'25", date(2025, 6, 1), date(2025, 6, 30)),
    ("2023", date(2023, 1, 1), date(2023, 12, 31)),
    ("Expected 2027", date(2027, 1, 1), date(2027, 12, 31)),
    ("Expected Graduation: May 2027", date(2027, 5, 1), date(2027, 5, 31)),
    ("Summer 2024", date(2024, 1, 1), date(2024, 12, 31)),
    ("06/2025", date(2025, 6, 1), date(2025, 6, 30)),
    ("2025-06", date(2025, 6, 1), date(2025, 6, 30)),
    ("2025-06-15", date(2025, 6, 15), date(2025, 6, 15)),
    ("15 June 2025", date(2025, 6, 15), date(2025, 6, 15)),
    ("June 15th, 2025", date(2025, 6, 15), date(2025, 6, 15)),
    ("03/04/2025", date(2025, 1, 1), date(2025, 12, 31)),  # which is the month is unknown
])
def test_a_stated_date_is_read_without_adding_to_it(written, first, last):
    columns = date_columns(written)

    assert (columns["start_date"], columns["start_date_text"]) == (first, written)
    assert last_day(written) == last


@pytest.mark.parametrize("written", [
    "Present", "Market 2025", "13/2025", "31 February 2025", "June 25", "last year", "1830",
])
def test_unreadable_wording_is_kept_without_a_date(written):
    columns = date_columns(None, written)

    assert columns == {"start_date": None, "end_date": None, "start_date_text": None, "end_date_text": written}
    assert last_day(written) is None


@pytest.mark.parametrize("value", [None, "", "  ", "null", "N/A", "-"])
def test_nothing_stated_is_nothing_stored(value):
    assert set(date_columns(value, value).values()) == {None}


@pytest.mark.parametrize("written, start, end", [
    ("Jan 2022 - Present", "Jan 2022", "Present"),
    ("Jan 2022 – Mar 2023 · 1 yr 3 mos", "Jan 2022", "Mar 2023"),
    ("Jun 2025 to Aug 2025", "Jun 2025", "Aug 2025"),
    ("2019-2023", "2019", "2023"),
    ("2019 - 2023", "2019", "2023"),
    ("06/2022-08/2023", "06/2022", "08/2023"),
    ("May 2024—Jul 2024", "May 2024", "Jul 2024"),
    ("2022-06", "2022-06", None),
    ("Oct 2021 · 3 mos", "Oct 2021", None),
])
def test_a_range_given_as_one_value_is_split(written, start, end):
    columns = date_columns(written)

    assert (columns["start_date_text"], columns["end_date_text"]) == (start, end)


def test_separate_values_are_left_as_they_are():
    assert date_columns("Aug 2023", "Present") == {
        "start_date": date(2023, 8, 1), "end_date": None,
        "start_date_text": "Aug 2023", "end_date_text": "Present",
    }


def test_a_lone_education_date_is_the_finish():
    assert date_columns("2027", lone_date_is_end=True)["end_date_text"] == "2027"
    assert date_columns("2027", lone_date_is_end=True)["start_date_text"] is None
    both = date_columns("2023 - 2027", lone_date_is_end=True)
    assert (both["start_date_text"], both["end_date_text"]) == ("2023", "2027")


def test_long_text_is_cut_to_fit():
    assert len(date_columns(None, "x" * 200)["end_date_text"]) == 50


def test_ongoing_words():
    assert all(is_ongoing(w) for w in ("Present", " current ", "Till date", "Ongoing"))
    assert not any(is_ongoing(w) for w in (None, "2025", "Expected 2027"))
