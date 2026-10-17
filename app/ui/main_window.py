from PySide6.QtCore import QSize, Qt, QTimer, QUrl
from PySide6.QtGui import QDesktopServices, QKeySequence, QShortcut
from PySide6.QtWidgets import QApplication, QFrame, QMessageBox, QHBoxLayout, QMainWindow, QStackedWidget, QToolButton, QVBoxLayout, QWidget

from app import APP_NAME
from app.infrastructure.media.ffmpeg import MediaError, bundled_root, locate
from app.services.download_service import DownloadManager
from app.domain.history import SMART_PLAYLISTS
from app.services.library_service import LibraryService
from app.services.organization_service import OrganizationService
from app.services.progress_service import ProgressService
from app.ui.dialogs.name_dialog import NameDialog
from app.ui.organize_menus import OrganizeMenus
from app.ui.player import shortcuts
from app.ui.query_state import QueryState
from app.styles.icons import icon
from app.ui.pages.downloads_page import DownloadsPage
from app.ui.pages.categories_page import CategoriesPage
from app.ui.pages.history_pages import ContinuePage, HistoryPage
from app.ui.pages.playlists_page import PlaylistDetailPage, PlaylistsPage
from app.ui.pages.library_page import LibraryPage
from app.ui.pages.video_pages import DownloadedPage, HomePage
from app.ui.pages.watch_page import WatchPage, watch_url
from app.ui.workers import run_async
from app.services.storage_service import STATUS_READY
from app.ui.dialogs.storage_dialog import StorageDialog
from app.ui.pages.settings_page import SettingsPage
from app.ui.widgets.sidebar import Sidebar
from app.ui.widgets.url_bar import TopBar

DEFAULT_PAGE = "home"


