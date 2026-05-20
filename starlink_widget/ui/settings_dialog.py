"""Dialogue de personnalisation — aperçu immédiat + glisser-déposer pour l'ordre."""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QDrag, QPixmap
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
)

from starlink_widget.core.display_fields import FIELD_BY_KEY, fields_by_category
from starlink_widget.core.widget_prefs import (
    load_field_order,
    load_visible_fields,
    save_widget_preferences,
)


class FieldOrderList(QListWidget):
    """Liste réordonnable sans fenêtre fantôme de drag."""

    order_changed = pyqtSignal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.setSpacing(2)

    def startDrag(self, supportedActions) -> None:
        drag = QDrag(self)
        empty = QPixmap(1, 1)
        empty.fill(Qt.GlobalColor.transparent)
        drag.setPixmap(empty)
        drag.exec(supportedActions)

    def dropEvent(self, event) -> None:
        super().dropEvent(event)
        self.order_changed.emit()


class SettingsDialog(QDialog):
    preferences_changed = pyqtSignal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Personnaliser le widget")
        self.setMinimumWidth(360)
        self.setMinimumHeight(480)
        self._block_persist = False
        self._build_ui()
        self._populate_list()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)

        hint = QLabel(
            "Cochez les champs à afficher. Glissez les lignes pour l'ordre.\n"
            "Avec ce menu ouvert : poignées sur les cartes (taille/largeur),\n"
            "glissez une carte pour la déplacer. Clic droit : graphique. Immédiat."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #8e8e93; font-size: 11px;")
        root.addWidget(hint)

        self._list = FieldOrderList()
        self._list.itemChanged.connect(self._on_item_changed)
        self._list.order_changed.connect(self._persist_and_notify)
        root.addWidget(self._list)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.close)
        root.addWidget(buttons)

    def refresh_list(self) -> None:
        self._populate_list()

    def _populate_list(self) -> None:
        self._block_persist = True
        self._list.clear()
        visible = load_visible_fields()
        order = load_field_order()
        labels = {f.key: f.label for cat in fields_by_category().values() for f in cat}
        for key in order:
            field = FIELD_BY_KEY.get(key)
            if field is None:
                continue
            label = labels.get(key, field.label)
            item = QListWidgetItem(f"{field.category} — {label}")
            item.setData(Qt.ItemDataRole.UserRole, key)
            item.setFlags(
                item.flags()
                | Qt.ItemFlag.ItemIsUserCheckable
                | Qt.ItemFlag.ItemIsDragEnabled
                | Qt.ItemFlag.ItemIsDropEnabled
                | Qt.ItemFlag.ItemIsEnabled
            )
            item.setCheckState(
                Qt.CheckState.Checked
                if key in visible
                else Qt.CheckState.Unchecked
            )
            self._list.addItem(item)
        self._block_persist = False

    def _on_item_changed(self, item: QListWidgetItem) -> None:
        if self._block_persist:
            return
        self._persist_and_notify()

    def _persist_and_notify(self) -> None:
        if self._block_persist:
            return
        order: list[str] = []
        visible: set[str] = set()
        for i in range(self._list.count()):
            item = self._list.item(i)
            if item is None:
                continue
            key = item.data(Qt.ItemDataRole.UserRole)
            if not key:
                continue
            order.append(str(key))
            if item.checkState() == Qt.CheckState.Checked:
                visible.add(str(key))
        save_widget_preferences(visible, order)
        self.preferences_changed.emit()
