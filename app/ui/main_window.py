from PySide6.QtCore import QSize, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QKeySequence, QShortcut
from PySide6.QtWidgets import QApplication, QFileDialog, QFrame, QMessageBox, QHBoxLayout, QMainWindow, QStackedWidget, QToolButton, QVBoxLayout, QWidget

from app import APP_NAME
from app.infrastructure.media.ffmpeg import MediaError, bundled_root, locate
from app.services.download_service import DownloadManager
from app.domain.history import SMART_PLAYLISTS
from app.logging_setup import get_logger, setup_logging
from app.services.backup_service import BackupService
from app.services.diagnostics_service import build_report
from app.services.library_service import LibraryService
from app.services.maintenance_service import MaintenanceService
from app.services.provider_service import update_providers
from app.services.organization_service import OrganizationService
from app.services.progress_service import ProgressService
from app.services.queue_service import QueueService
from app.ui.dialogs.backup_dialog import BackupDialog
from app.ui.dialogs.name_dialog import NameDialog
from app.ui.dialogs.space_dialog import SpaceDialog
from app.ui.errors import describe_error
from app.ui.layout_controller import LayoutController
from app.ui.widgets.settings_cards import DownloadsCard, MaintenanceCard, PlaybackCard, ProvidersCard
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
from app.styles.backdrop import BackdropWidget
from app.ui.chrome.compact_bar import CompactBar
from app.ui.chrome.nav_tree import NavTree
from app.ui.chrome.status_bar import AppStatusBar
from app.ui.chrome.top_nav import TopNav
from app.ui.widgets.sidebar import NAV_ITEMS, Sidebar
from app.ui.widgets.url_bar import TopBar

DEFAULT_PAGE = "home"


