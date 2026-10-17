import pytest
from PySide6.QtWidgets import QApplication, QLabel, QMessageBox

from app.infrastructure.media.ffmpeg import FFmpegTools, MediaError
from app.infrastructure.providers.base import StreamOption
from app.infrastructure.providers.chain import ProviderChain
from app.services import download_service as ds
from app.services.storage_service import StorageManager
from app.services.thumbnail_service import ThumbnailService
from app.bootstrap import create_window
from tests.fakes import VID, MediaProvider, make_stub_player
from tests.media import FFMPEG, FFPROBE, HAS_FFMPEG, make_media

pytestmark = pytest.mark.skipif(not HAS_FFMPEG, reason="ffmpeg não instalado")

DIRECT = StreamOption("progressive", "18", "mp4", 360, 30, 96, 4_000_000, "avc1.42001E", "mp4a.40.2")
H264 = StreamOption("video", "137", "mp4", 1080, 30, 4000, 90_000_000, "avc1.640028")
AAC = StreamOption("audio", "140", "m4a", None, None, 128, 3_000_000, "", "mp4a.40.2")
VP9 = StreamOption("video", "248", "webm", 720, 30, 2000, 40_000_000, "vp9")
STREAMS = [DIRECT, H264, AAC, VP9]


@pytest.fixture(scope="module")
def media(tmp_path_factory):
    return make_media(tmp_path_factory.mktemp("media_ui"))


@pytest.fixture
def ctx(qtbot, settings, tmp_path, media):
    settings.download_consent = True
    files = {"18": media["progressive_mp4"], "137": media["video_h264"], "140": media["audio_aac"], "248": media["video_vp9"]}
    provider = MediaProvider(files, STREAMS)
    state = {"tools": lambda: FFmpegTools(FFMPEG, FFPROBE).check(), "windows": []}

    def make(configure=True):
        storage = StorageManager(settings, tmp_path / "appdata")
        if configure and storage.status() != "ready":
            storage.configure(tmp_path / "lib", "folder", "sqlite")
        w = create_window(
            QApplication.instance(), settings, storage, ProviderChain([provider]),
            ThumbnailService(lambda u: b""), lambda: state["tools"](),
            player_options={"local_factory": make_stub_player, "online_factory": make_stub_player},
        )
        qtbot.addWidget(w)
        w.show()
        state["windows"].append(w)
        return w

    yield make, provider, state
    for w in state["windows"]:
        w.downloads.shutdown(3)


def open_link(qtbot, w):
    w.top_bar.url_input.setText(f"https://youtu.be/{VID}")
    w.top_bar.open_button.click()
    qtbot.waitUntil(lambda: w.watch_page.stack.currentIndex() == 2, timeout=10000)
    qtbot.waitUntil(lambda: w.watch_page.quality_combo.currentData() is not None, timeout=10000)


def finished(qtbot, w, timeout=30000):
    qtbot.waitUntil(lambda: bool(w.downloads.tasks()) and all(t.finished for t in w.downloads.tasks()), timeout=timeout)
    return w.downloads.tasks()[-1]


def test_quality_picker_lists_real_options_with_size(qtbot, ctx):
    make, provider, _ = ctx
    w = make()
    open_link(qtbot, w)
    combo = w.watch_page.quality_combo
    assert [combo.itemData(i) for i in range(combo.count())] == [1080, 720, 360]
    assert combo.itemText(0).startswith("1080p") and "MB" in combo.itemText(0)
    assert combo.currentData() == 1080
    w.watch_page.set_player_height(720)
    assert combo.currentData() == 720  # acompanha a qualidade do player
    combo.setCurrentIndex(combo.findData(360))
    combo.activated.emit(combo.currentIndex())  # o usuário escolheu 360p
    w.watch_page.set_player_height(1080)
    assert combo.currentData() == 360  # a escolha explícita do usuário vence o player


def test_default_quality_follows_player_height_when_nothing_chosen(qtbot, ctx):
    make, provider, _ = ctx
    w = make()
    w.watch_page.set_player_height(400)
    open_link(qtbot, w)
    assert w.watch_page.quality_combo.currentData() == 360


