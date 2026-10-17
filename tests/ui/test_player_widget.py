import pytest
from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication, QLineEdit

from app.ui.player import shortcuts
from app.ui.player.player_widget import PlayerWidget
from tests.fakes import VID

DUR = 200.0


@pytest.fixture
def w(window_factory):
    return window_factory()


def saved(w, fake_provider, source_id=VID):
    video, _ = w.library.save_info(fake_provider.fetch_info(source_id))
    return video


def downloaded(w, fake_provider, source_id=VID, name="a.mp4"):
    video = saved(w, fake_provider, source_id)
    f = w.library.layout.videos / name
    f.write_bytes(b"0" * 2048)
    return w.library.attach_local_file(video.id, f, "720p")


def open_in_player(w, video):
    w.open_saved_video(video.id)
    QApplication.processEvents()
    return w.watch_page.player


def local(player):
    return player._local


def online(player):
    return player._online


# ---------- escolha da fonte ----------
def test_downloaded_video_plays_the_local_file_first(w, fake_provider):
    video = downloaded(w, fake_provider)
    player = open_in_player(w, video)
    assert player.kind == "local" and local(player).names()[0] == "load_file"
    assert local(player).calls[0][1].endswith("a.mp4") and online(player) is None  # o online nem é criado
    assert player.controls.source_chip.text() == "Local"


def test_saved_but_not_downloaded_video_plays_online(w, fake_provider):
    player = open_in_player(w, saved(w, fake_provider))
    assert player.kind == "online" and online(player).calls[0] == ("load", VID, 0.0)
    assert player.controls.source_chip.text() == "Online" and local(player) is None


def test_unsaved_video_from_link_plays_online(w, fake_provider, qtbot):
    w.top_bar.url_input.setText(f"https://youtu.be/{VID}")
    w.top_bar.open_button.click()
    qtbot.waitUntil(lambda: w.watch_page.player.kind == "online", timeout=10000)
    assert w.watch_page.player.video is None


def test_missing_local_file_falls_back_to_online(w, fake_provider):
    video = downloaded(w, fake_provider)
    (w.library.layout.videos / "a.mp4").unlink()
    player = open_in_player(w, video)
    assert player.kind == "online"


def test_no_webengine_shows_message_with_browser_option(window_factory, fake_provider, qtbot):
    from tests.fakes import make_stub_player

    w = window_factory()
    w.watch_page.player._online_factory = lambda: None
    player = open_in_player(w, saved(w, fake_provider))
    assert player.stack.currentWidget() is player.message and "não está disponível" in player.message.label.text()
    with qtbot.waitSignal(player.browser_requested):
        player.message.buttons[0].click()


# ---------- retomar de onde parou ----------
def test_resumes_from_saved_position_with_notice_and_can_restart(w, fake_provider):
    video = downloaded(w, fake_provider)
    w.progress.save(video.id, 42, DUR)
    player = open_in_player(w, video)
    assert local(player).calls[0][2] == 42.0
    assert player.notice.isVisible() and "0:42" in player.notice_label.text()
    player.restart_button.click()
    assert not player.notice.isVisible() and ("seek", 0.0) in local(player).calls
    assert w.progress.get(video.id).position == 0.0 and w.progress.resume_position(video.id) == 0.0


def test_online_resume_passes_start_to_the_embed(w, fake_provider):
    video = saved(w, fake_provider)
    w.progress.save(video.id, 80, DUR)
    player = open_in_player(w, video)
    assert online(player).calls[0] == ("load", VID, 80.0)


def test_watched_video_starts_from_the_beginning(w, fake_provider):
    video = downloaded(w, fake_provider)
    w.progress.save(video.id, 199, DUR)  # 99%: assistido
    player = open_in_player(w, video)
    assert local(player).calls[0][2] == 0.0 and not player.notice.isVisible()


