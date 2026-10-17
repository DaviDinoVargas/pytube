import json

import pytest

from app.infrastructure.media import embed
from app.infrastructure.media.embed import EmbedBridge, build_html, map_error


@pytest.mark.parametrize("code,expected", [(100, "unavailable"), (101, "embed_blocked"), (150, "embed_blocked"), (153, "embed_blocked"), (2, "failed"), (5, "failed"), (999, "failed")])
def test_error_mapping(code, expected):
    assert map_error(code) == expected


def test_html_embeds_validated_id_and_secure_parameters():
    html = build_html("dQw4w9WgXcQ", start=75)
    assert "videoId: 'dQw4w9WgXcQ'" in html and "start: 75" in html
    assert embed.IFRAME_API_URL in html and "qwebchannel.js" in html
    assert "controls: 0" in html and "origin: 'https://dinotube.local'" in html
    assert "youtube-nocookie.com" in html  # sem cookies de rastreamento


@pytest.mark.parametrize("bad", ["", "curto", "x" * 12, "abc'); alert(1);//", "../../etc/passwd", None, "dQw4w9WgXc "])
def test_html_rejects_ids_that_could_inject_script(bad):
    with pytest.raises(ValueError):
        build_html(bad)


def test_html_start_is_clamped_and_numeric():
    assert "start: 0" in build_html("dQw4w9WgXcQ", start=-30)
    assert "start: 12" in build_html("dQw4w9WgXcQ", start=12.9)


def test_html_inlines_webchannel_script_instead_of_qrc_reference():
    from app.infrastructure.media.embed import webchannel_source

    js = webchannel_source()
    assert "QWebChannel" in js
    html = build_html("dQw4w9WgXcQ", webchannel_js=js)
    assert "qrc:///" not in html and "QWebChannel" in html and "new QWebChannel(qt.webChannelTransport" in html


def test_html_accepts_inline_api_script_for_tests():
    html = build_html("dQw4w9WgXcQ", api_script="window.MOCK=1;")
    assert "window.MOCK=1;" in html and embed.IFRAME_API_URL not in html


def test_bridge_translates_messages_into_signals(qtbot):
    bridge = EmbedBridge()
    got = {}
    bridge.time_changed.connect(lambda t, d: got.update(time=(t, d)))
    bridge.quality_changed.connect(lambda q, levels: got.update(quality=(q, levels)))
    bridge.status_changed.connect(lambda v, m, r: got.update(status=(v, m, r)))
    bridge.state_changed.connect(lambda s: got.update(state=s))
    bridge.message("time", json.dumps({"t": 12.5, "d": 200, "q": "hd720", "levels": ["hd1080", "hd720", "auto"], "v": 80, "m": False, "r": 1.5, "s": 1}))
    assert got == {"time": (12.5, 200.0), "quality": ("hd720", ["hd1080", "hd720", "auto"]), "status": (80.0, False, 1.5), "state": 1}


def test_bridge_error_and_lifecycle_signals(qtbot):
    bridge = EmbedBridge()
    with qtbot.waitSignal(bridge.error) as sig:
        bridge.message("error", json.dumps({"code": 150}))
    assert sig.args == ["embed_blocked", 150]
    with qtbot.waitSignal(bridge.ready):
        bridge.message("ready", "{}")
    with qtbot.waitSignal(bridge.channel_ready):
        bridge.message("channel", "{}")
    with qtbot.waitSignal(bridge.state_changed) as sig:
        bridge.message("state", json.dumps({"state": 0}))
    assert sig.args == [0]


def test_bridge_ignores_garbage(qtbot):
    bridge = EmbedBridge()
    bridge.message("time", "isto não é json")
    bridge.message("desconhecida", "{}")
    bridge.message("time", "{}")  # sem campos: valores padrão, sem exceção
