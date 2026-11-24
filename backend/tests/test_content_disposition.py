from urllib.parse import unquote

from app.api.resume import _content_disposition


def test_plain_filename_is_kept():
    header = _content_disposition("my_resume.pdf")
    assert header.startswith('inline; filename="my_resume.pdf"')


def test_quotes_and_line_breaks_cannot_break_out_of_the_header():
    header = _content_disposition('evil".pdf\r\nX-Injected: yes')
    assert "\r" not in header and "\n" not in header
    # exactly the two quotes that delimit the fallback filename
    assert header.split("; filename*=")[0].count('"') == 2
    assert unquote(header.split("filename*=UTF-8''")[1]) == 'evil".pdf\r\nX-Injected: yes'


def test_non_ascii_name_gets_an_ascii_fallback_and_an_encoded_original():
    header = _content_disposition("résumé.pdf")
    assert 'filename="r_sum_.pdf"' in header
    assert "filename*=UTF-8''r%C3%A9sum%C3%A9.pdf" in header


def test_empty_name_falls_back():
    assert 'filename="resume.pdf"' in _content_disposition("")
