import json
from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox

from app.domain.models import Progress, now_iso
from app.infrastructure.media.ffmpeg import FFmpegTools, MediaError
from app.services.provider_service import UpdateResult
from app.ui import main_window as mw
from app.ui.dialogs.backup_dialog import BackupDialog
from app.ui.dialogs.space_dialog import SpaceDialog
from tests.fakes import FakeProvider
from tests.media import FFMPEG, FFPROBE, HAS_FFMPEG, make_media


@pytest.fixture
def w(window_factory):
    return window_factory()


def add(w, i, title="V", size=None, name=None):
    video, _ = w.library.save_info(FakeProvider("f", title=f"{title}{i}").fetch_info(f"vid{i:08d}"))
    if size is not None:
        f = w.library.layout.videos / (name or f"{i}.mp4")
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_bytes(b"0" * size)
        video = w.library.attach_local_file(video.id, f, "720p")
    return video


def accept_confirms(monkeypatch, answer=True):
    monkeypatch.setattr(QMessageBox, "exec", lambda self: 0)
    monkeypatch.setattr(QMessageBox, "clickedButton", lambda self: self.buttons()[0 if answer else 1])


# ======================= seções de configurações =======================
def test_settings_page_shows_all_sections_with_current_values(w, settings):
    settings.player_volume = 35
    page = w.settings_page
    assert len(page._sections) == 4
    titles = [c.title_label.text() for c in page._sections]
    assert titles == ["REPRODUÇÃO", "DOWNLOADS", "PROVEDORES DE VÍDEO", "MANUTENÇÃO"]


def test_playback_preferences_are_persisted(w, settings):
    c = w.playback_card
    c.volume_slider.setValue(42)
    assert settings.player_volume == 42 and c.volume_value.text() == "42%"
    c.rate_combo.setCurrentIndex(c.rate_combo.findData(1.5))
    c.rate_combo.activated.emit(c.rate_combo.currentIndex())
    assert settings.default_rate == 1.5
    c.resume_check.setChecked(False)
    c.autoplay_check.setChecked(False)
    assert settings.resume_enabled is False and settings.autoplay_next is False
    w.settings_page.restore_check.setChecked(False)
    assert settings.restore_last_page is False


def test_resume_off_starts_from_the_beginning_without_notice(w, settings):
    v = add(w, 1)
    w.progress.save(v.id, 60, 200)
    settings.resume_enabled = False
    w.open_saved_video(v.id)
    stub = w.watch_page.player._backend
    assert stub.calls[0] == ("load", v.source_id, 0.0) and not w.watch_page.player.notice.isVisible()
    w.show_page("library")  # sair do player grava a posição do stub (0); volta a 60 antes de reabrir
    w.progress.save(v.id, 60, 200)
    settings.resume_enabled = True
    w.open_saved_video(v.id)
    loads = [c for c in w.watch_page.player._backend.calls if c[0] == "load"]
    assert loads[-1] == ("load", v.source_id, 60.0)


def test_default_speed_is_applied_when_media_loads(w, settings):
    settings.default_rate = 1.5
    v = add(w, 1)
    w.open_saved_video(v.id)
    stub = w.watch_page.player._backend
    stub.loaded.emit()
    assert ("rate", 1.5) in stub.calls
    settings.default_rate = 1.0
    w.show_page("library")
    w.open_saved_video(v.id)
    stub = w.watch_page.player._backend
    before = len(stub.calls)
    stub.loaded.emit()
    assert not any(c[0] == "rate" for c in stub.calls[before:])


def test_autoplay_next_can_be_turned_off(w, settings):
    a, b = add(w, 1), add(w, 2)
    pl = w.org.create_playlist("Fila")
    w.org.add_to_playlist(pl.id, [a.id, b.id])
    settings.autoplay_next = False
    w.play_playlist(pl.id)
    w.watch_page.player._backend.ended.emit()
    assert w.watch_page.player.video.id == a.id  # não avançou
    settings.autoplay_next = True
    w.watch_page.player._backend.ended.emit()
    assert w.watch_page.player.video.id == b.id


