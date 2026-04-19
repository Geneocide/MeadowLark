"""Non-blocking dialog for browsing download history."""

import webbrowser

from PyQt6.QtCore import QPoint, Qt
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMenu,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from QYT import parse_history_log

_COLUMNS = ("Datetime", "Site", "Type", "Title", "Result")
_RESULT_OPTIONS = ("All", "SUCCESS", "FAIL", "SKIPPED")
_NO_URL_TOOLTIP = "URL not available for older log entries"


class HistoryDialog(QDialog):
    """Non-blocking dialog showing download history in a table."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Load history and build the dialog layout."""
        super().__init__(parent)
        self.setWindowTitle("Download History")
        self.resize(900, 500)
        self.setModal(False)

        self._all_records = parse_history_log()

        layout = QVBoxLayout()

        if not self._all_records:
            layout.addWidget(QLabel("No download history found."))
        else:
            layout.addLayout(self._build_filter_bar())
            self._table = self._build_table()
            layout.addWidget(self._table)
            self._count_label = QLabel()
            layout.addWidget(self._count_label)
            self._apply_filters()

        self.setLayout(layout)

    def _build_filter_bar(self) -> QHBoxLayout:
        bar = QHBoxLayout()

        self._search = QLineEdit()
        self._search.setPlaceholderText("Search title…")
        self._search.textChanged.connect(self._apply_filters)
        bar.addWidget(self._search)

        sites = sorted({r["site"] for r in self._all_records})
        types = sorted({r["dtype"] for r in self._all_records})

        bar.addWidget(QLabel("Site:"))
        self._site_combo = self._make_combo(["All", *sites])
        bar.addWidget(self._site_combo)

        bar.addWidget(QLabel("Type:"))
        self._type_combo = self._make_combo(["All", *types])
        bar.addWidget(self._type_combo)

        bar.addWidget(QLabel("Result:"))
        self._result_combo = self._make_combo(list(_RESULT_OPTIONS))
        bar.addWidget(self._result_combo)

        self._open_btn = QPushButton("Open in Browser")
        self._open_btn.setEnabled(False)
        self._open_btn.setToolTip(_NO_URL_TOOLTIP)
        self._open_btn.clicked.connect(self._open_selected)
        bar.addWidget(self._open_btn)

        return bar

    def _make_combo(self, items: list[str]) -> QComboBox:
        combo = QComboBox()
        combo.addItems(items)
        combo.currentTextChanged.connect(self._apply_filters)
        return combo

    def _build_table(self) -> QTableWidget:
        table = QTableWidget(len(self._all_records), len(_COLUMNS))
        table.setHorizontalHeaderLabels(_COLUMNS)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.setAlternatingRowColors(True)
        table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        table.customContextMenuRequested.connect(self._show_context_menu)
        table.itemSelectionChanged.connect(self._on_selection_changed)

        for row, entry in enumerate(self._all_records):
            table.setItem(row, 0, QTableWidgetItem(entry["dt"]))
            table.setItem(row, 1, QTableWidgetItem(entry["site"]))
            table.setItem(row, 2, QTableWidgetItem(entry["dtype"]))

            title_item = QTableWidgetItem(entry["title"])
            title_item.setData(Qt.ItemDataRole.UserRole, entry["url"])
            table.setItem(row, 3, title_item)

            table.setItem(row, 4, QTableWidgetItem(entry["result"]))

        header = table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)

        return table

    def _get_selected_url(self) -> str | None:
        row = self._table.currentRow()
        if row < 0 or self._table.isRowHidden(row):
            return None
        title_item = self._table.item(row, 3)
        if title_item is None:
            return None
        return title_item.data(Qt.ItemDataRole.UserRole)  # type: ignore[return-value]

    def _on_selection_changed(self) -> None:
        url = self._get_selected_url()
        self._open_btn.setEnabled(bool(url))
        self._open_btn.setToolTip("" if url else _NO_URL_TOOLTIP)

    def _open_selected(self) -> None:
        url = self._get_selected_url()
        if url:
            webbrowser.open_new_tab(url)

    def _show_context_menu(self, pos: QPoint) -> None:
        url = self._get_selected_url()
        menu = QMenu(self)
        action = menu.addAction("Open in Browser")
        action.setEnabled(bool(url))
        if not url:
            action.setToolTip(_NO_URL_TOOLTIP)
        if url:
            action.triggered.connect(lambda: webbrowser.open_new_tab(url))
        menu.exec(self._table.viewport().mapToGlobal(pos))

    def _apply_filters(self) -> None:
        title_q = self._search.text().lower()
        site_f = self._site_combo.currentText()
        type_f = self._type_combo.currentText()
        result_f = self._result_combo.currentText()

        visible = 0
        for row, entry in enumerate(self._all_records):
            show = (
                (not title_q or title_q in entry["title"].lower())
                and (site_f == "All" or entry["site"] == site_f)
                and (type_f == "All" or entry["dtype"] == type_f)
                and _result_matches(entry["result"], result_f)
            )
            if show:
                self._table.showRow(row)
                visible += 1
            else:
                self._table.hideRow(row)

        self._count_label.setText(f"{visible} of {len(self._all_records)} records")
        self._on_selection_changed()


def _result_matches(result: str, filter_val: str) -> bool:
    """Return True if result string satisfies the chosen filter option."""
    if filter_val == "All":
        return True
    if filter_val == "SKIPPED":
        return result.startswith("SKIPPED")
    return result == filter_val