# ---------- salvar progresso ----------
def test_progress_is_saved_on_pause_and_on_stop(w, fake_provider):
    video = downloaded(w, fake_provider)
    player = open_in_player(w, video)
    stub = local(player)
    stub.position_changed.emit(30.0, DUR)
    stub.state_changed.emit(True)
    stub.state_changed.emit(False)  # pausou
    assert w.progress.get(video.id).position == 30.0
    stub.position_changed.emit(55.0, DUR)
    player.stop()
    assert w.progress.get(video.id).position == 55.0


def test_ending_marks_as_watched_and_next_open_does_not_resume(w, fake_provider):
    video = downloaded(w, fake_provider)
    player = open_in_player(w, video)
    stub = local(player)
    stub.position_changed.emit(DUR - 1, DUR)
    stub.ended.emit()
    got = w.progress.get(video.id)
    assert got.watched is True and got.position == 0.0
    w.show_page("library")
    player = open_in_player(w, video)
    assert local(player).calls[-1][2] == 0.0


def test_unsaved_video_never_writes_progress(w, fake_provider, qtbot):
    w.top_bar.url_input.setText(f"https://youtu.be/{VID}")
    w.top_bar.open_button.click()
    qtbot.waitUntil(lambda: w.watch_page.player.kind == "online", timeout=10000)
    stub = online(w.watch_page.player)
    stub.position_changed.emit(20.0, DUR)
    stub.state_changed.emit(False)
    assert w.library.list_videos() == []


def test_saving_while_watching_starts_tracking_without_restarting(w, fake_provider, qtbot):
    w.top_bar.url_input.setText(f"https://youtu.be/{VID}")
    w.top_bar.open_button.click()
    qtbot.waitUntil(lambda: w.watch_page.player.kind == "online", timeout=10000)
    player = w.watch_page.player
    stub = online(player)
    loads = stub.names().count("load")
    stub.position_changed.emit(25.0, DUR)
    w.watch_page.save_button.click()
    qtbot.waitUntil(lambda: player.video is not None, timeout=10000)
    assert stub.names().count("load") == loads  # a reprodução não reiniciou
    stub.state_changed.emit(True)
    stub.state_changed.emit(False)
    assert w.progress.get(player.video.id).position == 25.0


def test_leaving_the_page_stops_the_player_and_saves(w, fake_provider):
    video = downloaded(w, fake_provider)
    player = open_in_player(w, video)
    stub = local(player)
    stub.position_changed.emit(12.0, DUR)
    w.show_page("library")
    assert "stop" in stub.names() and player.kind == "" and w.progress.get(video.id).position == 12.0
    w.open_saved_video(video.id)  # voltar abre de novo (e retoma)
    assert local(w.watch_page.player).calls[-1][0] == "load_file"


# ---------- controles ----------
def test_play_button_and_click_on_video_toggle(w, fake_provider):
    player = open_in_player(w, downloaded(w, fake_provider))
    stub = local(player)
    assert stub.is_playing()  # abre tocando
    player.controls.play_button.click()
    assert "pause" in stub.names() and not stub.is_playing()
    player.controls.play_button.click()
    assert stub.is_playing()
    stub.clicked.emit()  # clique na imagem do vídeo
    assert not stub.is_playing()


def test_seek_slider_release_seeks_proportionally(w, fake_provider):
    player = open_in_player(w, downloaded(w, fake_provider))
    stub = local(player)
    stub.position_changed.emit(0.0, DUR)
    c = player.controls
    c.seek_slider.setValue(500)
    c._seeking = True
    c._commit_seek()
    assert ("seek", 100.0) in stub.calls
    stub.position_changed.emit(30.0, DUR)
    assert c.seek_slider.value() == 150 and c.time_label.text() == "0:30 / 3:20"


def test_volume_is_applied_persisted_and_restored(w, fake_provider, settings):
    player = open_in_player(w, downloaded(w, fake_provider))
    stub = local(player)
    player.controls.volume_slider.setValue(35)
    assert ("volume", 35) in stub.calls and settings.player_volume == 35
    stub.loaded.emit()
    assert stub.calls[-1] == ("volume", 35)  # restaurado ao carregar
    stub.status_changed.emit(35, True, 1.0)
    player.controls.volume_slider.setValue(50)  # mexer no volume tira o mudo
    assert ("muted", False) in stub.calls


