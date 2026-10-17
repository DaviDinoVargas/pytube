from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QMenu, QMessageBox, QPushButton, QToolButton, QVBoxLayout, QWidget

from app.domain.errors import StorageError
from app.styles.icons import icon
from app.ui.errors import describe_error
from app.ui.pages.base import EmptyState, Page
from app.ui.widgets.flow_layout import FlowLayout

CARD_WIDTH = 260


class CollectionCard(QFrame):
    """Cartão de uma categoria ou playlist: nome, descrição, quantidade e menu de ações."""

    opened = Signal(int)
    edit_requested = Signal(int)
    delete_requested = Signal(int)
    play_requested = Signal(int)

    def __init__(self, translator, tokens, item_id, name, description, count_text, color=None, edit_key="", delete_key="", play=False):
        super().__init__()
        self.item_id, self.name = item_id, name
        self.setObjectName("collectionCard")
        self.setFixedWidth(CARD_WIDTH)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setCursor(Qt.PointingHandCursor)
        self.setAccessibleName(f"{name}. {count_text}")
        t = translator.t

        column = QVBoxLayout(self)
        column.setContentsMargins(14, 12, 8, 12)
        column.setSpacing(4)
        head = QHBoxLayout()
        head.setSpacing(8)
        self.dot = QLabel("●" if color else "")
        self.dot.setObjectName("collectionDot")
        if color:
            self.dot.setStyleSheet(f"QLabel#collectionDot {{ color: {color}; font-size: 16px; }}")
        self.dot.setVisible(bool(color))
        self.name_label = QLabel(name)
        self.name_label.setObjectName("cardTitle")
        self.name_label.setWordWrap(True)
        self.menu_button = QToolButton()
        self.menu_button.setObjectName("iconButton")
        self.menu_button.setIcon(icon("more", tokens["text_secondary"]))
        self.menu_button.setToolTip(t("card.more"))
        self.menu_button.setAccessibleName(t("card.more"))
        self.menu_button.setPopupMode(QToolButton.InstantPopup)
        menu = QMenu(self.menu_button)
        menu.addAction(t(edit_key)).triggered.connect(lambda _=False: self.edit_requested.emit(self.item_id))
        menu.addAction(t(delete_key)).triggered.connect(lambda _=False: self.delete_requested.emit(self.item_id))
        self.menu_button.setMenu(menu)
        head.addWidget(self.dot)
        head.addWidget(self.name_label, 1)
        head.addWidget(self.menu_button)
        column.addLayout(head)
        self.description_label = QLabel(description)
        self.description_label.setObjectName("cardMeta")
        self.description_label.setWordWrap(True)
        self.description_label.setVisible(bool(description))
        column.addWidget(self.description_label)
        self.count_label = QLabel(count_text)
        self.count_label.setObjectName("cardMeta")
        column.addWidget(self.count_label)
        self.play_button = None
        if play:
            self.play_button = QPushButton(t("playlists.play_all"))
            self.play_button.setObjectName("secondary")
            self.play_button.setCursor(Qt.PointingHandCursor)
            self.play_button.clicked.connect(lambda: self.play_requested.emit(self.item_id))
            column.addWidget(self.play_button, 0, Qt.AlignLeft)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self.rect().contains(event.position().toPoint()):
            self.opened.emit(self.item_id)
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Space):
            self.opened.emit(self.item_id)
            return
        super().keyPressEvent(event)


class CollectionPage(Page):
    """Base de Categorias e Playlists: botão de criar, cartões em fluxo e estado vazio."""

    new_key = ""
    message = Signal(str, bool)

    def __init__(self, translator, org, library, tokens, prompt):
        super().__init__(translator)
        self._org, self._library, self._tokens, self._prompt = org, library, tokens, prompt
        self._dirty = True
        self.new_button = QPushButton()
        self.new_button.setObjectName("primary")
        self.new_button.setCursor(Qt.PointingHandCursor)
        self.new_button.clicked.connect(self.create)
        top = QHBoxLayout()
        top.addStretch(1)
        top.addWidget(self.new_button)
        self.body.addLayout(top)
        self.empty = EmptyState(translator, self.key)
        self.body.addWidget(self.empty)
        self.cards_box = QWidget()
        self.flow = FlowLayout(self.cards_box, 14, 14)
        self.body.addWidget(self.cards_box)
        self.body.addStretch(1)
        self.cards = []
        self.retranslate()

    # a subclasse informa o que listar
    def items(self):
        raise NotImplementedError

    def make_card(self, item):
        raise NotImplementedError

    def mark_dirty(self):
        self._dirty = True
        if self.isVisible():
            self.refresh()

    def showEvent(self, event):
        super().showEvent(event)
        if self._dirty:
            self.refresh()

    def refresh(self):
        self._dirty = False
        for card in self.cards:
            self.flow.removeWidget(card)
            card.setParent(None)
            card.deleteLater()
        self.cards = []
        items = self.items()
        for item in items:
            card = self.make_card(item)
            self.flow.addWidget(card)
            self.cards.append(card)
        self.flow.invalidate()
        self.empty.setVisible(not items)
        self.cards_box.setVisible(bool(items))

    def create(self):
        if self._library.ready:
            self._prompt(None)

    def set_tokens(self, tokens):
        self._tokens = tokens
        self.mark_dirty()

    def retranslate(self):
        super().retranslate()
        if hasattr(self, "new_button"):
            self.new_button.setText("+  " + self._tr.t(self.new_key))
            self.empty.retranslate()
            self.mark_dirty()

    def _confirm(self, title_key, body_key, name, ok_key):
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Question)
        box.setWindowTitle(self._tr.t(title_key))
        box.setText(self._tr.t(body_key, name=name))
        ok = box.addButton(self._tr.t(ok_key), QMessageBox.AcceptRole)
        box.addButton(self._tr.t("storage.cancel"), QMessageBox.RejectRole)
        box.exec()
        return box.clickedButton() is ok

    def _fail(self, exc):
        code = exc.code if isinstance(exc, StorageError) else "unknown"
        self.message.emit(describe_error(self._tr, code), True)


def count_text(translator, count):
    return translator.t("library.count_one") if count == 1 else translator.t("library.count_many", count=count)


class CategoriesPage(CollectionPage):
    key = "categories"
    new_key = "categories.new"
    category_opened = Signal(int)

    def items(self):
        return self._org.categories()

    def make_card(self, category):
        counts = self._org.category_counts()
        card = CollectionCard(
            self._tr, self._tokens, category.id, category.name, category.description,
            count_text(self._tr, counts.get(category.id, 0)), category.color, "categories.edit", "categories.delete",
        )
        card.opened.connect(self.category_opened)
        card.edit_requested.connect(self._edit)
        card.delete_requested.connect(self._delete)
        return card

    def _edit(self, category_id):
        category = self._org.get_category(category_id)
        if category is not None:
            self._prompt(category)

    def _delete(self, category_id):
        category = self._org.get_category(category_id)
        if category is not None and self._confirm("categories.confirm_title", "categories.confirm_body", category.name, "categories.delete"):
            self._org.delete_category(category_id)
