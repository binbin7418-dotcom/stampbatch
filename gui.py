#!/usr/bin/env python3
"""StampBatch desktop shell (tkinter).
Pick a folder of photos -> batch-watermark them -> re-check every output."""
import os
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from stamp_batch import POSITIONS, PRESETS, process_folder


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("StampBatch — Batch Photo Watermark & Re-Check")
        self.geometry("700x620")
        self.in_dir = tk.StringVar()
        self.out_dir = tk.StringVar()
        self.mode = tk.StringVar(value="text")
        self.text = tk.StringVar(value="© My Shop")
        self.logo_path = tk.StringVar()
        self.color = tk.StringVar(value="white")
        self.position = tk.StringVar(value="bottom-right")
        self.preset = tk.StringVar(value="generic")
        self.opacity = tk.IntVar(value=170)
        self.size = tk.DoubleVar(value=0.0)   # 0 = preset default
        self.tile = tk.BooleanVar(value=False)

        pad = {"padx": 12, "pady": 3}
        tk.Label(self, text="Photos folder:").pack(anchor="w", **pad)
        row = tk.Frame(self); row.pack(fill="x", padx=12)
        tk.Entry(row, textvariable=self.in_dir).pack(side="left", fill="x", expand=True)
        tk.Button(row, text="Browse…", command=self.pick_in).pack(side="left", padx=6)

        tk.Label(self, text="Output folder (originals are never touched):").pack(anchor="w", **pad)
        row = tk.Frame(self); row.pack(fill="x", padx=12)
        tk.Entry(row, textvariable=self.out_dir).pack(side="left", fill="x", expand=True)
        tk.Button(row, text="Browse…", command=self.pick_out).pack(side="left", padx=6)

        row = tk.Frame(self); row.pack(fill="x", padx=12, pady=(10, 0))
        tk.Label(row, text="Watermark:").pack(side="left")
        tk.Radiobutton(row, text="Text", variable=self.mode, value="text").pack(side="left")
        tk.Entry(row, textvariable=self.text, width=26).pack(side="left", padx=4)
        ttk.Combobox(row, textvariable=self.color, values=["white", "black"],
                     width=7, state="readonly").pack(side="left")
        tk.Radiobutton(row, text="Logo image", variable=self.mode, value="logo").pack(side="left", padx=(10, 0))
        tk.Button(row, text="Choose logo…", command=self.pick_logo).pack(side="left", padx=4)
        tk.Label(row, textvariable=self.logo_path).pack(side="left")

        row = tk.Frame(self); row.pack(fill="x", padx=12, pady=(8, 0))
        tk.Label(row, text="Position:").pack(side="left")
        ttk.Combobox(row, textvariable=self.position, values=POSITIONS,
                     width=14, state="readonly").pack(side="left", padx=4)
        tk.Label(row, text="Platform preset:").pack(side="left", padx=(10, 0))
        ttk.Combobox(row, textvariable=self.preset, values=sorted(PRESETS),
                     width=10, state="readonly").pack(side="left", padx=4)
        tk.Checkbutton(row, text="Tile across photo", variable=self.tile).pack(side="left", padx=(10, 0))

        row = tk.Frame(self); row.pack(fill="x", padx=12, pady=(8, 0))
        tk.Label(row, text="Opacity:").pack(side="left")
        tk.Scale(row, from_=20, to=255, orient="horizontal", variable=self.opacity,
                 length=180).pack(side="left")
        tk.Label(row, text="Size (% of photo width, 0 = preset):").pack(side="left", padx=(12, 0))
        tk.Spinbox(row, from_=0, to=60, increment=1, textvariable=self.size, width=5).pack(side="left")

        self.btn = tk.Button(self, text="Watermark & Re-Check", command=self.run, height=2)
        self.btn.pack(pady=12)
        self.log = scrolledtext.ScrolledText(self, wrap="word")
        self.log.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        self.write("StampBatch stamps a text or logo watermark on a whole folder of photos,\n"
                   "then re-opens every output to prove the mark landed and the size is unchanged.\n"
                   "Everything runs locally — your photos never leave this computer.\n"
                   "It only watermarks: it never resizes, crops or renames your photos.\n")

    def write(self, s):
        self.log.insert("end", s)
        self.log.see("end")

    def pick_in(self):
        p = filedialog.askdirectory()
        if p:
            self.in_dir.set(p)
            if not self.out_dir.get():
                self.out_dir.set(os.path.join(p, "stampbatch_output"))

    def pick_out(self):
        p = filedialog.askdirectory()
        if p:
            self.out_dir.set(p)

    def pick_logo(self):
        p = filedialog.askopenfilename(
            filetypes=[("Images", "*.png *.jpg *.jpeg *.webp *.bmp"), ("All files", "*.*")])
        if p:
            self.logo_path.set(p)
            self.mode.set("logo")

    def run(self):
        src, dst = self.in_dir.get().strip(), self.out_dir.get().strip()
        if not src or not os.path.isdir(src):
            messagebox.showerror("StampBatch", "Choose a photos folder first.")
            return
        if not dst:
            messagebox.showerror("StampBatch", "Choose an output folder.")
            return
        if os.path.abspath(src) == os.path.abspath(dst):
            messagebox.showerror("StampBatch", "Output folder must differ from the photos folder.")
            return
        config = {"mode": self.mode.get(), "text": self.text.get(),
                  "logo_path": self.logo_path.get(), "color": self.color.get(),
                  "position": self.position.get(), "preset": self.preset.get(),
                  "opacity": int(self.opacity.get()),
                  "size_ratio": (self.size.get() / 100.0) or None,
                  "margin_ratio": None, "tile": bool(self.tile.get()), "tile_angle": 0}
        self.btn.config(state="disabled")
        threading.Thread(target=self._work, args=(dst, config), daemon=True).start()

    def _work(self, dst, config):
        try:
            s = process_folder(self.in_dir.get().strip(), dst, config)
            self.write(f"\nDone. Photos: {s['found']} · watermarked & verified: {s['ok']} · "
                       f"failed: {s['failed']}\nReport: {s['report_path']}\n")
            for name, detail in s["failures"]:
                self.write(f"  [FAIL] {name} — {detail}\n")
            self.write("Verdict: PASS — every output re-checked.\n" if s["failed"] == 0
                       else "Verdict: CHECK THE REPORT — some photos failed verification.\n")
        except Exception as e:  # surface, never crash silently
            self.write(f"\nError: {e}\n")
        finally:
            self.btn.config(state="normal")


if __name__ == "__main__":
    App().mainloop()