def test_restore_last_page_setting(window_factory, settings):
    first = window_factory()
    first.show_page("library")
    assert settings.last_page == "library"
    assert window_factory().current_page == "library"
    settings.restore_last_page = False
    assert window_factory().current_page == "home"


# ======================= downloads e ffmpeg =======================
def test_concurrency_setting_reaches_the_download_manager(w, settings):
    c = w.downloads_card
    c.concurrent_combo.setCurrentIndex(c.concurrent_combo.findData(4))
    c.concurrent_combo.activated.emit(c.concurrent_combo.currentIndex())
    assert settings.download_concurrent == 4 and w.downloads._max == 4


@pytest.mark.skipif(not HAS_FFMPEG, reason="ffmpeg não instalado")
def test_ffmpeg_status_shows_version_or_clear_error(w, qtbot):
    w._tools_getter = lambda: FFmpegTools(FFMPEG, FFPROBE).check()
    w._tools = None
    w.refresh_ffmpeg_status()
    qtbot.waitUntil(lambda: "ffmpeg" in w.downloads_card.ffmpeg_label.text() and "versão" not in w.downloads_card.ffmpeg_label.text().lower(), timeout=10000)
    assert w.downloads_card.ffmpeg_label.objectName() == "statusOk"

    def broken():
        raise MediaError("ffmpeg_missing", "x")

    w._tools_getter, w._tools = broken, None
    w.refresh_ffmpeg_status()
    qtbot.waitUntil(lambda: "não foi encontrado" in w.downloads_card.ffmpeg_label.text(), timeout=10000)
    assert w.downloads_card.ffmpeg_label.objectName() == "statusError"


def test_choosing_ffmpeg_folder_saves_path_and_resets_cached_tools(w, settings, monkeypatch, tmp_path):
    w._tools = object()
    monkeypatch.setattr(QFileDialog, "getExistingDirectory", lambda *a, **k: str(tmp_path))
    w.downloads_card.ffmpeg_browse_requested.emit()
    assert settings.ffmpeg_path == str(tmp_path) and w._tools is None
    w.downloads_card.ffmpeg_path_changed.emit("")
    assert settings.ffmpeg_path == ""
    monkeypatch.setattr(QFileDialog, "getExistingDirectory", lambda *a, **k: "")
    w.downloads_card.ffmpeg_browse_requested.emit()  # cancelou: nada muda
    assert settings.ffmpeg_path == ""


# ======================= provedores =======================
def test_provider_order_is_applied_and_remembered(w, settings):
    chain = w.providers
    c = w.providers_card
    c.order_combo.setCurrentIndex(1)
    c.order_combo.activated.emit(1)
    assert settings.provider_order == ("ytdlp", "pytubefix") and chain.order[0] == "fake"  # só os conhecidos entram
    c.order_combo.setCurrentIndex(0)
    c.order_combo.activated.emit(0)
    assert settings.provider_order == ("pytubefix", "ytdlp")


@pytest.mark.parametrize("result,expected", [
    (UpdateResult(True, "", "ok"), "Reinicie o DinoTube"),
    (UpdateResult(False, "frozen"), "Indisponível neste executável"),
    (UpdateResult(False, "timeout"), "demorou demais"),
    (UpdateResult(False, "failed", "x"), "A atualização falhou"),
    (None, "A atualização falhou"),
])
def test_provider_update_results_are_explained(w, qtbot, monkeypatch, result, expected):
    def fake():
        if result is None:
            raise RuntimeError("falha inesperada")
        return result

    monkeypatch.setattr(mw, "update_providers", fake)
    w.providers_card.update_requested.emit()
    assert not w.providers_card.update_button.isEnabled() and "Atualizando" in w.providers_card.result_label.text()
    qtbot.waitUntil(lambda: w.providers_card.update_button.isEnabled(), timeout=10000)
    assert expected in w.providers_card.result_label.text()


def test_provider_versions_are_listed(w):
    text = w.providers_card.versions_label.text()
    assert "pytubefix" in text and "yt-dlp" in text


