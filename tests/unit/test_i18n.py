import pytest

from app.i18n import _STRINGS, Translator


def test_languages_have_same_keys():
    assert set(_STRINGS["pt-BR"]) == set(_STRINGS["en"])


def test_switch_emits_signal(qtbot):
    tr = Translator("pt-BR")
    with qtbot.waitSignal(tr.language_changed):
        tr.set_language("en")
    assert tr.t("nav.home") == "Home"


def test_unknown_language_is_ignored():
    tr = Translator("pt-BR")
    tr.set_language("xx")
    assert tr.language == "pt-BR"
    assert tr.t("chave.inexistente") == "chave.inexistente"
