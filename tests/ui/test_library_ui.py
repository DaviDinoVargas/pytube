import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QApplication

from app.domain import states
from app.domain.models import Video
from app.infrastructure.providers.base import ProviderError
from app.ui.pages import watch_page as wp
from app.ui.widgets.video_card import CARD_W, VideoCard
from app.ui.widgets.video_grid import VideoGrid
from tests.fakes import VID

TOKENS = None


def tokens():
    from app.styles.tokens import DARK

    return DARK


def card(qtbot, translator, video, state, thumb=None, can_download=False):
    c = VideoCard(translator, tokens(), video, state, thumb, can_download)
    qtbot.addWidget(c)
    c.show()
    return c


@pytest.fixture
def tr():
    from app.i18n import Translator

    return Translator("pt-BR")


def video(**kw):
    kw.setdefault("title", "Um título")
    kw.setdefault("channel", "Canal")
    kw.setdefault("duration", 125)
    return Video(source_id="abcdefghijk", url="u", id=7, **kw)


# ---------- card ----------
def test_saved_card_is_plain_without_badge(qtbot, tr):
    c = card(qtbot, tr, video(), states.SAVED)
    assert c.state_badge is None and c.property("state") == "saved"
    assert c.duration_badge.text() == "2:05"
    assert c.width() == CARD_W


@pytest.mark.parametrize("state,text", [
    (states.DOWNLOADED, "Baixado"), (states.MISSING, "Arquivo ausente"),
    (states.INVALID, "Arquivo inválido"), (states.FAILED, "Falhou"),
])
def test_state_badge_uses_text_not_only_color(qtbot, tr, state, text):
    c = card(qtbot, tr, video(), state)
    assert c.state_badge.text_label.text() == text and c.property("state") == state
    assert text in c.accessibleName()


def test_card_without_duration_has_no_duration_badge(qtbot, tr):
    assert card(qtbot, tr, video(duration=None), states.SAVED).duration_badge is None


def test_menu_actions_depend_on_state(qtbot, tr):
    assert card(qtbot, tr, video(), states.SAVED).action_keys() == ["Abrir", "Abrir no navegador", "Remover da biblioteca"]
    assert "Mostrar arquivo na pasta" in card(qtbot, tr, video(), states.DOWNLOADED).action_keys()
    assert "Baixar vídeo" not in card(qtbot, tr, video(), states.SAVED).action_keys()  # só existe com downloads ativos
    assert "Baixar vídeo" in card(qtbot, tr, video(), states.SAVED, can_download=True).action_keys()
    assert "Baixar vídeo" not in card(qtbot, tr, video(), states.DOWNLOADED, can_download=True).action_keys()


def test_click_enter_and_menu_open_the_video(qtbot, tr):
    c = card(qtbot, tr, video(), states.SAVED)
    with qtbot.waitSignal(c.open_requested) as s:
        qtbot.mouseClick(c.thumb, Qt.LeftButton)
    assert s.args == [7]
    with qtbot.waitSignal(c.open_requested):
        qtbot.keyClick(c, Qt.Key_Return)
    with qtbot.waitSignal(c.action_requested) as s:
        c.menu_button.menu().actions()[-1].trigger()
    assert s.args == [7, "remove"]


def test_long_title_is_elided_and_full_text_is_in_tooltip(qtbot, tr):
    title = "palavra " * 80
    c = card(qtbot, tr, video(title=title), states.SAVED)
    assert c.title_label.text().endswith("…") and c.toolTip() == title


def test_card_renders_real_thumbnail(qtbot, tr, tmp_path, jpeg):
    f = tmp_path / "t.jpg"
    f.write_bytes(jpeg)
    c = card(qtbot, tr, video(), states.SAVED, f)
    assert not c.thumb.pixmap().isNull() and c.thumb.pixmap().width() == CARD_W - 4


