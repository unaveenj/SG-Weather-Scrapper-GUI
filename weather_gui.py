import customtkinter as ctk
import threading
import os
import csv
import requests
from datetime import datetime
from typing import Optional

# ── Appearance ────────────────────────────────────────────────────────────────
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# ── Constants ─────────────────────────────────────────────────────────────────
BASE_URL     = "https://www.weather.gov.sg/files/dailydata/DAILYDATA_"
SCRIPT_DIR   = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR   = os.path.join(SCRIPT_DIR, "output")
CURRENT_YEAR = datetime.now().year

# NEA requires a browser-like User-Agent and a Referer from their own domain
DOWNLOAD_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Referer": "http://www.weather.gov.sg/climate-historical-daily/",
}

STATIONS: dict[str, str] = {
    "Paya Lebar":               "S06",
    "Ang Mo Kio":               "S109",
    "Macritchie Reservoir":     "S07",
    "Botanic Garden":           "S120",
    "Lower Peirce Reservoir":   "S08",
    "Bukit Panjang":            "S64",
    "Pulau Ubin":               "S106",
    "Bukit Timah":              "S90",
    "East Coast Parkway":       "S107",
    "Marina Barrage":           "S108",
    "Chai Chee":                "S61",
    "Changi":                   "S24",
    "Newton":                   "S111",
    "Choa Chu Kang (Central)":  "S114",
    "Lim Chu Kang":             "S112",
    "Choa Chu Kang (South)":    "S121",
    "Marine Parade":            "S113",
    "Choa Chu Kang (West)":     "S11",
    "Clementi":                 "S50",
    "Tuas South":               "S115",
    "Dhoby Ghaut":              "S118",
    "Pasir Panjang":            "S116",
    "Jurong Island":            "S117",
    "Jurong (West)":            "S44",
    "Nicoll Highway":           "S119",
    "Jurong Pier":              "S33",
    "Kent Ridge":               "S71",
    "Kranji Reservoir":         "S66",
    "Tengah":                   "S23",
    "Seletar":                  "S25",
    "Pasir Ris (West)":         "S29",
    "Mandai":                   "S40",
    "Serangoon":                "S36",
    "Tai Seng":                 "S43",
    "Pasir Ris (Central)":      "S94",
    "Sentosa Island":           "S60",
    "Punggol":                  "S81",
    "Queenstown":               "S77",
    "Sembawang":                "S80",
    "Tanjong Katong":           "S78",
    "Somerset (Road)":          "S79",
    "Tuas West":                "S82",
    "Toa Payoh":                "S88",
    "Tuas":                     "S89",
    "Ulu Pandan":               "S35",
    "Upper Peirce Reservoir":   "S69",
}

STATION_NAMES = sorted(STATIONS.keys())


# ── Helpers ───────────────────────────────────────────────────────────────────

def validate_date_range(
    start_year: int, start_month: int, end_year: int, end_month: int
) -> Optional[str]:
    """Return an error message string, or None if inputs are valid."""
    if not (1980 <= start_year <= CURRENT_YEAR):
        return f"Start year must be between 1980 and {CURRENT_YEAR}."
    if not (1980 <= end_year <= CURRENT_YEAR):
        return f"End year must be between 1980 and {CURRENT_YEAR}."
    if not (1 <= start_month <= 12):
        return "Start month must be between 1 and 12."
    if not (1 <= end_month <= 12):
        return "End month must be between 1 and 12."
    if (end_year, end_month) < (start_year, start_month):
        return "End date must be after or equal to start date."
    return None


def generate_links(
    start_year: int, start_month: int,
    end_year: int, end_month: int,
    selected_names: list[str],
) -> list[str]:
    links = []
    ids = [STATIONS[name] for name in selected_names if name in STATIONS]
    for year in range(start_year, end_year + 1):
        for month in range(1, 13):
            if (year, month) < (start_year, start_month):
                continue
            if (year, month) > (end_year, end_month):
                continue
            date_str = f"{year}{month:02d}"
            for sid in ids:
                links.append(f"{BASE_URL}{sid}_{date_str}.csv")
    return links


# ── Main Application ──────────────────────────────────────────────────────────

class WeatherApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("SG Weather Data Downloader")
        self.geometry("980x720")
        self.minsize(860, 620)
        self.resizable(True, True)

        self._cancel_flag = threading.Event()
        self._worker: Optional[threading.Thread] = None

        self._all_station_names = STATION_NAMES[:]   # master list for filtering
        self._selected_vars: dict[str, ctk.BooleanVar] = {
            name: ctk.BooleanVar(value=True) for name in STATION_NAMES
        }

        self._build_header()
        self._build_body()
        self._build_status_bar()

    # ── Layout builders ───────────────────────────────────────────────────────

    def _build_header(self):
        header = ctk.CTkFrame(self, fg_color=("gray85", "gray17"), corner_radius=0)
        header.pack(fill="x", padx=0, pady=0)

        ctk.CTkLabel(
            header, text="🌦  SG Weather Data Downloader",
            font=ctk.CTkFont(size=20, weight="bold"),
        ).pack(side="left", padx=20, pady=12)

        # Dark / Light toggle
        self._mode_btn = ctk.CTkButton(
            header, text="☀ Light", width=90,
            fg_color="transparent", hover_color=("gray75", "gray30"),
            command=self._toggle_mode,
        )
        self._mode_btn.pack(side="right", padx=16, pady=10)

    def _build_body(self):
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=16, pady=(8, 4))
        body.columnconfigure(0, weight=3)
        body.columnconfigure(1, weight=2)
        body.rowconfigure(0, weight=1)

        self._build_left_panel(body)
        self._build_right_panel(body)

    def _build_left_panel(self, parent):
        left = ctk.CTkFrame(parent)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        left.columnconfigure(1, weight=1)

        # ── Date range ────────────────────────────────────────────────────────
        ctk.CTkLabel(
            left, text="Date Range",
            font=ctk.CTkFont(size=14, weight="bold"),
        ).grid(row=0, column=0, columnspan=4, sticky="w", padx=16, pady=(14, 4))

        # Row labels
        for i, label in enumerate(["Start", "End"]):
            ctk.CTkLabel(left, text=label, width=40).grid(
                row=i + 1, column=0, padx=(16, 4), pady=4, sticky="w"
            )

        # Year / Month headers
        ctk.CTkLabel(left, text="Year", text_color=("gray50", "gray60")).grid(
            row=0, column=1, padx=4, pady=(14, 0), sticky="w"
        )
        ctk.CTkLabel(left, text="Month", text_color=("gray50", "gray60")).grid(
            row=0, column=2, padx=4, pady=(14, 0), sticky="w"
        )

        self._start_year  = self._date_entry(left, row=1, col=1, default=str(CURRENT_YEAR - 1))
        self._start_month = self._date_entry(left, row=1, col=2, default="1", width=70)
        self._end_year    = self._date_entry(left, row=2, col=1, default=str(CURRENT_YEAR))
        self._end_month   = self._date_entry(left, row=2, col=2, default=str(datetime.now().month), width=70)

        # ── Progress ──────────────────────────────────────────────────────────
        sep = ctk.CTkFrame(left, height=1, fg_color=("gray75", "gray35"))
        sep.grid(row=3, column=0, columnspan=4, sticky="ew", padx=16, pady=12)

        ctk.CTkLabel(
            left, text="Progress",
            font=ctk.CTkFont(size=14, weight="bold"),
        ).grid(row=4, column=0, columnspan=4, sticky="w", padx=16, pady=(0, 6))

        self._progress_bar = ctk.CTkProgressBar(left, mode="determinate")
        self._progress_bar.set(0)
        self._progress_bar.grid(row=5, column=0, columnspan=4, sticky="ew", padx=16, pady=(0, 4))

        self._progress_label = ctk.CTkLabel(left, text="0 / 0  (0%)", text_color=("gray40", "gray60"))
        self._progress_label.grid(row=6, column=0, columnspan=4, sticky="w", padx=16)

        # ── Download buttons ──────────────────────────────────────────────────
        btn_frame = ctk.CTkFrame(left, fg_color="transparent")
        btn_frame.grid(row=7, column=0, columnspan=4, sticky="ew", padx=16, pady=12)
        btn_frame.columnconfigure((0, 1), weight=1)

        self._dl_btn = ctk.CTkButton(
            btn_frame, text="⬇  Download", command=self._start_download,
            font=ctk.CTkFont(size=13, weight="bold"),
        )
        self._dl_btn.grid(row=0, column=0, sticky="ew", padx=(0, 6))

        self._cancel_btn = ctk.CTkButton(
            btn_frame, text="✕  Cancel",
            fg_color=("gray70", "gray30"), hover_color=("gray60", "gray25"),
            command=self._cancel_download, state="disabled",
        )
        self._cancel_btn.grid(row=0, column=1, sticky="ew", padx=(6, 0))

        # ── Merge section ─────────────────────────────────────────────────────
        sep2 = ctk.CTkFrame(left, height=1, fg_color=("gray75", "gray35"))
        sep2.grid(row=8, column=0, columnspan=4, sticky="ew", padx=16, pady=12)

        ctk.CTkLabel(
            left, text="Merge Downloaded CSVs",
            font=ctk.CTkFont(size=14, weight="bold"),
        ).grid(row=9, column=0, columnspan=4, sticky="w", padx=16, pady=(0, 6))

        merge_row = ctk.CTkFrame(left, fg_color="transparent")
        merge_row.grid(row=10, column=0, columnspan=4, sticky="ew", padx=16, pady=(0, 4))
        merge_row.columnconfigure(0, weight=1)

        self._merge_name = ctk.CTkEntry(merge_row, placeholder_text="merged_data")
        self._merge_name.grid(row=0, column=0, sticky="ew", padx=(0, 6))

        ctk.CTkLabel(merge_row, text=".csv", text_color=("gray50", "gray60")).grid(row=0, column=1)

        self._merge_btn = ctk.CTkButton(
            left, text="⊕  Merge CSVs", command=self._merge_csvs,
            fg_color=("gray65", "gray35"), hover_color=("gray55", "gray25"),
        )
        self._merge_btn.grid(row=11, column=0, columnspan=4, sticky="ew", padx=16, pady=(6, 16))

        # ── Status log ────────────────────────────────────────────────────────
        sep3 = ctk.CTkFrame(left, height=1, fg_color=("gray75", "gray35"))
        sep3.grid(row=12, column=0, columnspan=4, sticky="ew", padx=16, pady=(0, 8))

        ctk.CTkLabel(
            left, text="Activity Log",
            font=ctk.CTkFont(size=14, weight="bold"),
        ).grid(row=13, column=0, columnspan=4, sticky="w", padx=16, pady=(0, 4))

        self._log = ctk.CTkTextbox(left, height=130, state="disabled",
                                   font=ctk.CTkFont(family="Courier", size=11))
        self._log.grid(row=14, column=0, columnspan=4, sticky="nsew", padx=16, pady=(0, 16))
        left.rowconfigure(14, weight=1)

    def _build_right_panel(self, parent):
        right = ctk.CTkFrame(parent)
        right.grid(row=0, column=1, sticky="nsew")
        right.rowconfigure(3, weight=1)
        right.columnconfigure(0, weight=1)

        ctk.CTkLabel(
            right, text=f"Stations  ({len(STATION_NAMES)})",
            font=ctk.CTkFont(size=14, weight="bold"),
        ).grid(row=0, column=0, sticky="w", padx=16, pady=(14, 6))

        # Search box
        self._search_var = ctk.StringVar()
        self._search_var.trace_add("write", self._filter_stations)
        search = ctk.CTkEntry(right, textvariable=self._search_var,
                              placeholder_text="🔍  Search stations…")
        search.grid(row=1, column=0, sticky="ew", padx=16, pady=(0, 6))

        # Select All / None
        btn_row = ctk.CTkFrame(right, fg_color="transparent")
        btn_row.grid(row=2, column=0, sticky="ew", padx=16, pady=(0, 6))
        ctk.CTkButton(btn_row, text="Select All",  width=100,
                      command=self._select_all).pack(side="left", padx=(0, 6))
        ctk.CTkButton(btn_row, text="Select None", width=100,
                      fg_color=("gray65", "gray35"), hover_color=("gray55", "gray25"),
                      command=self._select_none).pack(side="left")

        # Scrollable station list
        self._station_scroll = ctk.CTkScrollableFrame(right, label_text="")
        self._station_scroll.grid(row=3, column=0, sticky="nsew", padx=16, pady=(0, 16))

        self._checkboxes: dict[str, ctk.CTkCheckBox] = {}
        self._render_station_list(STATION_NAMES)

        # Selection count label
        self._sel_count_label = ctk.CTkLabel(right, text=f"✓ {len(STATION_NAMES)} selected",
                                             text_color=("gray50", "gray60"))
        self._sel_count_label.grid(row=4, column=0, sticky="w", padx=16, pady=(0, 12))

    def _build_status_bar(self):
        bar = ctk.CTkFrame(self, fg_color=("gray80", "gray20"), corner_radius=0, height=28)
        bar.pack(fill="x", side="bottom")
        self._status_label = ctk.CTkLabel(bar, text="Ready", text_color=("gray40", "gray65"),
                                          font=ctk.CTkFont(size=11))
        self._status_label.pack(side="left", padx=12)

    # ── Widget factory ────────────────────────────────────────────────────────

    def _date_entry(self, parent, row: int, col: int, default: str = "",
                    width: int = 90) -> ctk.CTkEntry:
        entry = ctk.CTkEntry(parent, width=width)
        entry.insert(0, default)
        entry.grid(row=row, column=col, padx=4, pady=4, sticky="w")
        return entry

    # ── Station list helpers ──────────────────────────────────────────────────

    def _render_station_list(self, names: list[str]):
        for widget in self._station_scroll.winfo_children():
            widget.destroy()
        self._checkboxes.clear()
        for name in names:
            cb = ctk.CTkCheckBox(
                self._station_scroll, text=name,
                variable=self._selected_vars[name],
                command=self._update_sel_count,
            )
            cb.pack(anchor="w", pady=1)
            self._checkboxes[name] = cb

    def _filter_stations(self, *_):
        query = self._search_var.get().lower()
        filtered = [n for n in STATION_NAMES if query in n.lower()]
        self._render_station_list(filtered)
        self._update_sel_count()

    def _select_all(self):
        for var in self._selected_vars.values():
            var.set(True)
        self._update_sel_count()

    def _select_none(self):
        for var in self._selected_vars.values():
            var.set(False)
        self._update_sel_count()

    def _update_sel_count(self):
        count = sum(v.get() for v in self._selected_vars.values())
        self._sel_count_label.configure(text=f"✓ {count} selected")

    def _get_selected_stations(self) -> list[str]:
        return [name for name, var in self._selected_vars.items() if var.get()]

    # ── UI helpers ────────────────────────────────────────────────────────────

    def _log_message(self, msg: str):
        self._log.configure(state="normal")
        self._log.insert("end", msg + "\n")
        self._log.see("end")
        self._log.configure(state="disabled")

    def _set_status(self, msg: str):
        self._status_label.configure(text=msg)

    def _set_ui_downloading(self, active: bool):
        state_dl     = "disabled" if active else "normal"
        state_cancel = "normal"   if active else "disabled"
        self._dl_btn.configure(state=state_dl)
        self._cancel_btn.configure(state=state_cancel)
        self._merge_btn.configure(state=state_dl)

    def _toggle_mode(self):
        if ctk.get_appearance_mode() == "Dark":
            ctk.set_appearance_mode("light")
            self._mode_btn.configure(text="🌙 Dark")
        else:
            ctk.set_appearance_mode("dark")
            self._mode_btn.configure(text="☀ Light")

    def _show_error(self, msg: str):
        dialog = ctk.CTkToplevel(self)
        dialog.title("Error")
        dialog.geometry("380x140")
        dialog.grab_set()
        ctk.CTkLabel(dialog, text="⚠  " + msg, wraplength=340,
                     text_color=("red3", "#ff6b6b")).pack(padx=20, pady=24)
        ctk.CTkButton(dialog, text="OK", command=dialog.destroy, width=80).pack()

    def _show_info(self, title: str, msg: str):
        dialog = ctk.CTkToplevel(self)
        dialog.title(title)
        dialog.geometry("420x150")
        dialog.grab_set()
        ctk.CTkLabel(dialog, text=msg, wraplength=380).pack(padx=20, pady=24)
        ctk.CTkButton(dialog, text="OK", command=dialog.destroy, width=80).pack()

    # ── Download logic ────────────────────────────────────────────────────────

    def _start_download(self):
        # Validate inputs
        try:
            sy = int(self._start_year.get())
            sm = int(self._start_month.get())
            ey = int(self._end_year.get())
            em = int(self._end_month.get())
        except ValueError:
            self._show_error("Year and month fields must be integers.")
            return

        err = validate_date_range(sy, sm, ey, em)
        if err:
            self._show_error(err)
            return

        selected = self._get_selected_stations()
        if not selected:
            self._show_error("Please select at least one station.")
            return

        self._cancel_flag.clear()
        self._set_ui_downloading(True)
        self._progress_bar.set(0)
        self._progress_label.configure(text="0 / 0  (0%)")
        self._set_status("Downloading…")
        self._log_message(f"── Starting download: {sm}/{sy} → {em}/{ey}  |  {len(selected)} station(s) ──")

        self._worker = threading.Thread(
            target=self._download_worker,
            args=(sy, sm, ey, em, selected),
            daemon=True,
        )
        self._worker.start()

    def _download_worker(self, sy: int, sm: int, ey: int, em: int, selected: list[str]):
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        links = generate_links(sy, sm, ey, em, selected)
        total = len(links)
        downloaded = skipped = failed = 0

        for idx, link in enumerate(links):
            if self._cancel_flag.is_set():
                self._safe_update(lambda: self._log_message("⛔  Download cancelled by user."))
                break

            filename = os.path.basename(link)
            filepath = os.path.join(OUTPUT_DIR, filename)

            if os.path.exists(filepath) and os.path.getsize(filepath) > 0:
                skipped += 1
                msg = f"  ↷ Skipped (exists): {filename}"
            else:
                try:
                    r = requests.get(link, headers=DOWNLOAD_HEADERS, timeout=15)
                    if r.status_code == 200:
                        with open(filepath, "wb") as f:
                            f.write(r.content)
                        downloaded += 1
                        msg = f"  ✓ {filename}"
                    else:
                        failed += 1
                        msg = f"  ✗ {filename}  [HTTP {r.status_code}]"
                except (requests.RequestException, OSError) as exc:
                    failed += 1
                    msg = f"  ✗ {filename}  [{exc}]"

            pct = (idx + 1) / total
            count_text = f"{idx + 1} / {total}  ({pct:.0%})"
            self._safe_update(lambda m=msg, p=pct, c=count_text: (
                self._log_message(m),
                self._progress_bar.set(p),
                self._progress_label.configure(text=c),
                self._set_status(c),
            ))

        summary = f"── Done: {downloaded} downloaded, {skipped} skipped, {failed} failed ──"
        was_cancelled = self._cancel_flag.is_set()
        dl, sk, fa = downloaded, skipped, failed

        def _finalise(s=summary, c=was_cancelled, d=dl, sk_=sk, f_=fa):
            self._log_message(s)
            self._set_status("Cancelled" if c else "Download complete")
            self._set_ui_downloading(False)
            if not c:
                self._show_info(
                    "Download Complete",
                    f"✓ {d} file(s) downloaded\n"
                    f"↷ {sk_} skipped   ✗ {f_} failed\n"
                    f'Saved to "{OUTPUT_DIR}/"',
                )

        self._safe_update(_finalise)

    def _cancel_download(self):
        self._cancel_flag.set()
        self._set_status("Cancelling…")

    # ── Merge logic ───────────────────────────────────────────────────────────

    def _merge_csvs(self):
        filename = self._merge_name.get().strip() or "merged_data"
        # Strip accidental .csv suffix, then sanitise
        if filename.lower().endswith(".csv"):
            filename = filename[:-4]
        filename = "".join(c for c in filename if c.isalnum() or c in "._- ") or "merged_data"
        out_path = os.path.join(OUTPUT_DIR, f"{filename}.csv")

        if not os.path.isdir(OUTPUT_DIR):
            self._show_error(f'No "{OUTPUT_DIR}" directory found. Download data first.')
            return

        # Exclude the target merge file itself to avoid reading what we're writing
        all_files = sorted(
            f for f in os.listdir(OUTPUT_DIR)
            if f.endswith(".csv") and f != f"{filename}.csv"
        )

        if not all_files:
            self._show_error(f'No CSV files found in "{OUTPUT_DIR}".')
            return

        try:
            with open(out_path, "w", newline="", encoding="utf-8") as outfile:
                writer = csv.writer(outfile)
                header_written = False
                for fname in all_files:
                    with open(os.path.join(OUTPUT_DIR, fname), "r", encoding="utf-8",
                              errors="replace") as infile:
                        reader = csv.reader(infile)
                        rows = list(reader)
                        if not rows:
                            continue
                        if not header_written:
                            writer.writerow(rows[0])
                            header_written = True
                        writer.writerows(rows[1:])

            self._log_message(f"  ⊕ Merged {len(all_files)} files → {filename}.csv")
            self._show_info("Merge Complete",
                            f"Merged {len(all_files)} file(s) into\n\"{filename}.csv\"")
        except OSError as exc:
            self._show_error(str(exc))

    # ── Thread-safe callback helper ───────────────────────────────────────────

    def _safe_update(self, fn):
        """Schedule a callable on the main (Tk) thread."""
        self.after(0, fn)


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app = WeatherApp()
    app.mainloop()