def test_mute_button_and_icon_state(w, fake_provider):
    player = open_in_player(w, downloaded(w, fake_provider))
    stub = local(player)
    player.controls.mute_button.click()
    assert ("muted", True) in stub.calls
    stub.status_changed.emit(80, True, 1.0)
    assert player.controls.mute_button.toolTip().startswith("Reativar")


def test_speed_menu_applies_rate_and_marks_current(w, fake_provider):
    player = open_in_player(w, downloaded(w, fake_provider))
    stub = local(player)
    actions = player.controls.speed_button.menu().actions()
    assert [a.text() for a in actions] == ["0.5×", "0.75×", "1×", "1.25×", "1.5×", "1.75×", "2×"]
    next(a for a in actions if a.text() == "1.5×").trigger()
    assert ("rate", 1.5) in stub.calls
    stub.status_changed.emit(80, False, 1.5)
    assert player.controls.speed_button.text() == "1.5×"
    assert next(a for a in player.controls.speed_button.menu().actions() if a.isChecked()).text() == "1.5×"


def test_local_quality_shows_real_height_and_is_not_selectable(w, fake_provider):
    player = open_in_player(w, downloaded(w, fake_provider))
    stub = local(player)
    heights = []
    player.height_changed.connect(heights.append)
    stub.quality_changed.emit(720, [720])
    assert player.controls.quality_button.text() == "720p" and heights == [720]
    actions = player.controls.quality_button.menu().actions()
    assert len(actions) == 1 and not actions[0].isEnabled() and "720p" in actions[0].text()


def test_online_quality_menu_lists_levels_and_requests_change(w, fake_provider):
    player = open_in_player(w, saved(w, fake_provider))
    stub = online(player)
    stub._can_quality = True
    stub.quality_changed.emit(720, [1080, 720, 480])
    texts = [a.text() for a in player.controls.quality_button.menu().actions()]
    assert texts == ["Automática", "1080p", "720p", "480p"]
    next(a for a in player.controls.quality_button.menu().actions() if a.text() == "1080p").trigger()
    assert ("quality", 1080) in stub.calls
    player.controls.quality_button.menu().actions()[0].trigger()
    assert ("quality", None) in stub.calls
    QApplication.processEvents()  # o menu volta ao que o player reporta (720p), mesmo sem confirmar a troca
    assert next(a for a in player.controls.quality_button.menu().actions() if a.isChecked()).text() == "720p"


def test_playing_quality_feeds_the_download_default(w, fake_provider, qtbot):
    w.top_bar.url_input.setText(f"https://youtu.be/{VID}")
    w.top_bar.open_button.click()
    qtbot.waitUntil(lambda: w.watch_page.quality_combo.currentData() is not None, timeout=10000)
    assert w.watch_page.quality_combo.currentData() == 2160  # sem player: a maior disponível
    online(w.watch_page.player).quality_changed.emit(720, [720])
    assert w.watch_page.quality_combo.currentData() == 720  # acompanha o que está tocando


# ---------- erros e alternativas ----------
def error_buttons(player):
    return [b.text() for b in player.message.buttons]


def test_embed_blocked_offers_own_player_then_browser(w, fake_provider, qtbot):
    player = open_in_player(w, saved(w, fake_provider))
    online(player).error.emit("embed_blocked", "youtube:150")
    assert "não permite" in player.message.label.text()
    assert error_buttons(player) == ["Assistir com player próprio", "Abrir no navegador"]
    player.message.buttons[0].click()
    qtbot.waitUntil(lambda: player.kind == "stream", timeout=10000)
    url_call = next(c for c in local(player).calls if c[0] == "load_url")
    assert "googlevideo.com" in url_call[1] and player.controls.source_chip.text() == "Player próprio"