# ---------- grade ----------
@pytest.mark.parametrize("width,cols", [(272, 1), (560, 2), (880, 3), (1500, 5)])
def test_grid_wraps_cards_by_width(qtbot, tr, width, cols):
    g = VideoGrid()
    qtbot.addWidget(g)
    g.set_cards([card(qtbot, tr, video(), states.SAVED) for _ in range(6)])
    g.resize(width, g.heightForWidth(width))
    g.show()
    assert g.columns() == cols


def test_grid_can_shrink_and_grow_height_follows(qtbot, tr):
    g = VideoGrid()
    qtbot.addWidget(g)
    g.set_cards([card(qtbot, tr, video(), states.SAVED) for _ in range(6)])
    g.show()
    assert g.minimumSizeHint().width() <= CARD_W + 4  # a janela pode ficar estreita
    assert g.layout().heightForWidth(1500) < g.layout().heightForWidth(300)
    g.resize(1200, g.layout().heightForWidth(1200))
    assert g.columns() == 4
    g.resize(580, g.layout().heightForWidth(580))
    assert g.columns() == 2 and len(g.cards) == 6


def test_main_window_can_shrink_to_minimum_with_cards(qtbot, window_factory, fake_provider):
    w = window_factory()
    for n in range(7):
        w.library.save_info(fake_provider.fetch_info(f"video{n:06d}"))
    w.show_page("library")
    w.resize(w.minimumWidth(), 700)
    QApplication.processEvents()
    assert w.width() == w.minimumWidth() == 900
    cards = w.pages["library"].cards()
    assert len(cards) == 7 and all(c.isVisible() for c in cards)


# ---------- fluxo completo ----------
def open_url(w, url):
    w.top_bar.url_input.setText(url)
    w.top_bar.open_button.click()


def wait_content(qtbot, w):
    qtbot.waitUntil(lambda: w.watch_page.stack.currentIndex() == 2, timeout=5000)


def test_open_link_save_and_see_it_in_library(qtbot, window_factory, fake_provider):
    w = window_factory()
    open_url(w, f"https://youtu.be/{VID}")
    assert w.current_page == "watch"
    wait_content(qtbot, w)
    page = w.watch_page
    assert page.title_label.text() == "Vídeo de teste"
    assert "Canal Teste" in page.meta_label.text() and "3:32" in page.meta_label.text()
    assert page.save_button.text() == "Salvar na biblioteca"
    assert w.library.list_videos() == []  # abrir NÃO salva
    with qtbot.waitSignal(page.message):
        page.save_button.click()
    qtbot.waitUntil(lambda: page.save_button.text() == "Remover da biblioteca", timeout=5000)
    assert len(w.library.list_videos()) == 1
    w.show_page("library")
    cards = w.pages["library"].cards()
    assert len(cards) == 1 and cards[0].property("state") == "saved"
    assert not w.pages["library"].empty.isVisible()


def test_opening_saved_video_does_not_hit_the_network(qtbot, window_factory, fake_provider):
    w = window_factory()
    w.library.save_info(fake_provider.fetch_info(VID))
    calls = fake_provider.fetch_calls
    open_url(w, f"https://youtu.be/{VID}")
    wait_content(qtbot, w)
    assert fake_provider.fetch_calls == calls
    assert w.watch_page.save_button.text() == "Remover da biblioteca"


def test_remove_from_watch_page_keeps_page_and_allows_saving_again(qtbot, window_factory, fake_provider):
    w = window_factory()
    saved, _ = w.library.save_info(fake_provider.fetch_info(VID))
    w.open_saved_video(saved.id)
    page = w.watch_page
    page.save_button.click()
    assert w.library.list_videos() == [] and page.save_button.text() == "Salvar na biblioteca"
    page.save_button.click()
    qtbot.waitUntil(lambda: len(w.library.list_videos()) == 1, timeout=5000)


def test_provider_error_shows_message_and_retry_recovers(qtbot, window_factory, fake_provider):
    w = window_factory()
    fake_provider.error = "private"
    open_url(w, f"https://youtu.be/{VID}")
    qtbot.waitUntil(lambda: w.watch_page.stack.currentIndex() == 1, timeout=5000)
    assert "privado" in w.watch_page.error_label.text()
    fake_provider.error = None
    w.watch_page.retry_button.click()
    wait_content(qtbot, w)


