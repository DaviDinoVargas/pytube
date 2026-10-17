from PySide6.QtWidgets import QMenu


class OrganizeMenus:
    """Menus de categorias (marcáveis) e de playlists, usados nos cards, na tela do vídeo e nas ações em lote."""

    def __init__(self, translator, org, new_category, new_playlist, on_change=None):
        self._tr = translator
        self._org = org
        self._new_category = new_category  # callable() -> Category | None  (abre o diálogo)
        self._new_playlist = new_playlist
        self._on_change = on_change or (lambda kind: None)

    def categories_menu(self, video_ids, parent=None):
        t = self._tr.t
        menu = QMenu(t("card.menu_categories"), parent)
        video_ids = list(video_ids)
        current = [set(self._org.video_category_ids(v)) for v in video_ids]
        for category in self._org.categories():
            has_all = bool(current) and all(category.id in c for c in current)
            has_some = any(category.id in c for c in current)
            action = menu.addAction(category.name)
            action.setCheckable(True)
            action.setChecked(has_all)
            if has_some and not has_all:
                action.setText(f"{category.name}  ·  ◐")  # só alguns dos selecionados têm
            action.triggered.connect(lambda _=False, cid=category.id, all_=has_all: self._toggle_category(video_ids, cid, all_))
        if self._org.categories():
            menu.addSeparator()
        new = menu.addAction(t("bulk.new_category"))
        new.triggered.connect(lambda _=False: self._create_and_assign(video_ids))
        return menu

    def playlists_menu(self, video_ids, parent=None):
        t = self._tr.t
        menu = QMenu(t("card.menu_playlists"), parent)
        video_ids = list(video_ids)
        counts = self._org.playlist_counts()
        for playlist in self._org.playlists():
            action = menu.addAction(f"{playlist.name}  ({counts.get(playlist.id, 0)})")
            action.triggered.connect(lambda _=False, pid=playlist.id: self._add_to_playlist(video_ids, pid))
        if self._org.playlists():
            menu.addSeparator()
        new = menu.addAction(t("bulk.new_playlist"))
        new.triggered.connect(lambda _=False: self._create_playlist_and_add(video_ids))
        return menu

    # -- ações ----------------------------------------------------------------------------
    def _toggle_category(self, video_ids, category_id, all_have):
        if all_have:
            self._org.assign_categories(video_ids, remove=[category_id])
        else:
            self._org.assign_categories(video_ids, add=[category_id])
        self._on_change("categories")

    def _create_and_assign(self, video_ids):
        category = self._new_category()
        if category is not None:
            self._org.assign_categories(video_ids, add=[category.id])
            self._on_change("categories")

    def _add_to_playlist(self, video_ids, playlist_id):
        self._org.add_to_playlist(playlist_id, video_ids)
        self._on_change("playlist")

    def _create_playlist_and_add(self, video_ids):
        playlist = self._new_playlist()
        if playlist is not None:
            self._org.add_to_playlist(playlist.id, video_ids)
            self._on_change("playlist")