def test_own_player_failure_ends_with_browser_option(w, fake_provider, qtbot):
    fake_provider.url_error = "failed"
    player = open_in_player(w, saved(w, fake_provider))
    online(player).error.emit("embed_blocked", "youtube:150")
    player.message.buttons[0].click()
    qtbot.waitUntil(lambda: error_buttons(player) == ["Abrir no navegador"], timeout=10000)
    assert "player próprio" in player.message.label.text()
    with qtbot.waitSignal(player.browser_requested):
        player.message.buttons[0].click()


def test_unavailable_only_offers_browser(w, fake_provider):
    player = open_in_player(w, saved(w, fake_provider))
    online(player).error.emit("unavailable", "youtube:100")
    assert error_buttons(player) == ["Abrir no navegador"] and "não está disponível" in player.message.label.text()


def test_network_error_offers_retry_that_reopens(w, fake_provider):
    player = open_in_player(w, saved(w, fake_provider))
    stub = online(player)
    stub.error.emit("network", "timeout")
    assert error_buttons(player)[0] == "Tentar novamente"
    loads = stub.names().count("load")
    player.message.buttons[0].click()
    assert stub.names().count("load") == loads + 1 and player.kind == "online"


def test_local_failure_offers_online_with_current_position(w, fake_provider):
    video = downloaded(w, fake_provider)
    player = open_in_player(w, video)
    local(player).position_changed.emit(33.0, DUR)
    local(player).error.emit("local_failed", "codec")
    assert error_buttons(player) == ["Tentar novamente", "Assistir online", "Mostrar arquivo na pasta"]
    player.message.buttons[1].click()
    assert player.kind == "online" and online(player).calls[-1] == ("load", VID, 33.0)


def test_errors_from_a_backend_that_is_not_current_are_ignored(w, fake_provider):
    video = downloaded(w, fake_provider)
    player = open_in_player(w, video)
    old = local(player)
    w.show_page("library")
    old.error.emit("local_failed", "atrasado")
    assert player.stack.currentWidget() is not player.message


def test_failed_video_with_label_texts_follow_language(w, fake_provider):
    player = open_in_player(w, saved(w, fake_provider))
    combo = w.settings_page.language_combo
    combo.setCurrentIndex(combo.findData("en"))
    assert player.controls.play_button.toolTip().startswith("Play")
    online(player).error.emit("unavailable", "x")
    assert "not available" in player.message.label.text()


# ---------- atalhos ----------
@pytest.mark.parametrize("key,action", [
    (Qt.Key_Space, "play_pause"), (Qt.Key_K, "play_pause"), (Qt.Key_Left, "seek_back"), (Qt.Key_Right, "seek_forward"),
    (Qt.Key_Up, "volume_up"), (Qt.Key_Down, "volume_down"), (Qt.Key_M, "mute"), (Qt.Key_F, "fullscreen"), (Qt.Key_Escape, "exit_fullscreen"),
])
def test_keymap(key, action):
    assert shortcuts.action_for(key) == action
    assert shortcuts.action_for(key, Qt.ControlModifier) is None  # Ctrl+tecla é de outro atalho


def test_shortcuts_do_not_fire_while_typing_or_on_focused_controls(qtbot):
    from PySide6.QtWidgets import QPushButton, QSlider

    field, button, slider = QLineEdit(), QPushButton(), QSlider()
    for action in ("play_pause", "mute", "fullscreen", "seek_back"):
        assert shortcuts.should_ignore(field, action)
    assert shortcuts.should_ignore(button, "play_pause") and not shortcuts.should_ignore(button, "mute")
    assert shortcuts.should_ignore(slider, "seek_back") and not shortcuts.should_ignore(slider, "play_pause")
    assert not shortcuts.should_ignore(None, "play_pause")


def press(widget, key, mods=Qt.NoModifier):
    widget.keyPressEvent(QKeyEvent(QEvent.KeyPress, key, mods))