@pytest.mark.parametrize("code", ["unavailable", "age_restricted", "network", "drm", "blocked", "failed", "live", "members_only"])
def test_every_provider_error_has_a_translation(qtbot, window_factory, fake_provider, code):
    w = window_factory()
    fake_provider.error = code
    open_url(w, f"https://youtu.be/{VID}")
    qtbot.waitUntil(lambda: w.watch_page.stack.currentIndex() == 1, timeout=5000)
    assert not w.watch_page.error_label.text().startswith("error.")


def test_stale_response_is_ignored(qtbot, window_factory, fake_provider):
    w = window_factory()
    page = w.watch_page
    page.open_source_id("aaaaaaaaaaa")
    old = page._request
    page.open_source_id("bbbbbbbbbbb")
    page._on_info(old, fake_provider.fetch_info("aaaaaaaaaaa"))
    assert page._info is None  # a resposta velha não sobrescreve
    wait_content(qtbot, w)


def test_back_button_returns_to_previous_page(qtbot, window_factory, fake_provider):
    w = window_factory()
    w.show_page("library")
    open_url(w, f"https://youtu.be/{VID}")
    assert w.current_page == "watch"
    w.watch_page.back_button.click()
    assert w.current_page == "library"


def test_watch_page_is_not_remembered_as_last_page(qtbot, window_factory, settings, fake_provider):
    w = window_factory()
    w.show_page("downloaded")
    open_url(w, f"https://youtu.be/{VID}")
    assert settings.last_page == "downloaded"


# ---------- páginas ----------
def attach_file(w, video_id, tmp_path, name="a.mp4", size=2048):
    f = w.library.layout.videos / name
    f.write_bytes(b"0" * size)
    return w.library.attach_local_file(video_id, f, "720p")


def test_downloaded_page_lists_only_verified_downloads(qtbot, window_factory, fake_provider, tmp_path):
    w = window_factory()
    a, _ = w.library.save_info(fake_provider.fetch_info("aaaaaaaaaaa"))
    b, _ = w.library.save_info(fake_provider.fetch_info("bbbbbbbbbbb"))
    attach_file(w, a.id, tmp_path)
    w.show_page("downloaded")
    cards = w.pages["downloaded"].cards()
    assert [c.video.source_id for c in cards] == ["aaaaaaaaaaa"] and cards[0].property("state") == "downloaded"
    w.show_page("library")
    assert {c.video.source_id: c.property("state") for c in w.pages["library"].cards()} == {
        "aaaaaaaaaaa": "downloaded", "bbbbbbbbbbb": "saved"}


def test_deleted_file_is_shown_as_missing_not_downloaded(qtbot, window_factory, fake_provider, tmp_path):
    w = window_factory()
    a, _ = w.library.save_info(fake_provider.fetch_info("aaaaaaaaaaa"))
    attach_file(w, a.id, tmp_path)
    (w.library.layout.videos / "a.mp4").unlink()
    w.show_page("library")
    assert w.pages["library"].cards()[0].property("state") == "missing"
    w.show_page("downloaded")
    assert w.pages["downloaded"].cards() == [] and w.pages["downloaded"].empty.isVisible()


def test_home_sections_and_empty_state(qtbot, window_factory, fake_provider, tmp_path):
    w = window_factory()
    home = w.pages["home"]
    assert home.empty.isVisible()
    a, _ = w.library.save_info(fake_provider.fetch_info("aaaaaaaaaaa"))
    assert not home.empty.isVisible() and len(home.cards()) == 1  # só "recentes"
    attach_file(w, a.id, tmp_path)
    assert len(home.cards()) == 2  # recentes + baixados
    from PySide6.QtWidgets import QLabel

    titles = [l.text() for l in home.findChildren(QLabel) if l.objectName() == "sectionTitle"]
    assert titles == ["Adicionados recentemente", "Baixados"]


