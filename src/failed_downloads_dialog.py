"""Non-blocking dialog for reviewing, retrying, and deleting failed downloads."""

import webbrowser

from PyQt6.QtCore import QPoint, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMenu,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .logging_utils import log_exception
from .ydl_options import get_source_options

_COLUMNS = ("Failed At", "Site", "Type", "Title")
_RECORD_ROLE = Qt.ItemDataRole.UserRole + 1
_UNKNOWN_SOURCE_TOOLTIP = "Unknown source type — cannot rebuild download options"


class FailedDownloadsDialog(QDialog):
    """
    Non-blocking dialog listing failed downloads.

    The dialog is deliberately dumb: it renders whatever records it is handed and
    emits intent signals. All store mutation is owned by MyWindow, which pushes
    refreshed record lists back via set_records().
    """

    retry_requested = pyqtSignal(dict)  # full record
    delete_requested = pyqtSignal(str)  # record key

    def __init__(self, records: list[dict], parent: QWidget | None = None) -> None:
        """Build the dialog layout and populate it with the given records."""
        super().__init__(parent)
        self.setWindowTitle("Failed Downloads")
        self.resize(900, 400)
        self.setModal(False)

        self._records: list[dict] = []

        layout = QVBoxLayout()
        self._table = self._build_table()
        layout.addWidget(self._table)
        layout.addLayout(self._build_button_row())
        self.setLayout(layout)

        self.set_records(records)

    def _build_table(self) -> QTableWidget:
        table = QTableWidget(0, len(_COLUMNS))
        table.setHorizontalHeaderLabels(_COLUMNS)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.setAlternatingRowColors(True)
        table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        table.customContextMenuRequested.connect(self._show_context_menu)
        table.itemSelectionChanged.connect(self._on_selection_changed)

        header = table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)

        return table

    def _build_button_row(self) -> QHBoxLayout:
        row = QHBoxLayout()

        self._retry_btn = QPushButton("Retry")
        self._retry_btn.setEnabled(False)
        self._retry_btn.clicked.connect(self._retry_selected)
        row.addWidget(self._retry_btn)

        self._delete_btn = QPushButton("Delete")
        self._delete_btn.setEnabled(False)
        self._delete_btn.clicked.connect(self._delete_selected)
        row.addWidget(self._delete_btn)

        row.addStretch()

        self._count_label = QLabel()
        row.addWidget(self._count_label)

        return row

    def set_records(self, records: list[dict]) -> None:
        """Replace the table contents with the given records (newest-first)."""
        self._records = records
        self._table.setRowCount(len(records))

        for row, record in enumerate(records):
            values = (
                record.get("failed_at", ""),
                record.get("site", ""),
                record.get("source", ""),
                record.get("title", ""),
            )
            error = record.get("error", "")
            for col, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                # The error string is the only place the user learns *why* it
                # failed; put it on every cell so any hover reveals it.
                item.setToolTip(error)
                if col == 0:
                    item.setData(_RECORD_ROLE, record)
                self._table.setItem(row, col, item)

        self._count_label.setText(f"{len(records)} failed download(s)")
        self._on_selection_changed()

    def _selected_record(self) -> dict | None:
        row = self._table.currentRow()
        if row < 0:
            return None
        item = self._table.item(row, 0)
        if item is None:
            return None
        return item.data(_RECORD_ROLE)  # type: ignore[return-value]

    def _can_retry(self, record: dict | None) -> bool:
        # Records come from a user-editable JSON file on disk, so a malformed or
        # old-schema entry must never reach get_source_options: an exception
        # escaping a Qt slot aborts the interpreter rather than being catchable.
        if not record:
            return False
        source = record.get("source")
        if not isinstance(source, str) or not source:
            return False
        try:
            return bool(get_source_options(source))
        except (TypeError, ValueError, OSError) as exc:
            log_exception(exc, f"Cannot rebuild download options for source {source!r}")
            return False

    def _can_delete(self, record: dict | None) -> bool:
        return bool(record) and bool(record.get("key"))  # type: ignore[union-attr]

    def _on_selection_changed(self) -> None:
        record = self._selected_record()
        can_retry = self._can_retry(record)
        self._delete_btn.setEnabled(self._can_delete(record))
        self._retry_btn.setEnabled(can_retry)
        self._retry_btn.setToolTip("" if can_retry else _UNKNOWN_SOURCE_TOOLTIP)

    def _retry_selected(self) -> None:
        record = self._selected_record()
        if record is not None:
            self.retry_requested.emit(record)

    def _delete_selected(self) -> None:
        record = self._selected_record()
        key = record.get("key") if record else None
        if key:
            self.delete_requested.emit(key)

    def _show_context_menu(self, pos: QPoint) -> None:
        record = self._selected_record()
        urls = record.get("urls") if record else None
        can_retry = self._can_retry(record)

        menu = QMenu(self)

        retry_action = menu.addAction("Retry")
        retry_action.setEnabled(can_retry)
        if can_retry:
            retry_action.triggered.connect(self._retry_selected)
        else:
            retry_action.setToolTip(_UNKNOWN_SOURCE_TOOLTIP)

        delete_action = menu.addAction("Delete")
        delete_action.setEnabled(self._can_delete(record))
        if self._can_delete(record):
            delete_action.triggered.connect(self._delete_selected)

        open_action = menu.addAction("Open in Browser")
        open_action.setEnabled(bool(urls))
        if urls:
            open_action.triggered.connect(lambda: webbrowser.open_new_tab(urls[0]))

        menu.exec(self._table.viewport().mapToGlobal(pos))