class MainWindow(QMainWindow):
    def __init__(self, settings, translator, theme, storage, providers, thumbnails=None, tools_getter=None, player_options=None):
        super().__init__()
        self._settings = settings
        self._storage = storage
        self.library = LibraryService(storage, providers, thumbnails)
        self.progress = ProgressService(self.library)
        self.org = OrganizationService(self.library)
        self.query_state = QueryState(settings)
        self.organize = OrganizeMenus(translator, self.org, self._prompt_category, self._prompt_playlist, self._on_organized)
        self._tools = None
        self._tools_getter = tools_getter
        self.downloads = DownloadManager(
            self.library, providers, self._ffmpeg_tools, max_concurrent=settings.download_concurrent
        )
        self._tr = translator
        self._theme = theme
        self.setWindowTitle(APP_NAME)
        self.setMinimumSize(900, 600)
        self.resize(1280, 800)

        tokens = theme.tokens
        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)
        row = QHBoxLayout(root)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)

        self.sidebar = Sidebar(translator, tokens, settings.sidebar_collapsed)
        row.addWidget(self.sidebar)

        column = QVBoxLayout()
        column.setSpacing(0)
        self.top_bar = TopBar(translator, tokens)
        column.addWidget(self.top_bar)

        self.stack = QStackedWidget()
        self.pages = {}
        library = self.library
        video_args = dict(
            can_download=lambda: library.ready, download_status=self.downloads.status_for_video, organize=self.organize,
            progress=self.progress,
        )
        for page in (
            HomePage(translator, library, tokens, org=self.org, **video_args),
            ContinuePage(translator, library, tokens, self.org, **video_args),
            LibraryPage(translator, library, tokens, self.org, self.query_state, settings, **video_args),
            DownloadedPage(translator, library, tokens, **video_args),
            PlaylistsPage(translator, self.org, library, tokens, self._prompt_playlist),
            CategoriesPage(translator, self.org, library, tokens, self._prompt_category),
            HistoryPage(
                translator, library, tokens, self.org, self.progress,
                can_download=video_args["can_download"], download_status=video_args["download_status"], organize=self.organize,
            ),
            DownloadsPage(translator, self.downloads, library, tokens),
        ):
            self._add_page(page)
        self.settings_page = SettingsPage(translator, settings.language, settings.theme, storage)
        self.settings_page.language_selected.connect(self._on_language)
        self.settings_page.theme_selected.connect(self._on_theme)
        self.settings_page.change_storage_requested.connect(self.change_storage)
        self.settings_page.open_storage_requested.connect(self._open_storage_folder)
        self._add_page(self.settings_page)
        self.watch_page = WatchPage(
            translator, library, tokens, self.downloads, self._ask_download_consent, self.progress, settings, player_options, self.organize
        )
        self.watch_page.playback_ended.connect(self._on_playback_ended)
        self.playlist_page = PlaylistDetailPage(translator, self.org, library, tokens)
        self._add_page(self.playlist_page)
        self._playlist_id = None
        self.watch_page.back_requested.connect(self._go_back)
        self.watch_page.message.connect(self.top_bar.show_message)
        self._add_page(self.watch_page)
        for page in self.pages.values():
            if hasattr(page, "video_opened"):
                page.video_opened.connect(self.open_saved_video)
            if hasattr(page, "video_action"):
                page.video_action.connect(self._on_video_action)
        self.pages["home"].category_all_requested.connect(lambda cid: self.show_library_with(category_ids=frozenset({cid})))
        self.pages["history"].message.connect(self.top_bar.show_message)
        self.pages["categories"].message.connect(self.top_bar.show_message)
        self.pages["categories"].category_opened.connect(lambda cid: self.show_library_with(category_ids=frozenset({cid})))
        self.pages["playlists"].message.connect(self.top_bar.show_message)
        self.pages["playlists"].playlist_opened.connect(self.open_playlist)
        self.pages["playlists"].play_requested.connect(lambda pid: self.play_playlist(pid))
        self.pages["playlists"].smart_opened.connect(self.open_smart_playlist)
        self.pages["playlists"].smart_play_requested.connect(self.play_smart_playlist)
        self.playlist_page.back_requested.connect(lambda: self.show_page("playlists"))
        self.playlist_page.play_requested.connect(self.play_playlist)
        self.pages["downloads"].message.connect(self.top_bar.show_message)
        self.pages["library"].message.connect(self.top_bar.show_message)
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(250)
        self._search_timer.timeout.connect(self._apply_search)
        self.top_bar.search_changed.connect(lambda _text: self._search_timer.start())
        self.query_state.changed.connect(self._sync_search_field)
        library.changed.connect(self._on_library_changed)
        self.downloads.queue_changed.connect(self._on_downloads_changed)
        column.addWidget(self.stack, 1)

        # Rodapé com a engrenagem de configurações no canto inferior direito
        footer = QFrame()
        footer.setObjectName("footer")
        footer_row = QHBoxLayout(footer)
        footer_row.setContentsMargins(12, 4, 12, 8)
        footer_row.addStretch(1)
        self.settings_button = QToolButton()
        self.settings_button.setObjectName("iconButton")
        self.settings_button.setCheckable(True)
        self.settings_button.setIconSize(QSize(20, 20))
        self.settings_button.setCursor(Qt.PointingHandCursor)
        self.settings_button.clicked.connect(self._toggle_settings)
        footer_row.addWidget(self.settings_button)
        column.addWidget(footer)
        row.addLayout(column, 1)

        self.sidebar.page_selected.connect(self.show_page)
        self.sidebar.collapsed_changed.connect(lambda c: setattr(settings, "sidebar_collapsed", c))
        self.top_bar.video_requested.connect(self._on_video_requested)
        self._previous_page = DEFAULT_PAGE
        self._back_page = DEFAULT_PAGE

        QShortcut(QKeySequence("Ctrl+K"), self, activated=self.top_bar.focus_search)
        QShortcut(QKeySequence("Ctrl+L"), self, activated=self.top_bar.focus_url)
        QShortcut(QKeySequence("Ctrl+,"), self, activated=lambda: self.show_page("settings"))

        theme.theme_changed.connect(self._apply_tokens)
        self._apply_tokens()
        self.retranslate()
        last = settings.last_page
        self.show_page(last if last in self.pages else DEFAULT_PAGE)

    def _add_page(self, page):
        self.pages[page.key] = page
        self.stack.addWidget(page)

    @property
    def current_page(self):
        return self.stack.currentWidget().key

    def show_page(self, key):
        if key not in self.pages:
            return
        if key not in ("settings", "watch", "playlist"):
            self._previous_page = key
        self.stack.setCurrentWidget(self.pages[key])
        self.settings_button.setChecked(key == "settings")
        self.sidebar.select("playlists" if key == "playlist" else key)
        if key not in ("watch", "playlist"):
            self._settings.last_page = key

    def _toggle_settings(self):
        if self.current_page == "settings":
            self.show_page(self._previous_page)
        else:
            self.show_page("settings")

    def ensure_storage(self):
        """Garante uma pasta de biblioteca válida. No primeiro uso o diálogo só termina salvando ou saindo."""
        if self._storage.status() == STATUS_READY:
            return True
        accepted = StorageDialog(self._tr, self._storage, first_run=True, parent=self).exec() == StorageDialog.Accepted
        self.settings_page.refresh_storage()
        self.library.notify()
        return accepted

    def change_storage(self):
        if StorageDialog(self._tr, self._storage, first_run=False, parent=self).exec() == StorageDialog.Accepted:
            self.settings_page.refresh_storage()
            self.library.notify()

    def _open_storage_folder(self):
        if self._storage.status() == STATUS_READY:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self._storage.config.root)))

    def _on_video_requested(self, source_id):
        self._enter_watch()
        self.watch_page.open_source_id(source_id)

    def open_saved_video(self, video_id, playlist_id=None):
        """Abre um vídeo da biblioteca. Com `playlist_id`, a reprodução segue para o próximo item ao terminar."""
        self._playlist_id = playlist_id
        self._enter_watch()
        self.watch_page.open_saved(video_id)
        self._refresh_playlist_context(video_id)

    def open_playlist(self, playlist_id):
        self.playlist_page.show_playlist(playlist_id)
        self.show_page("playlist")

    def play_playlist(self, playlist_id, start_video_id=0):
        """Reproduz a playlist na ordem escolhida, a partir do primeiro item ou de `start_video_id`."""
        ids = self.org.playlist_video_ids(playlist_id)
        if not ids:
            return
        self.open_saved_video(start_video_id if start_video_id in ids else ids[0], playlist_id)

    def open_smart_playlist(self, key):
        """Playlist inteligente = a biblioteca com a consulta correspondente já aplicada."""
        self.query_state.open(SMART_PLAYLISTS[key])
        self.show_page("library")

    def play_smart_playlist(self, key):
        videos = self.org.query(SMART_PLAYLISTS[key])
        if videos:
            self.open_saved_video(videos[0].id)

    def _refresh_playlist_context(self, video_id):
        playlist = self.org.get_playlist(self._playlist_id) if self._playlist_id is not None else None
        ids = self.org.playlist_video_ids(self._playlist_id) if playlist is not None else []
        if playlist is not None and video_id in ids:
            self.watch_page.set_playlist_context(playlist.name, ids.index(video_id) + 1, len(ids))
        else:
            self._playlist_id = None
            self.watch_page.set_playlist_context(None)

    def _on_playback_ended(self):
        """Fim do vídeo dentro de uma playlist: segue para o próximo item (se houver)."""
        video = self.watch_page.player.video
        if self._playlist_id is None or video is None:
            return
        following = self.org.next_in_playlist(self._playlist_id, video.id)
        if following is not None:
            self.open_saved_video(following.id, self._playlist_id)
        else:
            self._playlist_id = None
            self.watch_page.set_playlist_context(None)

    def _enter_watch(self):
        if self.current_page != "watch":
            self._back_page = self.current_page
        self.show_page("watch")

    def _go_back(self):
        self.show_page(self._back_page if self._back_page in self.pages else DEFAULT_PAGE)

    # -- busca e organização --------------------------------------------------------------------
    def _apply_search(self):
        """A busca da barra superior filtra a biblioteca (com debounce) e leva o usuário até ela."""
        text = self.top_bar.search_input.text()
        self.query_state.set_text(text)
        if text.strip() and self.current_page != "library":
            self.show_page("library")

    def _sync_search_field(self):
        field = self.top_bar.search_input
        if field.text() != self.query_state.query.text:
            field.blockSignals(True)
            field.setText(self.query_state.query.text)
            field.blockSignals(False)

    def show_library_with(self, **filters):
        """Abre a biblioteca já filtrada (ex.: por categoria ou playlist)."""
        self.query_state.focus(**filters)
        self.show_page("library")

    def _prompt_category(self, existing=None):
        return self._prompt_name(existing, "dialog.category_new", "dialog.category_edit", True,
                                 self.org.create_category, self.org.update_category)

    def _prompt_playlist(self, existing=None):
        return self._prompt_name(existing, "dialog.playlist_new", "dialog.playlist_edit", False,
                                 lambda name, desc, _color: self.org.create_playlist(name, desc),
                                 lambda pid, name, desc, _color: self.org.update_playlist(pid, name, desc))

    def _prompt_name(self, existing, new_key, edit_key, with_color, create, update):
        """Diálogo de nome (e cor). Devolve o item criado/editado ou None se o usuário cancelou."""
        result = {}

        def submit(name, description, color):
            if existing is None:
                result["item"] = create(name, description, color)
            else:
                result["item"] = update(existing.id, name, description, color)

        dialog = NameDialog(
            self._tr, edit_key if existing else new_key, submit, with_color,
            name=getattr(existing, "name", ""), description=getattr(existing, "description", ""),
            color=getattr(existing, "color", None), parent=self,
        )
        return result.get("item") if dialog.exec() == NameDialog.Accepted else None

    def _on_organized(self, kind):
        self.top_bar.show_message(self._tr.t("bulk.categories_toast" if kind == "categories" else "bulk.playlist_toast"), False)

    def _ffmpeg_tools(self):
        """ffmpeg/ffprobe verificados (a checagem roda uma vez). Levanta MediaError se faltarem."""
        if self._tools is None:
            if self._tools_getter is not None:
                self._tools = self._tools_getter()
            else:
                tools = locate(bundled_root(), self._settings.ffmpeg_path or None)
                if tools is None:
                    raise MediaError("ffmpeg_missing", "nenhum ffmpeg encontrado")
                self._tools = tools.check()
        return self._tools

    def _ask_download_consent(self):
        """Pede, uma única vez, a confirmação de que o download é para uso pessoal e legítimo."""
        if self._settings.download_consent:
            return True
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Information)
        box.setWindowTitle(self._tr.t("dl.consent_title"))
        box.setText(self._tr.t("dl.consent_body"))
        ok = box.addButton(self._tr.t("dl.consent_ok"), QMessageBox.AcceptRole)
        box.addButton(self._tr.t("storage.cancel"), QMessageBox.RejectRole)
        box.exec()
        if box.clickedButton() is ok:
            self._settings.download_consent = True
            return True
        return False

    def _on_downloads_changed(self):
        self.sidebar.set_badge("downloads", self.downloads.active_count())
        self._on_library_changed()

    def closeEvent(self, event):
        self.downloads.shutdown()
        self.watch_page.player.shutdown()  # grava a posição e encerra o Chromium na ordem certa
        super().closeEvent(event)

    def keyPressEvent(self, event):
        """Atalhos do player. Só chegam aqui as teclas que o widget em foco não usou (campos de texto ficam livres)."""
        if self.current_page == "watch":
            action = shortcuts.action_for(event.key(), event.modifiers())
            if action and not shortcuts.should_ignore(QApplication.focusWidget(), action):
                self.watch_page.player.perform(action)
                event.accept()
                return
        super().keyPressEvent(event)

    def _on_library_changed(self):
        for page in self.pages.values():
            if hasattr(page, "mark_dirty"):
                page.mark_dirty()

    def _on_video_action(self, video_id, action):
        video = self.library.get(video_id)
        if video is None:
            return
        if action == "watch":
            self.progress.mark_watched(video_id, True)
        elif action == "unwatch":
            self.progress.mark_watched(video_id, False)
        elif action == "restart":
            self.progress.restart(video_id)
        elif action == "forget":
            self.progress.forget(video_id)
        elif action == "download":
            self.open_saved_video(video_id)
        elif action == "browser":
            url = watch_url(video.source_id)
            if url:
                QDesktopServices.openUrl(QUrl(url))
        elif action == "folder":
            path = self.library.local_path(video)
            if path is not None:
                QDesktopServices.openUrl(QUrl.fromLocalFile(str(path.parent)))
        elif action == "remove":
            if video.local_status == "ok" and not self._confirm_remove():
                return
            self.library.remove(video_id)

    def _confirm_remove(self):
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Question)
        box.setWindowTitle(self._tr.t("watch.confirm_remove_title"))
        box.setText(self._tr.t("watch.confirm_remove_body"))
        remove = box.addButton(self._tr.t("watch.remove"), QMessageBox.AcceptRole)
        box.addButton(self._tr.t("storage.cancel"), QMessageBox.RejectRole)
        box.exec()
        return box.clickedButton() is remove

    def start_background_checks(self):
        """Confere em segundo plano se os arquivos baixados ainda existem."""
        if self.library.ready:
            self.downloads.cleanup_orphans()
            run_async(self.library.validate_all)

    def _on_language(self, code):
        self._settings.language = code
        self._tr.set_language(code)
        self.retranslate()

    def _on_theme(self, name):
        self._settings.theme = name
        self.settings_page.set_theme(name)
        self._theme.apply(name)

    def _apply_tokens(self):
        tokens = self._theme.tokens
        self.sidebar.set_tokens(tokens)
        self.top_bar.set_tokens(tokens)
        self.settings_button.setIcon(icon("settings", tokens["text_secondary"]))
        for page in self.pages.values():
            page.set_tokens(tokens)

    def retranslate(self):
        label = self._tr.t("nav.settings")
        self.settings_button.setToolTip(f"{label} (Ctrl+,)")
        self.settings_button.setAccessibleName(label)
        self.sidebar.refresh()
        self.top_bar.retranslate()
        for page in self.pages.values():
            page.retranslate()