def test_pages_update_when_library_changes_while_hidden(qtbot, window_factory, fake_provider):
    w = window_factory()
    w.show_page("settings")
    w.library.save_info(fake_provider.fetch_info("aaaaaaaaaaa"))
    w.show_page("library")
    assert len(w.pages["library"].cards()) == 1


def test_card_menu_remove_asks_confirmation_only_for_downloads(qtbot, window_factory, fake_provider, tmp_path, monkeypatch):
    w = window_factory()
    a, _ = w.library.save_info(fake_provider.fetch_info("aaaaaaaaaaa"))
    w._on_video_action(a.id, "remove")  # salvo, sem arquivo: remove direto
    assert w.library.list_videos() == []
    b, _ = w.library.save_info(fake_provider.fetch_info("bbbbbbbbbbb"))
    attach_file(w, b.id, tmp_path, "b.mp4")
    asked = []
    monkeypatch.setattr(type(w), "_confirm_remove", lambda self: asked.append(1) or False)
    w._on_video_action(b.id, "remove")
    assert asked == [1] and len(w.library.list_videos()) == 1  # recusou: nada muda
    monkeypatch.setattr(type(w), "_confirm_remove", lambda self: True)
    w._on_video_action(b.id, "remove")
    assert w.library.list_videos() == []
    assert (w.library.layout.videos / "b.mp4").exists()  # o arquivo nunca é apagado por aqui


def test_open_in_browser_uses_only_validated_ids(qtbot, window_factory, fake_provider, monkeypatch):
    opened = []
    monkeypatch.setattr(wp.QDesktopServices, "openUrl", lambda url: opened.append(url.toString()))
    w = window_factory()
    open_url(w, f"https://youtu.be/{VID}")
    wait_content(qtbot, w)
    w.watch_page.browser_button.click()
    assert opened == [f"https://www.youtube.com/watch?v={VID}"]
    assert wp.watch_url("../../etc/passwd") is None and wp.watch_url("curto") is None and wp.watch_url(None) is None


def test_language_switch_retranslates_cards_and_sections(qtbot, window_factory, fake_provider, tmp_path):
    w = window_factory()
    a, _ = w.library.save_info(fake_provider.fetch_info("aaaaaaaaaaa"))
    attach_file(w, a.id, tmp_path)
    combo = w.settings_page.language_combo
    combo.setCurrentIndex(combo.findData("en"))
    w.show_page("home")
    assert w.pages["home"].cards()[0].state_badge.text_label.text() == "Downloaded"


def test_library_is_inert_without_storage(qtbot, window_factory):
    from app.services.storage_service import StorageManager

    w = window_factory(configure=False)
    assert not w.library.ready
    w.show_page("library")
    assert w.pages["library"].empty.isVisible()
    assert not w.watch_page.save_button.isEnabled() or w.watch_page._info is None


def test_save_url_from_topbar_while_unconfigured_is_safe(qtbot, window_factory):
    w = window_factory(configure=False)
    open_url(w, f"https://youtu.be/{VID}")
    wait_content(qtbot, w)
    assert not w.watch_page.save_button.isEnabled()  # sem pasta de biblioteca não dá para salvar


def test_player_area_keeps_16_9(qtbot, window_factory, fake_provider):
    w = window_factory()
    w.resize(1300, 800)
    w.library.save_info(fake_provider.fetch_info(VID))
    w.open_saved_video(1)
    QApplication.processEvents()
    area = w.watch_page.player
    assert abs(area.height() - min(area.width(), 1000) * 9 / 16) <= 2
    w.resize(900, 700)
    QApplication.processEvents()
    assert abs(area.height() - area.width() * 9 / 16) <= 2


def test_player_never_pushes_actions_out_of_view(qtbot, window_factory, fake_provider):
    w = window_factory()
    w.resize(1400, 760)
    w.library.save_info(fake_provider.fetch_info(VID))
    w.open_saved_video(1)
    QApplication.processEvents()
    page = w.watch_page
    assert page.player.height() <= page.height() * 0.58 + 2
    assert abs(page.player.height() - page.player.width() * 9 / 16) <= 2  # proporção preservada