# ======================= manutenção =======================
def test_maintenance_actions_need_a_library(window_factory):
    w = window_factory(configure=False)
    w.maintenance_card.buttons["verify"].click()
    assert "Configure primeiro" in w.maintenance_card.status_label.text()
    w.maintenance_card.buttons["manage_space"].click()  # não abre diálogo
    assert "Configure primeiro" in w.maintenance_card.status_label.text()


def test_verify_files_reports_counts(w, qtbot):
    a = add(w, 1, size=100)
    add(w, 2)
    (w.library.layout.videos / "1.mp4").unlink()
    w.maintenance_card.buttons["verify"].click()
    qtbot.waitUntil(lambda: "Verificação concluída" in w.maintenance_card.status_label.text(), timeout=10000)
    assert "0 baixados e 1 com problema" in w.maintenance_card.status_label.text()


def test_refresh_metadata_updates_titles_and_reports(w, qtbot, fake_provider):
    add(w, 1)
    fake_provider.title = "Título atualizado"
    w.maintenance_card.buttons["refresh"].click()
    qtbot.waitUntil(lambda: "atualizados" in w.maintenance_card.status_label.text(), timeout=10000)
    assert "1 atualizados e 0 com falha" in w.maintenance_card.status_label.text()
    assert w.library.list_videos()[0].title == "Título atualizado"
    fake_provider.error = "private"
    w.maintenance_card.buttons["refresh"].click()
    qtbot.waitUntil(lambda: "1 com falha" in w.maintenance_card.status_label.text() or "1 falharam" in w.maintenance_card.status_label.text(), timeout=10000)
    assert w.maintenance_card.status_label.objectName() == "statusError"


def test_clear_thumbnails(w):
    add(w, 1)
    assert any(w.library.layout.thumbnails.iterdir())
    w.maintenance_card.buttons["clear_thumbs"].click()
    assert "miniaturas apagadas" in w.maintenance_card.status_label.text() and not any(w.library.layout.thumbnails.iterdir())


def test_export_diagnostics_writes_report_without_secrets(w, monkeypatch, tmp_path):
    add(w, 1)
    target = tmp_path / "diag.txt"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a, **k: (str(target), ""))
    w.maintenance_card.buttons["diagnostics"].click()
    text = target.read_text(encoding="utf-8")
    assert "DinoTube" in text and "vídeos: 1" in text and "Provedores" in text
    assert str(Path.home()) not in text
    assert "diag.txt" in w.maintenance_card.status_label.text()
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a, **k: ("", ""))
    w.maintenance_card.buttons["diagnostics"].click()  # cancelou: sem erro


def test_open_logs_folder(w, monkeypatch):
    opened = []
    monkeypatch.setattr(mw.QDesktopServices, "openUrl", lambda url: opened.append(url.toLocalFile()))
    w.maintenance_card.buttons["logs"].click()
    assert opened == [str(w.library.layout.logs)]


def test_logging_goes_to_library_logs_folder_without_secrets(w):
    import logging

    w._after_storage_ready()
    logging.getLogger("dinotube.teste").info("link https://a.googlevideo.com/v?sig=SEGREDO ok")
    for h in logging.getLogger("dinotube").handlers:
        h.flush()
    content = (w.library.layout.logs / "dinotube.log").read_text(encoding="utf-8")
    assert "Biblioteca em uso" in content and "SEGREDO" not in content


def test_background_checks_make_one_automatic_backup_per_day(w, qtbot):
    add(w, 1)
    w.start_background_checks()
    qtbot.waitUntil(lambda: any(i.kind == "auto" for i in w.backups.list()), timeout=10000)
    assert len([i for i in w.backups.list() if i.kind == "auto"]) == 1
    w.start_background_checks()
    qtbot.wait(500)
    assert len([i for i in w.backups.list() if i.kind == "auto"]) == 1  # ainda não venceu o prazo de 24 h


# ======================= diálogo de espaço e arquivos =======================
def make_space(w, tools=None):
    return SpaceDialog(w._tr, w.maintenance, w.library, tools or (lambda: None), w.open_saved_video, w)