def test_download_from_link_saves_downloads_and_shows_everywhere(qtbot, ctx):
    make, provider, _ = ctx
    w = make()
    open_link(qtbot, w)
    page = w.watch_page
    page.quality_combo.setCurrentIndex(page.quality_combo.findData(360))
    assert page.download_button.text() == "Baixar" and w.library.list_videos() == []
    page.download_button.click()
    task = finished(qtbot, w)
    assert task.status == ds.COMPLETED, task.error_detail
    video = w.library.list_videos()[0]
    assert video.local_status == "ok" and video.local_quality == "360p"
    qtbot.waitUntil(lambda: page.download_button.text() == "Baixar novamente", timeout=5000)
    assert "360p" in page.local_label.text()
    w.show_page("downloaded")
    assert [c.property("state") for c in w.pages["downloaded"].cards()] == ["downloaded"]
    w.show_page("library")
    assert w.pages["library"].cards()[0].state_badge.text_label.text() == "Baixado"


def test_consent_is_asked_once_and_decline_blocks_download(qtbot, ctx, settings, monkeypatch):
    make, provider, _ = ctx
    settings.download_consent = False
    w = make()
    open_link(qtbot, w)
    monkeypatch.setattr(QMessageBox, "exec", lambda self: 0)
    monkeypatch.setattr(QMessageBox, "clickedButton", lambda self: self.buttons()[1])  # Cancelar
    w.watch_page.download_button.click()
    assert w.downloads.tasks() == [] and settings.download_consent is False and w.library.list_videos() == []
    monkeypatch.setattr(QMessageBox, "clickedButton", lambda self: self.buttons()[0])  # Concordo
    w.watch_page.quality_combo.setCurrentIndex(w.watch_page.quality_combo.findData(360))
    w.watch_page.download_button.click()
    assert settings.download_consent is True
    assert finished(qtbot, w).status == ds.COMPLETED
    page = w.watch_page
    qtbot.waitUntil(lambda: page.download_button.isEnabled() and page.download_button.text() == "Baixar novamente", timeout=5000)
    asked = []
    monkeypatch.setattr(QMessageBox, "exec", lambda self: asked.append(1) or 0)
    w.watch_page.download_button.click()  # já baixado: pergunta só se quer baixar de novo
    assert len(asked) == 1  # (a confirmação de substituição), não o consentimento de novo


def test_progress_and_cancel_from_watch_page(qtbot, ctx):
    make, provider, _ = ctx
    provider.delay = 0.25
    w = make()
    open_link(qtbot, w)
    page = w.watch_page
    page.download_button.click()
    qtbot.waitUntil(lambda: page.progress_bar.isVisible() and "Baixando" in page.progress_label.text(), timeout=15000)
    assert not page.download_button.isEnabled() and not page.quality_combo.isEnabled()
    assert w.sidebar.badge("downloads") == 1
    w.show_page("library")
    assert w.pages["library"].cards()[0].property("state") == "downloading"
    w.open_saved_video(w.library.list_videos()[0].id)
    page.cancel_button.click()
    qtbot.waitUntil(lambda: w.downloads.tasks()[-1].status == ds.CANCELLED, timeout=15000)
    qtbot.waitUntil(lambda: page.download_button.isEnabled(), timeout=5000)
    assert not page.progress_bar.isVisible() and w.sidebar.badge("downloads") == 0


def test_failure_shows_message_in_queue_and_retry_works(qtbot, ctx):
    make, provider, _ = ctx
    provider.fail_times, provider.fail_code = 1, "network"
    w = make()
    open_link(qtbot, w)
    messages = []
    w.watch_page.message.connect(lambda text, err: messages.append((text, err)))
    w.watch_page.quality_combo.setCurrentIndex(w.watch_page.quality_combo.findData(360))
    w.watch_page.download_button.click()
    task = finished(qtbot, w)
    assert task.status == ds.FAILED
    qtbot.waitUntil(lambda: any(err and "conectar" in text for text, err in messages), timeout=5000)
    w.show_page("library")
    assert w.pages["library"].cards()[0].property("state") == "failed"
    w.show_page("downloads")
    row = w.pages["downloads"]._rows[task.id]
    assert "Falhou" in row.status.text() and "conectar" in row.status.text()
    qtbot.waitUntil(row.buttons["retry"].isVisible, timeout=5000)  # widgets novos aparecem no próximo ciclo de eventos
    assert not row.buttons["cancel"].isVisible()
    row.buttons["retry"].click()
    assert finished(qtbot, w).status == ds.COMPLETED
    qtbot.waitUntil(lambda: all(t.status == ds.COMPLETED for t in w.downloads.tasks()), timeout=15000)