class MainWindow(QMainWindow):
    maintenance_progress = Signal(int, int)  # emitido pela thread de trabalho; entregue na da interface

    def __init__(self, settings, translator, theme, storage, providers, thumbnails=None, tools_getter=None, player_options=None):
        super().__init__()
        self._settings = settings
        self._storage = storage
        self.library = LibraryService(storage, providers, thumbnails)
        self.progress = ProgressService(self.library)
        self.org = OrganizationService(self.library)
        self.queue = QueueService(self.library, settings)
        self.providers = providers
        self.maintenance = MaintenanceService(self.library, storage, self.library.thumbnails)
        self.backups = BackupService(self.library, storage)
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
        root = BackdropWidget(tokens)  # desenha o fundo do tema (gradiente + manchas, grade, papel…)
        self.backdrop = root
        self.setCentralWidget(root)
        shell = QVBoxLayout(root)  # [navegação do topo] / [corpo] / [barra de estado]
        shell.setContentsMargins(0, 0, 0, 0)
        shell.setSpacing(0)
        self.top_nav = TopNav(translator, tokens)
        self.top_nav.hide()
        shell.addWidget(self.top_nav)
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)
        shell.addLayout(row, 1)

        self.sidebar = Sidebar(translator, tokens, settings.sidebar_collapsed)
        row.addWidget(self.sidebar)
        self.nav_tree = NavTree(translator, tokens)  # navegação do layout Gerenciador
        self.nav_tree.hide()
        row.addWidget(self.nav_tree)

        column = QVBoxLayout()
        column.setSpacing(0)
        self.compact_bar = CompactBar(translator, tokens)  # layout Compacto: cabeçalho da janela pequena
        self.compact_bar.hide()
        column.addWidget(self.compact_bar)
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
        self.settings_page = SettingsPage(translator, settings.language, settings.theme, storage, settings)
        self.settings_page.language_selected.connect(self._on_language)
        self.settings_page.theme_selected.connect(self._on_theme)
        self.settings_page.layout_selected.connect(self._on_layout)
        self._build_settings_sections()
        self.settings_page.change_storage_requested.connect(self.change_storage)
        self.settings_page.open_storage_requested.connect(self._open_storage_folder)
        self._add_page(self.settings_page)
        self.watch_page = WatchPage(
            translator, library, tokens, self.downloads, self._ask_download_consent, self.progress, settings, player_options, self.organize,
            org=self.org, queue=self.queue,
        )
        self.watch_page.playback_ended.connect(self._on_playback_ended)
        self.watch_page.video_opened.connect(self.open_saved_video)
        self.watch_page.video_shown.connect(self.compact_bar.set_title)
        self.queue.changed.connect(self._sync_queue_current)
        self.queue.changed.connect(self.watch_page.refresh_queue)
        self.watch_page.queue_add_requested.connect(lambda video_id: self._queue_add([video_id]))
        self.watch_page.queue_previous_requested.connect(lambda: self._queue_step(-1))
        self.watch_page.queue_next_requested.connect(lambda: self._queue_step(1))
        self.watch_page.queue_remove_requested.connect(self.queue.remove)
        self.watch_page.queue_order_changed.connect(self.queue.set_order)
        self.watch_page.queue_clear_requested.connect(self.queue.clear)
        self.compact_bar.pin_toggled.connect(self._on_pin_toggled)
        self.compact_bar.full_requested.connect(lambda: self._on_layout(self._settings.layout_before_compact))
        self.compact_bar.paste_requested.connect(self._paste_link)
        self.compact_bar.set_pinned(settings.compact_on_top)
        self.watch_page.player.mini_changed.connect(self._on_mini_changed)
        self.watch_page.player.expand_requested.connect(self._enter_watch)
        self.playlist_page = PlaylistDetailPage(translator, self.org, library, tokens)
        self._add_page(self.playlist_page)
        self._playlist_id = None
        self.watch_page.back_requested.connect(self._go_back)
        self.watch_page.message.connect(self.notify)
        self._add_page(self.watch_page)
        for page in self.pages.values():
            if hasattr(page, "video_opened"):
                page.video_opened.connect(self.open_saved_video)
            if hasattr(page, "video_action"):
                page.video_action.connect(self._on_video_action)
        self.pages["home"].playlist_opened.connect(self.open_playlist)
        self.pages["home"].category_all_requested.connect(lambda cid: self.show_library_with(category_ids=frozenset({cid})))
        self.pages["history"].message.connect(self.notify)
        self.pages["categories"].message.connect(self.notify)
        self.pages["categories"].category_opened.connect(lambda cid: self.show_library_with(category_ids=frozenset({cid})))
        self.pages["playlists"].message.connect(self.notify)
        self.pages["playlists"].playlist_opened.connect(self.open_playlist)
        self.pages["playlists"].play_requested.connect(lambda pid: self.play_playlist(pid))
        self.pages["playlists"].smart_opened.connect(self.open_smart_playlist)
        self.pages["playlists"].smart_play_requested.connect(self.play_smart_playlist)
        self.playlist_page.back_requested.connect(lambda: self.show_page("playlists"))
        self.playlist_page.play_requested.connect(self.play_playlist)
        self.pages["downloads"].message.connect(self.notify)
        self.pages["library"].message.connect(self.notify)
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(250)
        self._search_timer.timeout.connect(self._apply_search)
        self._search_text = ""
        self.top_bar.search_changed.connect(self._on_search_typed)
        self.top_nav.search_changed.connect(self._on_search_typed)
        self.top_nav.page_selected.connect(self.show_page)
        self.top_nav.video_requested.connect(self._on_video_requested)
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
        self.footer = footer
        self._footer_row = footer_row
        row.addLayout(column, 1)
        self.status_bar = AppStatusBar(translator)  # layouts Gerenciador e Estação: a engrenagem muda para cá
        self.status_bar.hide()
        shell.addWidget(self.status_bar)
        self._status_timer = QTimer(self)
        self._status_timer.setSingleShot(True)
        self._status_timer.setInterval(200)
        self._status_timer.timeout.connect(self._refresh_status)
        self.nav_tree.query_requested.connect(self._on_tree_query)
        self.nav_tree.category_requested.connect(lambda cid: self.show_library_with(category_ids=frozenset({cid})))
        self.nav_tree.playlist_requested.connect(lambda pid: self.show_library_with(playlist_id=pid))
        self.nav_tree.page_requested.connect(self.show_page)
        self.pages["library"].selection_count_changed.connect(self._on_selection_count)
        self.query_state.changed.connect(self._sync_tree_selection)

        self.sidebar.page_selected.connect(self.show_page)
        self.sidebar.collapsed_changed.connect(lambda c: setattr(settings, "sidebar_collapsed", c))
        self.top_bar.video_requested.connect(self._on_video_requested)
        self._previous_page = DEFAULT_PAGE
        self._back_page = DEFAULT_PAGE
        self.layouts = LayoutController(self)

        QShortcut(QKeySequence("Ctrl+K"), self, activated=self.top_bar.focus_search)
        QShortcut(QKeySequence("Ctrl+L"), self, activated=self.top_bar.focus_url)
        QShortcut(QKeySequence("Ctrl+,"), self, activated=lambda: self.show_page("settings"))

        theme.theme_changed.connect(self._apply_tokens)
        self._apply_tokens()
        self.retranslate()
        self.layouts.apply(settings.layout)
        last = settings.last_page if settings.restore_last_page else DEFAULT_PAGE
        self.show_page(last if last in self.pages else DEFAULT_PAGE)

    def _add_page(self, page):
        self.pages[page.key] = page
        self.stack.addWidget(page)

    @property
    def current_page(self):
        return self.stack.currentWidget().key

    def show_page(self, key):
        key = self._redirect(key)
        if key not in self.pages:
            return
        if key not in ("settings", "watch", "playlist"):
            self._previous_page = key
        self.stack.setCurrentWidget(self.pages[key])
        self.top_nav.select(key)
        self._update_compact_title()
        self.layouts.on_page_changed(key)
        self.settings_button.setChecked(key == "settings")
        self.sidebar.select("playlists" if key == "playlist" else key)
        if key not in ("watch", "playlist"):
            self._settings.last_page = key

    def _update_compact_title(self):
        key = self.current_page if hasattr(self, "stack") and self.stack.currentWidget() is not None else "home"
        if key == "watch" and self.watch_page.player.video is not None:
            self.compact_bar.set_title(self.watch_page.player.video.title)
        else:
            self.compact_bar.set_title(self._tr.t(f"nav.{key}") if key in NAV_ITEMS or key == "settings" else "DinoTube")

    def _redirect(self, key):
        """Em layouts de tabela única (Gerenciador), Início, Baixados e Continuar viram consultas da própria biblioteca."""
        controller = getattr(self, "layouts", None)
        target = controller.profile.redirect(key) if controller is not None else None
        if target is None or key == target:
            return key
        if key == "downloaded":
            self.query_state.focus(state="downloaded")
        elif key == "continue":
            self.query_state.focus(watch="in_progress", sort="last_played")
        return target

    # -- árvore de navegação e barra de estado -------------------------------------------------------------
    def _on_tree_query(self, query):
        self.query_state.open(query)
        self.show_page("library")

    def _sync_tree_selection(self):
        if self.nav_tree.isVisible():
            self.nav_tree.select(self.nav_tree.key_for_query(self.query_state.query) if self.current_page == "library" else None)

    def _on_selection_count(self, count):
        self._selection_count = count
        self._update_status_selection()

    def _update_status_selection(self):
        n = getattr(self, "_selection_count", 0)
        t = self._tr.t
        self.status_bar.set_selection("" if n == 0 else (t("status.selected_one") if n == 1 else t("status.selected", count=n)))

    def _refresh_status(self):
        """Contagens da árvore e da barra de estado (com pequeno atraso: uma operação em lote dispara muitos avisos)."""
        if not self.library.ready or not (self.nav_tree.isVisible() or self.status_bar.isVisible()):
            return
        from app.domain.query import apply_query
        from app.services.storage_service import format_bytes

        t = self._tr.t
        data = self.org.load_data()
        from app.ui.chrome.nav_tree import LIBRARY_ENTRIES

        counts = {f"library/{key}": len(apply_query(query, data)) for key, _label, query in LIBRARY_ENTRIES}
        from app.domain.query import LibraryQuery

        for category in data.categories:
            counts[f"category/{category.id}"] = len(apply_query(LibraryQuery(category_ids=frozenset({category.id})), data))
        for playlist in data.playlists:
            counts[f"playlist/{playlist.id}"] = len(apply_query(LibraryQuery(playlist_id=playlist.id), data))
        counts["page/downloads"] = self.downloads.active_count()
        self.nav_tree.refresh(data, counts)
        self._sync_tree_selection()
        total, downloaded = len(data.videos), counts.get("library/downloaded", 0)
        self.status_bar.set_summary(t("status.videos_one") if total == 1 else t("status.videos", total=total, downloaded=downloaded))
        active = self.downloads.active_count()
        self.status_bar.set_downloads(t("status.downloads", count=active) if active else "")
        try:
            usage = self._storage.usage()
            self.status_bar.set_disk(t("status.disk", used=format_bytes(usage["videos_bytes"]), free=format_bytes(usage["free"])))
        except Exception:
            self.status_bar.set_disk("")
        self._update_status_selection()

    def schedule_status_refresh(self):
        self._status_timer.start()

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
        self._after_storage_ready()
        self.library.notify()
        return accepted

    def change_storage(self):
        if StorageDialog(self._tr, self._storage, first_run=False, parent=self).exec() == StorageDialog.Accepted:
            self.settings_page.refresh_storage()
            self._after_storage_ready()
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
        self.queue.set_current(video_id)  # só marca se o vídeo está na fila
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

    # -- fila de reprodução ---------------------------------------------------------------------
    def _queue_add(self, ids, play_next=False):
        self.queue.add(ids, play_next)
        self.notify(self._tr.t("queue.next_toast" if play_next else "queue.added_toast"), False)

    def _sync_queue_current(self):
        """O vídeo que está tocando e entra na fila vira o 'atual' dela."""
        video = self.watch_page.player.video
        if video is not None and video.id in self.queue and self.queue.current is None:
            self.queue.set_current(video.id)

    def _queue_step(self, direction):
        """Anterior (-1) ou próximo (+1) da fila, a partir do vídeo aberto ou do marcado como atual."""
        video = self.watch_page.player.video
        base = video.id if video is not None and video.id in self.queue else self.queue.current
        target = self.queue.next_id(base) if direction > 0 else self.queue.previous_id(base)
        if target is not None:
            self.open_saved_video(target)

    def _on_playback_ended(self):
        """Fim do vídeo: segue a fila (se ele está nela) ou a playlist (se há uma tocando)."""
        video = self.watch_page.player.video
        if video is not None and self._settings.autoplay_next and video.id in self.queue:
            following = self.queue.next_id(video.id)
            if following is not None:
                self._open_next(following)
                return
        if self._playlist_id is None or video is None or not self._settings.autoplay_next:
            return
        following = self.org.next_in_playlist(self._playlist_id, video.id)
        if following is not None:
            self._open_next(following.id, self._playlist_id)
        else:
            self._playlist_id = None
            self.watch_page.set_playlist_context(None)

    def _on_mini_changed(self, mini):
        if mini and self.current_page == "watch":
            self._go_back()

    def _open_next(self, video_id, playlist_id=None):
        """Abre o próximo da fila/playlist. No mini player, troca o vídeo sem tirar o usuário da página em que está."""
        if self.watch_page.player.is_mini:
            self._playlist_id = playlist_id
            self.queue.set_current(video_id)
            self.watch_page.open_saved(video_id)
            self._refresh_playlist_context(video_id)
        else:
            self.open_saved_video(video_id, playlist_id)

    def _enter_watch(self):
        self.watch_page.player.exit_mini()
        if self.current_page != "watch":
            self._back_page = self.current_page
        self.show_page("watch")

    def _go_back(self):
        self.show_page(self._back_page if self._back_page in self.pages else DEFAULT_PAGE)

    # -- seções de configurações: reprodução, downloads, provedores, manutenção ---------------------
    def _build_settings_sections(self):
        s, tr = self._settings, self._tr
        self.playback_card = PlaybackCard(tr, s)
        self.downloads_card = DownloadsCard(tr, s)
        self.providers_card = ProvidersCard(tr, s)
        self.maintenance_card = MaintenanceCard(tr)
        for card in (self.playback_card, self.downloads_card, self.providers_card, self.maintenance_card):
            self.settings_page.add_section(card)
        self.downloads_card.concurrency_changed.connect(self.downloads.set_max_concurrent)
        self.downloads_card.ffmpeg_browse_requested.connect(self._browse_ffmpeg)
        self.downloads_card.ffmpeg_path_changed.connect(self._set_ffmpeg_path)
        self.providers_card.order_changed.connect(lambda order: setattr(self.providers, "order", order))
        self.providers_card.update_requested.connect(self._update_providers)
        m = self.maintenance_card
        m.manage_space_requested.connect(self._open_space_dialog)
        m.backups_requested.connect(self._open_backup_dialog)
        m.verify_requested.connect(self._verify_files)
        m.refresh_requested.connect(self._refresh_metadata)
        m.clear_thumbs_requested.connect(self._clear_thumbnails)
        m.diagnostics_requested.connect(self._export_diagnostics)
        m.logs_requested.connect(self._open_logs)
        self.maintenance_progress.connect(m.show_progress)

    def _browse_ffmpeg(self):
        folder = QFileDialog.getExistingDirectory(self, self._tr.t("settings.ffmpeg_choose"), "")
        if folder:
            self._set_ffmpeg_path(folder)

    def _set_ffmpeg_path(self, path):
        self._settings.ffmpeg_path = path
        self._tools = None  # a próxima verificação usa o novo caminho
        self.refresh_ffmpeg_status()

    def refresh_ffmpeg_status(self):
        """Mostra a versão do ffmpeg em uso (a checagem roda em segundo plano) ou o motivo de não funcionar."""
        def check():
            return self._ffmpeg_tools()

        def done(tools):
            self.downloads_card.set_ffmpeg_status(self._tr.t("settings.ffmpeg_ok", version=tools.version_text.replace("ffmpeg version ", "")[:60]), True)

        def failed(exc):
            self.downloads_card.set_ffmpeg_status(describe_error(self._tr, getattr(exc, "code", "ffmpeg_missing")), False)

        run_async(check, done, failed)

    def _update_providers(self):
        self.providers_card.set_busy(True)
        run_async(update_providers, self._providers_updated, lambda exc: self._providers_updated(None))

    def _providers_updated(self, result):
        t = self._tr.t
        self.providers_card.set_busy(False)
        if result is None:
            self.providers_card.show_result(t("settings.provider_update_failed"), False)
        elif result.ok:
            self.providers_card.show_result(t("settings.provider_update_ok"), True)
        else:
            key = {"frozen": "settings.provider_update_frozen", "timeout": "settings.provider_update_timeout"}.get(result.code, "settings.provider_update_failed")
            self.providers_card.show_result(t(key), False)
        self.providers_card.refresh_versions()

    def _need_library(self):
        if not self.library.ready:
            self.maintenance_card.show_status(self._tr.t("maint.no_storage"), False)
            return False
        return True

    def _open_space_dialog(self):
        if self._need_library():
            SpaceDialog(self._tr, self.maintenance, self.library, self._ffmpeg_tools, self.open_saved_video, self).exec()

    def _open_backup_dialog(self):
        if self._need_library():
            BackupDialog(self._tr, self.backups, self).exec()

    def _verify_files(self):
        if not self._need_library():
            return
        run_async(self.maintenance.verify_all, lambda c: self.maintenance_card.show_status(
            self._tr.t("maint.verified", downloaded=c["downloaded"], problems=c["missing"] + c["invalid"]), True),
            lambda exc: self.maintenance_card.show_status(describe_error(self._tr, getattr(exc, "code", "")), False))

    def _refresh_metadata(self):
        if not self._need_library():
            return
        progress = self.maintenance_progress.emit
        run_async(lambda: self.maintenance.refresh_metadata(progress=progress), lambda r: self.maintenance_card.show_status(
            self._tr.t("maint.refreshed", updated=r.updated, failed=len(r.failed)), not r.failed),
            lambda exc: self.maintenance_card.show_status(describe_error(self._tr, getattr(exc, "code", "")), False))

    def _clear_thumbnails(self):
        if self._need_library():
            count, size = self.maintenance.clear_thumbnail_cache()
            from app.services.storage_service import format_bytes

            self.maintenance_card.show_status(self._tr.t("maint.thumbs_cleared", count=count, size=format_bytes(size)), True)

    def _export_diagnostics(self):
        target, _ = QFileDialog.getSaveFileName(self, self._tr.t("settings.diagnostics"), "dinotube-diagnostico.txt", "Texto (*.txt)")
        if not target:
            return
        try:
            tools = self._ffmpeg_tools()
        except Exception:
            tools = None
        from pathlib import Path

        Path(target).write_text(build_report(self._settings, self._storage, self.library, tools, self.providers), encoding="utf-8")
        self.maintenance_card.show_status(self._tr.t("maint.diagnostics_saved", name=Path(target).name), True)

    def _open_logs(self):
        if self._need_library():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self._storage.layout.logs)))

    def _after_storage_ready(self):
        """Com a biblioteca configurada: logs na pasta dela e informações de ferramentas atualizadas."""
        if self._storage.status() == STATUS_READY:
            setup_logging(self._storage.layout.logs)
            get_logger("app").info("Biblioteca em uso: modo %s", self._storage.config.mode)

    # -- busca e organização --------------------------------------------------------------------
    def _on_pin_toggled(self, on):
        self._settings.compact_on_top = on
        self.layouts.set_keep_on_top(on)

    def _paste_link(self):
        """Abre o vídeo cujo link está na área de transferência (a janela compacta não tem campo de link)."""
        from app.domain.urls import extract_video_id

        text = QApplication.clipboard().text().strip()
        video_id = extract_video_id(text) if text else None
        if video_id is None:
            self.notify(self._tr.t("compact.paste_empty"), True)
            return
        self._on_video_requested(video_id)

    def _on_search_typed(self, text):
        self._search_text = text
        self._search_timer.start()

    def _apply_search(self):
        """A busca (da barra superior ou da navegação do topo) filtra a biblioteca, com debounce, e leva o usuário até ela."""
        text = self._search_text
        self.query_state.set_text(text)
        if text.strip() and self.current_page != "library":
            self.show_page("library")

    def _sync_search_field(self):
        text = self.query_state.query.text
        for field in (self.top_bar.search_input, self.top_nav.search_input):
            if field.text() != text:
                field.blockSignals(True)
                field.setText(text)
                field.blockSignals(False)
        self._search_text = text

    def notify(self, text, error=False):
        """Mensagem curta para o usuário, na barra que o layout atual mostra (todas recebem; só as visíveis aparecem)."""
        self.top_bar.show_message(text, error)
        self.top_nav.show_message(text, error)
        self.compact_bar.show_message(text, error)
        status = getattr(self, "status_bar", None)
        if status is not None:
            status.show_message(text, error)

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
        self.notify(self._tr.t("bulk.categories_toast" if kind == "categories" else "bulk.playlist_toast"), False)

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
        self.schedule_status_refresh()

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
        elif action == "queue_add":
            self._queue_add([video_id])
        elif action == "queue_next":
            self._queue_add([video_id], play_next=True)
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
            self._after_storage_ready()
            self.downloads.cleanup_orphans()
            run_async(self.library.validate_all)
            run_async(self.backups.auto_backup_if_due)  # no máximo um backup automático por dia
        self.refresh_ffmpeg_status()

    def _on_language(self, code):
        self._settings.language = code
        self._tr.set_language(code)
        self.retranslate()

    @property
    def settings(self):
        return self._settings

    def _on_layout(self, key):
        if key == "compact" and self._settings.layout != "compact":
            self._settings.layout_before_compact = self._settings.layout  # para o botão 'Janela completa'
        self._settings.layout = key
        self.layouts.apply(key, go_landing=True)

    def show_landing(self, key):
        """Página inicial do layout. 'watch' sem vídeo aberto mostra a tela do vídeo vazia (estação e compacto)."""
        if key == "watch":
            self.watch_page.show_empty()
        self.show_page(key)

    def _on_theme(self, name):
        self._settings.theme = name
        self.settings_page.set_theme(name)
        self._theme.apply(name)


    def _apply_tokens(self):
        tokens = self._theme.tokens
        self.backdrop.set_tokens(tokens)
        self.sidebar.set_tokens(tokens)
        self.compact_bar.set_tokens(tokens)
        self.top_bar.set_tokens(tokens)
        self.top_nav.set_tokens(tokens)
        self.nav_tree.set_tokens(tokens)
        self.settings_button.setIcon(icon("settings", tokens["text_secondary"]))
        for page in self.pages.values():
            page.set_tokens(tokens)

    def _build_nav_menu(self):
        """Menu do botão ☰ da barra superior (layout Compacto, que não tem sidebar)."""
        from PySide6.QtWidgets import QMenu

        t = self._tr.t
        menu = QMenu(self.compact_bar.menu_button)
        for key in NAV_ITEMS:
            menu.addAction(t(f"nav.{key}")).triggered.connect(lambda _=False, k=key: self.show_page(k))
        menu.addSeparator()
        menu.addAction(t("queue.title")).triggered.connect(lambda: self.show_landing("watch") if self.watch_page.player.video is None else self.show_page("watch"))
        menu.addAction(t("nav.settings")).triggered.connect(lambda: self.show_page("settings"))
        self.compact_bar.menu_button.setMenu(menu)

    def retranslate(self):
        self._build_nav_menu()
        label = self._tr.t("nav.settings")
        self.settings_button.setToolTip(f"{label} (Ctrl+,)")
        self.settings_button.setAccessibleName(label)
        self.sidebar.refresh()
        self.top_bar.retranslate()
        self.compact_bar.retranslate()
        self.top_nav.retranslate()
        self.nav_tree.retranslate()
        for page in self.pages.values():
            page.retranslate()
        self.schedule_status_refresh()