def select_rows(table, *rows):
    from PySide6.QtCore import QItemSelectionModel

    table.clearSelection()
    flags = QItemSelectionModel.Select | QItemSelectionModel.Rows
    for r in rows:
        table.selectionModel().select(table.model().index(r, 0), flags)


def test_space_dialog_lists_largest_first_and_frees_selected(w, qtbot, monkeypatch):
    a, b, c = add(w, 1, size=500), add(w, 2, size=3000), add(w, 3, size=100)
    d = make_space(w)
    qtbot.addWidget(d)
    t = d.large_table
    assert [t.item(r, 2).data(Qt.UserRole) for r in range(t.rowCount())] == [3000, 500, 100]
    assert "3 arquivos ocupam" in d.summary.text() and not d.free_button.isEnabled()
    select_rows(t, 0, 1)
    assert d.free_button.isEnabled() and "Libera" in d.free_label.text()
    accept_confirms(monkeypatch, False)
    d.free_selected()
    assert len(w.maintenance.largest()) == 3  # recusou
    accept_confirms(monkeypatch, True)
    d.free_selected()
    assert [e.size for e in w.maintenance.largest()] == [100] and t.rowCount() == 1
    assert "liberados" in d.status.text() and len(w.library.list_videos()) == 3  # os registros ficam


def test_space_dialog_missing_files_tab_forget_and_redownload(w, qtbot):
    a = add(w, 1, size=100)
    (w.library.layout.videos / "1.mp4").unlink()
    d = make_space(w)
    qtbot.addWidget(d)
    d.verify()
    assert d.missing_table.rowCount() == 1 and d.missing_table.item(0, 1).text() == "Arquivo ausente"
    assert not d.locate_button.isEnabled()
    select_rows(d.missing_table, 0)
    assert d.locate_button.isEnabled() and d.forget_button.isEnabled()
    d.forget_selected()
    assert d.missing_table.rowCount() == 0 and w.library.get(a.id).local_status == "none"
    (w.library.layout.videos / "2.mp4").write_bytes(b"0")
    b = add(w, 2, size=10)
    (w.library.layout.videos / "2.mp4").unlink()
    d.verify()
    select_rows(d.missing_table, 0)
    d.redownload_selected()
    assert w.current_page == "watch" and w.watch_page.player.video.id == b.id


@pytest.mark.skipif(not HAS_FFMPEG, reason="ffmpeg não instalado")
def test_space_dialog_locate_validates_the_file(w, qtbot, monkeypatch, tmp_path):
    media = make_media(tmp_path / "m")
    tools = FFmpegTools(FFMPEG, FFPROBE).check()
    a = add(w, 1, size=100)
    (w.library.layout.videos / "1.mp4").unlink()
    d = make_space(w, lambda: tools)
    qtbot.addWidget(d)
    d.verify()
    select_rows(d.missing_table, 0)
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *a, **k: (str(media["garbage"]), ""))
    d.locate_selected()
    assert "não passou" in d.status.text() or "descartado" in d.status.text() or d.status.objectName() == "statusError"
    assert w.library.get(a.id).local_status == "missing"
    good = tmp_path / "bom.mp4"
    good.write_bytes(media["progressive_mp4"].read_bytes())
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *a, **k: (str(good), ""))
    d.locate_selected()
    assert w.library.get(a.id).local_status == "ok" and d.missing_table.rowCount() == 0 and "localizado" in d.status.text()
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *a, **k: ("", ""))
    d.locate_selected()  # cancelar não faz nada


def test_space_dialog_orphans_tab(w, qtbot, monkeypatch, tmp_path):
    add(w, 1, size=100)
    loose = w.library.layout.videos / "pasta" / "solto.mkv"
    loose.parent.mkdir()
    loose.write_bytes(b"0" * 800)
    d = make_space(w)
    qtbot.addWidget(d)
    assert d.orphan_table.rowCount() == 1 and d.orphan_table.item(0, 0).text().endswith("solto.mkv")
    select_rows(d.orphan_table, 0)
    accept_confirms(monkeypatch, True)
    d.delete_orphans()
    assert not loose.exists() and d.orphan_table.rowCount() == 0 and (w.library.layout.videos / "1.mp4").exists()


