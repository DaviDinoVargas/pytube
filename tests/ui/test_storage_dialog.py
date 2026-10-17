import sys
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication, QDialog

from app.bootstrap import create_window
from app.domain.models import Video
from app.i18n import Translator
from app.services.storage_service import STATUS_READY, SUBFOLDERS, StorageManager
from app.ui.dialogs.storage_dialog import StorageDialog


@pytest.fixture
def manager(settings, tmp_path):
    return StorageManager(settings, tmp_path / "appdata")


def dialog(qtbot, manager, first_run=True):
    d = StorageDialog(Translator("pt-BR"), manager, first_run=first_run)
    qtbot.addWidget(d)
    d.show()
    return d


def test_first_run_prefills_suggestion_and_defaults_to_folder_mode(qtbot, manager):
    d = dialog(qtbot, manager)
    assert d.path_input.text() != ""
    assert d.mode == "folder"
    assert d.format_row.isVisible()
    assert d.cancel_button.text() == "Sair"
    assert not d.migrate_check.isVisible()


def test_saving_creates_folders_and_persists_choice(qtbot, manager, tmp_path):
    d = dialog(qtbot, manager)
    d.path_input.setText(str(tmp_path / "DinoTube"))
    d.format_combo.setCurrentIndex(d.format_combo.findData("json"))
    d.save_button.click()
    assert d.result() == QDialog.Accepted
    for name in SUBFOLDERS:
        assert (tmp_path / "DinoTube" / name).is_dir()
    assert manager.status() == STATUS_READY
    assert manager.config.format == "json"


def test_database_mode_hides_format_choice(qtbot, manager, tmp_path):
    d = dialog(qtbot, manager)
    d.mode_buttons["database"].setChecked(True)
    assert not d.format_row.isVisible()
    assert d.format == "sqlite"
    d.path_input.setText(str(tmp_path / "x"))
    d.save_button.click()
    assert manager.config.mode == "database"
    assert (tmp_path / "appdata" / "library.db").is_file()


@pytest.mark.parametrize("text,expected", [
    ("", "Informe a pasta"),
    ("relativo/pasta", "caminho completo"),
])
def test_invalid_path_shows_translated_error_and_stays_open(qtbot, manager, text, expected):
    d = dialog(qtbot, manager)
    d.path_input.setText(text)
    d.save_button.click()
    assert d.result() != QDialog.Accepted
    assert d.error_label.isVisible() and expected in d.error_label.text()
    assert manager.status() != STATUS_READY
    d.path_input.setText("/tmp")
    assert not d.error_label.isVisible()


def test_path_pointing_to_a_file_is_rejected(qtbot, manager, tmp_path):
    f = tmp_path / "arquivo.txt"
    f.write_text("x")
    d = dialog(qtbot, manager)
    d.path_input.setText(str(f))
    d.save_button.click()
    assert "não é uma pasta" in d.error_label.text()


def test_browse_fills_path(qtbot, manager, monkeypatch, tmp_path):
    monkeypatch.setattr("app.ui.dialogs.storage_dialog.QFileDialog.getExistingDirectory", lambda *a, **k: str(tmp_path / "escolhida"))
    d = dialog(qtbot, manager)
    d.browse_button.click()
    assert d.path_input.text() == str(tmp_path / "escolhida")


def test_browse_cancel_keeps_current_path(qtbot, manager, monkeypatch):
    monkeypatch.setattr("app.ui.dialogs.storage_dialog.QFileDialog.getExistingDirectory", lambda *a, **k: "")
    d = dialog(qtbot, manager)
    before = d.path_input.text()
    d.browse_button.click()
    assert d.path_input.text() == before


def test_change_offers_migration_when_library_has_data(qtbot, manager, tmp_path):
    manager.configure(tmp_path / "a", "folder", "json")
    manager.store.add_video(Video(source_id="abcdefghijk", url="https://youtu.be/abcdefghijk", title="Meu vídeo"))
    d = dialog(qtbot, manager, first_run=False)
    assert d.cancel_button.text() == "Cancelar"
    assert not d.migrate_check.isVisible()  # mesmo local
    d.path_input.setText(str(tmp_path / "b"))
    assert d.migrate_check.isVisible() and d.migrate_check.isChecked()
    assert "1 vídeos" in d.migrate_check.text()
    d.format_combo.setCurrentIndex(d.format_combo.findData("sqlite"))
    d.save_button.click()
    assert manager.store.list_videos()[0].title == "Meu vídeo"
    assert (tmp_path / "a" / "data" / "library.json").is_file()


def test_user_can_decline_migration_and_choice_is_remembered(qtbot, manager, tmp_path):
    manager.configure(tmp_path / "a", "folder", "json")
    manager.store.add_video(Video(source_id="abcdefghijk", url="u", title="V"))
    d = dialog(qtbot, manager, first_run=False)
    d.path_input.setText(str(tmp_path / "b"))
    d.migrate_check.click()
    assert not d.migrate_check.isChecked()
    d.path_input.setText(str(tmp_path / "c"))
    assert not d.migrate_check.isChecked()
    d.save_button.click()
    assert manager.store.list_videos() == []