def test_downloads_page_lists_orders_and_clears(qtbot, ctx):
    make, provider, _ = ctx
    w = make()
    page = w.pages["downloads"]
    w.show_page("downloads")
    assert page.empty.isVisible() and not page.clear_button.isVisible()
    a, _ = w.library.save_info(provider.fetch_info("aaaaaaaaaaa"))
    b, _ = w.library.save_info(provider.fetch_info("bbbbbbbbbbb"))
    ta, tb = w.downloads.enqueue(a.id, 360), w.downloads.enqueue(b.id, 360)
    qtbot.waitUntil(lambda: ta.finished and tb.finished, timeout=30000)
    qtbot.waitUntil(lambda: page.clear_button.isVisible(), timeout=5000)
    assert not page.empty.isVisible() and len(page._rows) == 2
    order = [page.list_layout.itemAt(i).widget().task.id for i in range(page.list_layout.count())]
    assert order == [tb.id, ta.id]  # finalizadas: a mais recente primeiro
    page._rows[ta.id].buttons["remove"].click()
    assert len(page._rows) == 1
    page.clear_button.click()
    assert page.empty.isVisible()


def test_open_button_on_finished_row_goes_to_video(qtbot, ctx):
    make, provider, _ = ctx
    w = make()
    v, _ = w.library.save_info(provider.fetch_info(VID))
    task = w.downloads.enqueue(v.id, 360)
    qtbot.waitUntil(lambda: task.finished, timeout=30000)
    w.show_page("downloads")
    qtbot.waitUntil(lambda: task.id in w.pages["downloads"]._rows, timeout=5000)
    w.pages["downloads"]._rows[task.id].buttons["open"].click()
    assert w.current_page == "watch"


def test_card_menu_download_opens_the_quality_picker(qtbot, ctx):
    make, provider, _ = ctx
    w = make()
    v, _ = w.library.save_info(provider.fetch_info(VID))
    w.show_page("library")
    card = w.pages["library"].cards()[0]
    assert "Baixar vídeo" in card.action_keys()
    next(a for a in card.menu_button.menu().actions() if a.text() == "Baixar vídeo").trigger()
    assert w.current_page == "watch"
    qtbot.waitUntil(lambda: w.watch_page.quality_combo.currentData() is not None, timeout=10000)


def test_missing_ffmpeg_reports_clear_error(qtbot, ctx):
    make, provider, state = ctx

    def broken():
        raise MediaError("ffmpeg_missing", "x")

    state["tools"] = broken
    w = make()
    open_link(qtbot, w)
    messages = []
    w.watch_page.message.connect(lambda text, err: messages.append(text))
    w.watch_page.download_button.click()
    task = finished(qtbot, w)
    assert task.error_code == "ffmpeg_missing"
    qtbot.waitUntil(lambda: any("ffmpeg" in m for m in messages), timeout=5000)


def test_stream_listing_failure_shows_retry(qtbot, ctx):
    make, provider, _ = ctx
    w = make()
    v, _ = w.library.save_info(provider.fetch_info(VID))
    provider.error = "network"
    w.open_saved_video(v.id)
    page = w.watch_page
    qtbot.waitUntil(lambda: page.quality_retry.isVisible(), timeout=10000)
    assert "indisponíveis" in page.quality_combo.currentText() and not page.download_button.isEnabled()
    provider.error = None
    page.quality_retry.click()
    qtbot.waitUntil(lambda: page.quality_combo.currentData() is not None, timeout=10000)
    assert page.download_button.isEnabled() and not page.quality_retry.isVisible()


def test_closing_window_cancels_running_downloads(qtbot, ctx):
    make, provider, _ = ctx
    provider.delay = 0.3
    w = make()
    v, _ = w.library.save_info(provider.fetch_info(VID))
    task = w.downloads.enqueue(v.id, 1080)
    qtbot.waitUntil(lambda: task.status == ds.DOWNLOADING, timeout=15000)
    w.close()
    assert task.status == ds.CANCELLED
    assert not any(w.library.layout.tmp.iterdir())


def test_download_is_disabled_without_library_folder(qtbot, ctx):
    make, provider, _ = ctx
    w = make(configure=False)
    open_link(qtbot, w)
    assert not w.watch_page.download_button.isEnabled()


def test_queue_texts_follow_language(qtbot, ctx):
    make, provider, _ = ctx
    w = make()
    v, _ = w.library.save_info(provider.fetch_info(VID))
    task = w.downloads.enqueue(v.id, 360)
    qtbot.waitUntil(lambda: task.finished, timeout=30000)
    combo = w.settings_page.language_combo
    combo.setCurrentIndex(combo.findData("en"))
    w.show_page("downloads")
    qtbot.waitUntil(lambda: task.id in w.pages["downloads"]._rows, timeout=5000)
    assert w.pages["downloads"]._rows[task.id].status.text() == "Finished · 360p"
    assert w.pages["downloads"].clear_button.text() == "Clear finished"