def test_window_keys_control_the_player_only_on_the_watch_page(w, fake_provider):
    video = downloaded(w, fake_provider)
    player = open_in_player(w, video)
    stub = local(player)
    assert stub.is_playing()  # abre tocando
    w.watch_page.setFocus()
    press(w, Qt.Key_Space)
    assert not stub.is_playing()
    press(w, Qt.Key_Space)
    assert stub.is_playing()
    press(w, Qt.Key_Right)
    assert ("seek", 5.0) in stub.calls
    press(w, Qt.Key_Left)
    assert ("seek", 0.0) in stub.calls  # nunca abaixo de zero
    press(w, Qt.Key_M)
    assert ("muted", True) in stub.calls
    w.show_page("library")
    calls_before = list(stub.calls)
    press(w, Qt.Key_Space)
    assert stub.calls == calls_before  # fora da tela do vídeo, as teclas não mexem no player


def test_typing_in_the_url_field_does_not_toggle_playback(w, fake_provider, qtbot):
    player = open_in_player(w, downloaded(w, fake_provider))
    stub = local(player)
    calls_before = list(stub.calls)
    w.top_bar.url_input.setFocus()
    qtbot.keyClick(w.top_bar.url_input, Qt.Key_Space)
    qtbot.keyClick(w.top_bar.url_input, Qt.Key_M)
    assert stub.calls == calls_before and stub.is_playing()  # nada chegou ao player
    assert w.top_bar.url_input.text() == " m"


def test_seek_is_clamped_to_duration_and_volume_to_range(w, fake_provider):
    player = open_in_player(w, downloaded(w, fake_provider))
    stub = local(player)
    stub.position_changed.emit(198.0, DUR)
    player.perform(shortcuts.SEEK_FORWARD)
    assert ("seek", 200.0) in stub.calls
    player.set_volume(98)
    player.perform(shortcuts.VOLUME_UP)
    assert player.controls.volume_slider.value() == 100
    player.set_volume(2)
    player.perform(shortcuts.VOLUME_DOWN)
    assert player.controls.volume_slider.value() == 0


# ---------- tela cheia ----------
def test_fullscreen_enter_and_exit_restores_position_in_layout(w, fake_provider):
    video = downloaded(w, fake_provider)
    player = open_in_player(w, video)
    host = player.parentWidget()
    layout = host.layout()
    index = layout.indexOf(player)
    player.toggle_fullscreen()
    assert player.is_fullscreen and player.parentWidget() is None and player.isWindow()
    assert player.controls.fullscreen_button.toolTip().startswith("Sair")
    press(player, Qt.Key_Escape)
    assert not player.is_fullscreen and player.parentWidget() is host and layout.indexOf(player) == index
    assert player.controls.fullscreen_button.toolTip().startswith("Tela cheia")


def test_escape_outside_fullscreen_does_nothing(w, fake_provider):
    player = open_in_player(w, downloaded(w, fake_provider))
    press(player, Qt.Key_Escape)
    assert not player.is_fullscreen


def test_shutdown_leaves_fullscreen_and_stops_everything(w, fake_provider):
    video = downloaded(w, fake_provider)
    player = open_in_player(w, video)
    local(player).position_changed.emit(10.0, DUR)
    player.toggle_fullscreen()
    player.shutdown()
    assert not player.is_fullscreen and w.progress.get(video.id).position == 10.0


def test_closing_the_window_shuts_the_player_down(w, fake_provider):
    video = downloaded(w, fake_provider)
    player = open_in_player(w, video)
    local(player).position_changed.emit(7.0, DUR)
    w.close()
    assert w.progress.get(video.id).position == 7.0


def test_stop_does_not_overwrite_newer_progress_on_the_next_open(w, fake_provider):
    video = downloaded(w, fake_provider)
    player = open_in_player(w, video)
    local(player).position_changed.emit(30.0, DUR)
    player.stop()
    assert w.progress.get(video.id).position == 30.0
    w.progress.save(video.id, 100.0, DUR)  # alteração posterior, vinda de outro lugar
    player.stop()  # um segundo stop() não pode regravar os 30 s antigos
    assert w.progress.get(video.id).position == 100.0
    w.open_saved_video(video.id)
    assert local(w.watch_page.player).calls[-1][2] == 100.0  # retoma do valor novo
