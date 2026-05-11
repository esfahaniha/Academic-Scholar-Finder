#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import sqlite3
import math
import ast
import os
from typing import Tuple, List

import pandas as pd
from PySide6.QtCore import Qt, QLocale
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QPushButton, QTableView, QSpinBox, QFileDialog, QLineEdit, QStackedWidget,
    QDoubleSpinBox, QGridLayout, QStatusBar, QAbstractItemView, QMessageBox
)
from PySide6.QtGui import QStandardItemModel, QStandardItem

# ---------- Config ----------
APP_TITLE = "Academic Scholar Finder (SQLite, Lazy Loading) - Fixed"
DB_FILE = "scholars.db"
CSV_FILE = "data.csv"
DEFAULT_PAGE_SIZE = 20

# Columns used (use the exact names from your CSV / DB)
DISPLAY_COLUMNS = [
    "scholar_id", "name", "affiliation", "Country", "Institution",
    "citedby", "Country Ranking", "World Rank", "interests", "email_domain"
]
NUMERIC_COLUMNS = ["citedby", "Country Ranking", "World Rank"]


# ---------- Database helpers ----------
def prepare_database(db_path: str = DB_FILE, csv_path: str = CSV_FILE):
    """Create DB and import CSV if empty. Create indexes for performance."""
    need_import = False
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # create table if not exists
    cur.execute("""
    CREATE TABLE IF NOT EXISTS scholars (
        scholar_id TEXT,
        url_picture TEXT,
        name TEXT,
        affiliation TEXT,
        email_domain TEXT,
        interests TEXT,
        citedby INTEGER,
        [Country Ranking] INTEGER,
        [World Rank] INTEGER,
        Country TEXT,
        Institution TEXT
    )
    """)
    conn.commit()

    # check if table empty
    cur.execute("SELECT COUNT(1) FROM scholars")
    count = cur.fetchone()[0]
    if count == 0:
        need_import = True

    if need_import:
        if not os.path.exists(csv_path):
            conn.close()
            raise FileNotFoundError(f"CSV file not found: {csv_path}")
        print("Importing CSV into SQLite (first-run). This may take a while for large CSV...")
        # read in chunks to avoid memory spike
        chunksize = 200_000
        for i, chunk in enumerate(pd.read_csv(csv_path, chunksize=chunksize)):
            # ensure interests is string
            if "interests" in chunk.columns:
                chunk["interests"] = chunk["interests"].fillna("").astype(str)
            chunk.to_sql("scholars", conn, if_exists="append", index=False)
            print(f"Imported chunk {i+1}, rows total so far: {i*chunksize + len(chunk)}")
        # create indexes
        print("Creating indexes...")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_country ON scholars(Country)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_institution ON scholars(Institution)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_interests ON scholars(interests)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_citedby ON scholars(citedby)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_worldrank ON scholars([World Rank])")
        conn.commit()
        print("Import complete.")
    conn.close()


def safe_bracket(col_name: str) -> str:
    """Return column name wrapped in brackets for safe SQL (handles spaces)."""
    # If already has brackets, return as-is
    if not col_name:
        return col_name
    col = col_name.strip()
    if col.startswith("[") and col.endswith("]"):
        return col
    return f"[{col}]"


def build_where_clause(
    mode: str,
    option_value: str,
    quick_text: str,
    numeric_col: str,
    numeric_mode: str,
    vmin: float,
    vmax: float
) -> Tuple[str, List]:
    """
    Build SQL WHERE clause and parameters (use parameterized queries to avoid injection).
    Returns (clause, params)
    """
    clauses = []
    params: List = []

    # quick text search on name or affiliation
    if quick_text:
        clauses.append("(LOWER(name) LIKE ? OR LOWER(affiliation) LIKE ?)")
        qt = f"%{quick_text.lower()}%"
        params.extend([qt, qt])

    # mode-based filtering
    if mode in ("کشور", "دانشگاه", "فیلد کاری"):
        if option_value:
            if mode == "کشور":
                clauses.append("Country = ?")
                params.append(option_value)
            elif mode == "دانشگاه":
                clauses.append("Institution = ?")
                params.append(option_value)
            else:
                # interests stored as text; use LIKE for containment
                clauses.append("interests LIKE ?")
                params.append(f"%{option_value}%")
    else:
        # numeric filters: use bracketed column name
        col = numeric_col
        if col and col in NUMERIC_COLUMNS:
            col_sql = safe_bracket(col)
            if numeric_mode == ">=":
                clauses.append(f"COALESCE(CAST({col_sql} AS REAL), -1e18) >= ?")
                params.append(vmin)
            elif numeric_mode == "<=":
                clauses.append(f"COALESCE(CAST({col_sql} AS REAL), 1e18) <= ?")
                params.append(vmin)
            elif numeric_mode == "بین":
                clauses.append(f"(COALESCE(CAST({col_sql} AS REAL), -1e18) >= ? AND COALESCE(CAST({col_sql} AS REAL), 1e18) <= ?)")
                params.extend([vmin, vmax])

    if clauses:
        return "WHERE " + " AND ".join(clauses), params
    else:
        return "", []


