import pytest

from app.domain.urls import extract_video_id

VID = "dQw4w9WgXcQ"


@pytest.mark.parametrize("text", [
    f"https://www.youtube.com/watch?v={VID}",
    f"https://youtube.com/watch?v={VID}&t=30s",
    f"youtube.com/watch?v={VID}",
    f"https://youtu.be/{VID}",
    f"https://youtu.be/{VID}?si=abc",
    f"https://www.youtube.com/shorts/{VID}",
    f"https://www.youtube.com/embed/{VID}",
    f"https://m.youtube.com/watch?v={VID}",
    f"  https://www.youtube.com/watch?v={VID}  ",
])
def test_recognizes_valid_links(text):
    assert extract_video_id(text) == VID


@pytest.mark.parametrize("text", [
    "", "   ", None, "banana", "https://example.com/watch?v=" + VID,
    "https://www.youtube.com/watch", "https://www.youtube.com/watch?v=curto",
    f"ftp://youtube.com/watch?v={VID}", "javascript:alert(1)",
    f"https://youtube.com.evil.com/watch?v={VID}",
])
def test_rejects_invalid_links(text):
    assert extract_video_id(text) is None