def test_existing_target_library_is_never_overwritten(qtbot, manager, tmp_path):
    manager.configure(tmp_path / "b", "folder", "json")
    manager.store.add_video(Video(source_id="bbbbbbbbbbb", url="u", title="Do destino"))
    manager.configure(tmp_path / "a", "folder", "json")
    manager.store.add_video(Video(source_id="aaaaaaaaaaa", url="u", title="Da origem"))
    d = dialog(qtbot, manager, first_run=False)
    d.path_input.setText(str(tmp_path / "b"))
    assert not d.migrate_check.isVisible()
    assert "já tem uma biblioteca" in d.notice_label.text()
    d.save_button.click()
    assert [v.title for v in manager.store.list_videos()] == ["Do destino"]


def test_cancel_changes_nothing(qtbot, manager, tmp_path):
    manager.configure(tmp_path / "a", "folder", "json")
    d = dialog(qtbot, manager, first_run=False)
    d.path_input.setText(str(tmp_path / "b"))
    d.cancel_button.click()
    assert d.result() == QDialog.Rejected
    assert manager.config.root == tmp_path / "a"
    assert not (tmp_path / "b").exists()


def make_window(qtbot, settings, manager):
    from app.infrastructure.providers.chain import ProviderChain
    from tests.fakes import FakeProvider

    from tests.fakes import make_stub_player

    w = create_window(
        QApplication.instance(), settings, manager, ProviderChain([FakeProvider("fake")]),
        player_options={"local_factory": make_stub_player, "online_factory": make_stub_player},
    )
    qtbot.addWidget(w)
    w.show()
    return w


def test_settings_card_shows_unconfigured_then_real_values(qtbot, settings, manager, tmp_path):
    w = make_window(qtbot, settings, manager)
    page = w.settings_page
    assert page.storage_rows["path"][1].text() == "Não configurado"
    assert not page.open_folder_button.isEnabled()
    manager.configure(tmp_path / "lib", "folder", "json")
    manager.store.add_video(Video(source_id="abcdefghijk", url="u"))
    (tmp_path / "lib" / "videos" / "a.mp4").write_bytes(b"0" * 4096)
    page.refresh_storage()
    assert page.storage_rows["path"][1].text() == str(tmp_path / "lib")
    assert page.storage_rows["format"][1].text() == "JSON"
    assert "1 vídeos" in page.storage_rows["library"][1].text()
    assert "1 arquivos · 4.0 KB" == page.storage_rows["files"][1].text()
    assert page.open_folder_button.isEnabled()


def test_settings_card_warns_when_root_is_missing(qtbot, settings, manager, tmp_path):
    import shutil

    manager.configure(tmp_path / "lib", "folder", "sqlite")
    manager.close()
    shutil.rmtree(tmp_path / "lib")
    w = make_window(qtbot, settings, StorageManager(settings, tmp_path / "appdata"))
    assert w.settings_page.storage_warning.isVisible() or w.settings_page.storage_warning.text() != ""
    assert "não foi encontrada" in w.settings_page.storage_warning.text()


def test_ensure_storage_runs_dialog_only_when_needed(qtbot, settings, manager, tmp_path, monkeypatch):
    calls = []

    def fake_exec(self):
        calls.append(self._first_run)
        self._manager.configure(tmp_path / "lib", "folder", "sqlite")
        return QDialog.Accepted

    monkeypatch.setattr(StorageDialog, "exec", fake_exec)
    w = make_window(qtbot, settings, manager)
    assert w.ensure_storage() is True and calls == [True]
    assert w.ensure_storage() is True and calls == [True]  # já configurado: não pergunta de novo


def test_ensure_storage_returns_false_when_user_quits(qtbot, settings, manager, monkeypatch):
    monkeypatch.setattr(StorageDialog, "exec", lambda self: QDialog.Rejected)
    w = make_window(qtbot, settings, manager)
    assert w.ensure_storage() is False


def test_change_button_opens_dialog_and_refreshes_card(qtbot, settings, manager, tmp_path, monkeypatch):
    manager.configure(tmp_path / "a", "folder", "json")
    w = make_window(qtbot, settings, manager)

    def fake_exec(self):
        self._manager.configure(tmp_path / "b", "folder", "sqlite")
        return QDialog.Accepted

    monkeypatch.setattr(StorageDialog, "exec", fake_exec)
    w.settings_page.change_storage_button.click()
    assert w.settings_page.storage_rows["path"][1].text() == str(tmp_path / "b")
    assert w.settings_page.storage_rows["format"][1].text() == "SQLite"


def test_card_texts_follow_language(qtbot, settings, manager, tmp_path):
    manager.configure(tmp_path / "a", "database", "sqlite")
    w = make_window(qtbot, settings, manager)
    combo = w.settings_page.language_combo
    combo.setCurrentIndex(combo.findData("en"))
    assert w.settings_page.open_folder_button.text() == "Open folder"
    assert w.settings_page.storage_rows["mode"][1].text() == "Database"
