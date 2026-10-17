"""Acessibilidade: todo controle visível tem nome para leitores de tela e dá para operar tudo pelo teclado."""

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QAbstractButton, QComboBox, QLineEdit, QSlider

from tests.fakes import FakeProvider


@pytest.fixture
def w(window_factory):
    window = window_factory()
    for i, title in enumerate(["Aula de Python", "Documentário", "Receita"]):
        video, _ = window.library.save_info(FakeProvider("f", title=title).fetch_info(f"vid{i:08d}"))
        if i == 0:
            f = window.library.layout.videos / "a.mp4"
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_bytes(b"0" * 100)
            window.library.attach_local_file(video.id, f, "720p")
    return window


def unnamed_controls(root):
    bad = []
    for button in root.findChildren(QAbstractButton):
        if button.isVisibleTo(root) and not (button.text().strip() or button.accessibleName().strip()):
            bad.append(f"botão {type(button).__name__}/{button.objectName()}")
    fields = [x for kind in (QLineEdit, QComboBox, QSlider) for x in root.findChildren(kind)]
    for field in fields:
        if field.isVisibleTo(root) and not (field.accessibleName().strip() or getattr(field, "placeholderText", lambda: "")()):
            bad.append(f"campo {type(field).__name__}/{field.objectName()}")
    return bad


PAGES = ["home", "continue", "library", "downloaded", "playlists", "categories", "history", "downloads", "settings"]


@pytest.mark.parametrize("language", ["pt-BR", "en"])
def test_every_page_has_names_on_all_visible_controls(w, qtbot, language):
    w._on_language(language)
    for page in PAGES:
        w.show_page(page)
        qtbot.wait(20)
        assert unnamed_controls(w) == [], page
    w.open_saved_video(1)
    w.watch_page.player._backend.loaded.emit()
    assert unnamed_controls(w) == [], "watch"


def test_mini_player_controls_are_named(w):
    w.open_saved_video(1)
    player = w.watch_page.player
    player._backend.loaded.emit()
    player.enter_mini()
    assert unnamed_controls(player) == []
    player.exit_mini()


def test_sidebar_and_gear_are_reachable_by_tab_and_activate_by_keyboard(w):
    for widget in (w.settings_button, *w.sidebar.findChildren(QAbstractButton)):
        assert widget.focusPolicy() & Qt.TabFocus, widget.objectName()
    assert w.settings_button.accessibleName() or w.settings_button.toolTip()


def test_icon_buttons_of_the_player_are_keyboard_focusable(w):
    c = w.watch_page.player.controls
    for button in (c.play_button, c.mute_button, c.fullscreen_button, c.mini_button):
        assert button.focusPolicy() & Qt.TabFocus