def test_manage_space_button_opens_the_dialog(w, monkeypatch):
    opened = []
    monkeypatch.setattr(SpaceDialog, "exec", lambda self: opened.append(self) or 0)
    w.maintenance_card.buttons["manage_space"].click()
    assert len(opened) == 1


# ======================= diálogo de backups =======================
def make_backup(w):
    return BackupDialog(w._tr, w.backups, w)


def test_backup_dialog_create_and_restore(w, qtbot, monkeypatch):
    add(w, 1, "Antes")
    d = make_backup(w)
    qtbot.addWidget(d)
    assert d.list.count() == 0 and not d.restore_button.isEnabled()
    d.create_button.click()
    assert d.list.count() == 1 and "Backup criado" in d.status.text() and "Manual" in d.list.item(0).text()
    add(w, 2, "Depois")
    assert len(w.library.list_videos()) == 2
    d.list.setCurrentRow(0)
    assert d.restore_button.isEnabled()
    accept_confirms(monkeypatch, False)
    d.restore_button.click()
    assert len(w.library.list_videos()) == 2  # recusou
    accept_confirms(monkeypatch, True)
    d.restore_button.click()
    assert [v.title for v in w.library.list_videos()] == ["Antes1"] and "restaurada" in d.status.text()
    assert any(i.kind == "pre-restore" for i in w.backups.list())  # o estado anterior ficou guardado


def test_backup_dialog_rejects_invalid_import_without_changes(w, qtbot, monkeypatch, tmp_path):
    add(w, 1)
    d = make_backup(w)
    qtbot.addWidget(d)
    bad = tmp_path / "ruim.json"
    bad.write_text(json.dumps({"format": "outra-coisa"}))
    accept_confirms(monkeypatch, True)
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *a, **k: (str(bad), ""))
    before = w.library.store.export_data()
    d.import_button.click()
    assert "não é um backup válido" in d.status.text() and d.status.objectName() == "statusError"
    assert w.library.store.export_data() == before


def test_backup_dialog_export_import_and_csv(w, qtbot, monkeypatch, tmp_path):
    add(w, 1, "Um")
    d = make_backup(w)
    qtbot.addWidget(d)
    target = tmp_path / "exportado.json"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a, **k: (str(target), ""))
    d.export_button.click()
    assert target.exists() and "exportado.json" in d.status.text()
    csv_path = tmp_path / "lista.csv"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a, **k: (str(csv_path), ""))
    d.csv_button.click()
    assert "Um1" in csv_path.read_text(encoding="utf-8-sig")
    add(w, 2, "Dois")
    accept_confirms(monkeypatch, True)
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *a, **k: (str(target), ""))
    d.import_button.click()
    assert [v.title for v in w.library.list_videos()] == ["Um1"]
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a, **k: ("", ""))
    d.export_button.click()  # cancelou: sem erro


def test_backups_button_opens_dialog(w, monkeypatch):
    opened = []
    monkeypatch.setattr(BackupDialog, "exec", lambda self: opened.append(self) or 0)
    w.maintenance_card.buttons["backups"].click()
    assert len(opened) == 1


# ======================= idioma =======================
def test_new_sections_follow_language(w):
    combo = w.settings_page.language_combo
    combo.setCurrentIndex(combo.findData("en"))
    assert [c.title_label.text() for c in w.settings_page._sections] == ["PLAYBACK", "DOWNLOADS", "VIDEO PROVIDERS", "MAINTENANCE"]
    assert w.maintenance_card.buttons["backups"].text() == "Backups and export…"
    assert w.playback_card.resume_check.text() == "Resume where you left off"
    assert w.settings_page.restore_check.text() == "Open the last page used"
    d = BackupDialog(w._tr, w.backups, w)
    assert d.create_button.text() == "Create backup now"