# ---------- UI ----------
class ScholarFinderUI(QWidget):
    def __init__(self, db_path: str = DB_FILE):
        super().__init__()
        self.setWindowTitle(APP_TITLE)
        self.setLayoutDirection(Qt.RightToLeft)
        self.resize(1200, 720)

        # DB
        self.db_path = db_path
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()

        # UI state
        self.current_page = 1
        self.page_size = DEFAULT_PAGE_SIZE

        # cached category lists (load once from DB)
        self._load_categories()

        # --- Layout ---
        main_layout = QVBoxLayout(self)
        top_bar = QGridLayout()
        main_layout.addLayout(top_bar)

        # Search Mode
        top_bar.addWidget(QLabel("جستجو بر اساس:"), 0, 0)
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["کشور", "دانشگاه", "فیلد کاری", "تعداد ارجاعات", "World Rank", "Country Ranking"])
        self.mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        top_bar.addWidget(self.mode_combo, 0, 1)

        # Dynamic area
        self.dynamic_area = QStackedWidget()
        # category widget
        self.option_combo = QComboBox()
        cat_widget = QWidget()
        cat_layout = QHBoxLayout(cat_widget)
        cat_layout.setContentsMargins(0,0,0,0)
        cat_layout.addWidget(QLabel("گزینه:"))
        cat_layout.addWidget(self.option_combo)
        self.dynamic_area.addWidget(cat_widget)

        # numeric widget
        num_widget = QWidget()
        num_layout = QHBoxLayout(num_widget)
        num_layout.setContentsMargins(0,0,0,0)
        self.numeric_col_label = QLabel("ستون:")
        self.numeric_mode = QComboBox()
        self.numeric_mode.addItems([">=", "<=", "بین"])
        self.num_min = QDoubleSpinBox(); self.num_min.setMaximum(1e12); self.num_min.setDecimals(0)
        self.num_max = QDoubleSpinBox(); self.num_max.setMaximum(1e12); self.num_max.setDecimals(0); self.num_max.setEnabled(False)
        self.numeric_mode.currentIndexChanged.connect(self._on_numeric_mode_changed)
        num_layout.addWidget(self.numeric_col_label)
        num_layout.addWidget(self.numeric_mode)
        num_layout.addWidget(QLabel("از:")); num_layout.addWidget(self.num_min)
        num_layout.addWidget(QLabel("تا:")); num_layout.addWidget(self.num_max)
        self.dynamic_area.addWidget(num_widget)

        top_bar.addWidget(self.dynamic_area, 0, 2, 1, 6)

        # page size + search/reset
        top_bar.addWidget(QLabel("تعداد در هر صفحه:"), 1, 0)
        self.page_size_spin = QSpinBox(); self.page_size_spin.setRange(5, 1000); self.page_size_spin.setValue(self.page_size)
        top_bar.addWidget(self.page_size_spin, 1, 1)
        self.search_btn = QPushButton("جستجو"); self.search_btn.clicked.connect(self.on_search_clicked)
        top_bar.addWidget(self.search_btn, 1, 2)
        self.reset_btn = QPushButton("بازنشانی"); self.reset_btn.clicked.connect(self.reset_filters)
        top_bar.addWidget(self.reset_btn, 1, 3)

        # quick search
        top_bar.addWidget(QLabel("جستجوی سریع (نام/افیلییشن):"), 1, 4)
        self.quick_search = QLineEdit(); self.quick_search.setPlaceholderText("عبارتی از نام یا affiliation...")
        self.quick_search.returnPressed.connect(self.on_search_clicked)
        top_bar.addWidget(self.quick_search, 1, 5, 1, 3)

        # Table (use QStandardItemModel for small page size)
        self.table = QTableView()
        self.table_model = QStandardItemModel(0, len(DISPLAY_COLUMNS))
        self.table.setModel(self.table_model)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSortingEnabled(True)
        self.table.horizontalHeader().setStretchLastSection(True)
        main_layout.addWidget(self.table)

        # pagination controls
        pagelayout = QHBoxLayout()
        self.prev_btn = QPushButton("قبلی"); self.prev_btn.clicked.connect(self.prev_page)
        self.next_btn = QPushButton("بعدی"); self.next_btn.clicked.connect(self.next_page)
        self.page_label = QLabel("صفحه 1/1")
        pagelayout.addWidget(self.prev_btn); pagelayout.addWidget(self.next_btn)
        pagelayout.addStretch(1); pagelayout.addWidget(self.page_label)
        main_layout.addLayout(pagelayout)

        # status + export
        self.status = QStatusBar(); main_layout.addWidget(self.status)
        self.export_btn = QPushButton("خروجی CSV از نتایج"); self.export_btn.clicked.connect(self.export_results)
        main_layout.addWidget(self.export_btn)

        # init dynamic controls and load first page
        self._on_mode_changed()
        self.on_search_clicked()

    def _load_categories(self):
        # load distinct lists for countries, institutions and interests (limited unique)
        cur = self.conn.cursor()
        cur.execute("SELECT DISTINCT Country FROM scholars WHERE Country IS NOT NULL AND Country <> ''")
        self.countries = sorted([r[0] for r in cur.fetchall() if r[0]])
        cur.execute("SELECT DISTINCT Institution FROM scholars WHERE Institution IS NOT NULL AND Institution <> ''")
        self.institutions = sorted([r[0] for r in cur.fetchall() if r[0]])
        # interests: we stored as text (e.g. "['AI','ML']"); parse some distinct values
        cur.execute("SELECT DISTINCT interests FROM scholars WHERE interests IS NOT NULL AND interests <> '' LIMIT 10000")
        fldset = set()
        for (val,) in cur.fetchall():
            try:
                lst = ast.literal_eval(val) if isinstance(val, str) and val.startswith("[") else [v.strip() for v in str(val).split(",") if v.strip()]
                for it in lst:
                    if isinstance(it, str) and it.strip():
                        fldset.add(it.strip())
            except Exception:
                for it in str(val).split(","):
                    if it.strip(): fldset.add(it.strip())
        self.fields = sorted(fldset)

    def _on_mode_changed(self):
        mode = self.mode_combo.currentText()
        if mode in ["کشور", "دانشگاه", "فیلد کاری"]:
            self.dynamic_area.setCurrentIndex(0)
            self.option_combo.clear()
            if mode == "کشور":
                self.option_combo.addItems(self.countries)
            elif mode == "دانشگاه":
                self.option_combo.addItems(self.institutions)
            else:
                self.option_combo.addItems(self.fields)
        else:
            self.dynamic_area.setCurrentIndex(1)
            # numeric_col_label text must match exactly one of NUMERIC_COLUMNS
            if mode == "تعداد ارجاعات":
                self.numeric_col_label.setText("citedby")
            elif mode == "World Rank":
                self.numeric_col_label.setText("World Rank")
            else:
                self.numeric_col_label.setText("Country Ranking")

    def _on_numeric_mode_changed(self):
        self.num_max.setEnabled(self.numeric_mode.currentText() == "بین")

    # ---------- Query / Load ----------
    def on_search_clicked(self):
        # reset to first page and apply page size
        try:
            self.page_size = int(self.page_size_spin.value())
        except Exception:
            self.page_size = DEFAULT_PAGE_SIZE
        self.current_page = 1
        self.load_page()

    def build_query(self) -> Tuple[str, List]:
        mode = self.mode_combo.currentText()
        option_value = self.option_combo.currentText().strip() if mode in ["کشور","دانشگاه","فیلد کاری"] else ""
        quick_text = self.quick_search.text().strip()
        numeric_col = self.numeric_col_label.text() if self.dynamic_area.currentIndex()==1 else ""
        numeric_mode = self.numeric_mode.currentText()
        vmin = float(self.num_min.value()) if self.num_min.value() is not None else 0
        vmax = float(self.num_max.value()) if self.num_max.value() is not None else 0

        where_clause, params = build_where_clause(mode, option_value, quick_text, numeric_col, numeric_mode, vmin, vmax)
        # order by most cited by default — bracket the column names
        order_clause = f"ORDER BY COALESCE({safe_bracket('citedby')}, 0) DESC"
        # build SELECT with bracketed column names
        select_cols = ", ".join([safe_bracket(c) for c in DISPLAY_COLUMNS])
        limit_clause = f"LIMIT ? OFFSET ?"
        sql = f"SELECT {select_cols} FROM scholars {where_clause} {order_clause} {limit_clause}"
        return sql, params

    def get_total_count(self) -> int:
        mode = self.mode_combo.currentText()
        option_value = self.option_combo.currentText().strip() if mode in ["کشور","دانشگاه","فیلد کاری"] else ""
        quick_text = self.quick_search.text().strip()
        numeric_col = self.numeric_col_label.text() if self.dynamic_area.currentIndex()==1 else ""
        numeric_mode = self.numeric_mode.currentText()
        vmin = float(self.num_min.value()) if self.num_min.value() is not None else 0
        vmax = float(self.num_max.value()) if self.num_max.value() is not None else 0

        where_clause, params = build_where_clause(mode, option_value, quick_text, numeric_col, numeric_mode, vmin, vmax)
        q = f"SELECT COUNT(1) FROM scholars {where_clause}"
        cur = self.conn.cursor()
        cur.execute(q, params)
        return cur.fetchone()[0]

    def load_page(self):
        try:
            sql_base, params = self.build_query()
            offset = (self.current_page - 1) * self.page_size
            exec_params = params + [self.page_size, offset]
            cur = self.conn.cursor()
            cur.execute(sql_base, exec_params)
            rows = cur.fetchall()

            # populate QStandardItemModel
            self.table_model.clear()
            self.table_model.setHorizontalHeaderLabels([c for c in DISPLAY_COLUMNS])
            for r in rows:
                items = []
                for col in DISPLAY_COLUMNS:
                    # Row is sqlite3.Row so accessible by key (with original column name)
                    v = r[col] if (col in r.keys()) else ""
                    items.append(QStandardItem("" if v is None else str(v)))
                self.table_model.appendRow(items)

            total = self.get_total_count()
            page_count = max(1, math.ceil(total / self.page_size)) if total else 1
            self.page_label.setText(f"صفحه {self.current_page}/{page_count}  |  نتایج: {total}")
            self.prev_btn.setEnabled(self.current_page > 1)
            self.next_btn.setEnabled(self.current_page < page_count)
            self.status.showMessage(f"حجم کلی دیتابیس: {self._db_row_count()}  |  نتایج فیلتر شده: {total}")
        except Exception as e:
            QMessageBox.critical(self, "خطا در بارگذاری", f"{e}")

    def _db_row_count(self) -> int:
        cur = self.conn.cursor()
        cur.execute("SELECT COUNT(1) FROM scholars")
        return cur.fetchone()[0]

    # ---------- Pagination ----------
    def next_page(self):
        total = self.get_total_count()
        page_count = max(1, math.ceil(total / self.page_size)) if total else 1
        if self.current_page < page_count:
            self.current_page += 1
            self.load_page()

    def prev_page(self):
        if self.current_page > 1:
            self.current_page -= 1
            self.load_page()

    # ---------- reset / export ----------
    def reset_filters(self):
        self.quick_search.clear()
        if self.option_combo.count() > 0:
            self.option_combo.setCurrentIndex(0)
        self.numeric_mode.setCurrentIndex(0)
        self.num_min.setValue(0)
        self.num_max.setValue(0)
        self.page_size_spin.setValue(DEFAULT_PAGE_SIZE)
        self.current_page = 1
        self.load_page()

    def export_results(self):
        # export ALL filtered results (not only page) into CSV
        mode = self.mode_combo.currentText()
        option_value = self.option_combo.currentText().strip() if mode in ["کشور","دانشگاه","فیلد کاری"] else ""
        quick_text = self.quick_search.text().strip()
        numeric_col = self.numeric_col_label.text() if self.dynamic_area.currentIndex()==1 else ""
        numeric_mode = self.numeric_mode.currentText()
        vmin = float(self.num_min.value()) if self.num_min.value() is not None else 0
        vmax = float(self.num_max.value()) if self.num_max.value() is not None else 0

        where_clause, params = build_where_clause(mode, option_value, quick_text, numeric_col, numeric_mode, vmin, vmax)
        select_cols = ", ".join([safe_bracket(c) for c in DISPLAY_COLUMNS])
        q = f"SELECT {select_cols} FROM scholars {where_clause} ORDER BY COALESCE({safe_bracket('citedby')},0) DESC"
        try:
            df = pd.read_sql_query(q, self.conn, params=params)
        except Exception as e:
            QMessageBox.critical(self, "خطا", f"خطا در گرفتن نتایج: {e}")
            return

        path, _ = QFileDialog.getSaveFileName(self, "ذخیره نتایج به CSV", "results.csv", "CSV Files (*.csv)")
        if not path:
            return
        try:
            df.to_csv(path, index=False)
            QMessageBox.information(self, "تمام شد", f"نتایج در '{path}' ذخیره شد.")
        except Exception as e:
            QMessageBox.critical(self, "خطا", f"خطا در ذخیره‌سازی: {e}")

    def closeEvent(self, event):
        try:
            self.conn.close()
        except:
            pass
        event.accept()


# ---------- main ----------
def main():
    # prepare DB (import CSV only if DB empty)
    try:
        prepare_database(DB_FILE, CSV_FILE)
    except FileNotFoundError as e:
        print(e)
        return

    app = QApplication(sys.argv)
    QLocale.setDefault(QLocale(QLocale.Persian, QLocale.Iran))
    w = ScholarFinderUI(DB_FILE)
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
