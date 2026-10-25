#!/usr/bin/env python3
"""SubtitleFix desktop shell (tkinter). Pick a subtitle file -> repair & re-check."""
import os
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from subtitle_fix import run_subtitlefix


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("SubtitleFix — Subtitle Repair & Re-Check")
        self.geometry("680x520")
        self.src = tk.StringVar()
        tk.Label(self, text="Subtitle file (.srt / .vtt):").pack(anchor="w", padx=12, pady=(12, 2))
        row = tk.Frame(self)
        row.pack(fill="x", padx=12)
        tk.Entry(row, textvariable=self.src).pack(side="left", fill="x", expand=True)
        tk.Button(row, text="Browse…", command=self.pick).pack(side="left", padx=6)
        self.btn = tk.Button(self, text="Repair & Re-Check", command=self.run, height=2)
        self.btn.pack(pady=12)
        self.log = scrolledtext.ScrolledText(self, wrap="word")
        self.log.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        self.write("SubtitleFix repairs broken timings, overlaps and numbering, then\n"
                   "re-parses the repaired file to prove it is mechanically sound.\n"
                   "Everything runs locally — your files never leave this computer.\n")

    def write(self, s):
        self.log.insert("end", s)
        self.log.see("end")

    def pick(self):
        p = filedialog.askopenfilename(filetypes=[("Subtitle files", "*.srt *.vtt"), ("All files", "*.*")])
        if p:
            self.src.set(p)

    def run(self):
        src = self.src.get().strip()
        if not src or not os.path.isfile(src):
            messagebox.showerror("SubtitleFix", "Choose a subtitle file first.")
            return
        self.btn.config(state="disabled")
        threading.Thread(target=self._work, args=(src,), daemon=True).start()

    def _work(self, src):
        try:
            outdir = os.path.join(os.path.dirname(src), "subtitlefix_output")
            s = run_subtitlefix(src, outdir)
            self.write(f"\nDone. Cues: {s['cues']} · auto-fixed: {s['fixed']} · "
                       f"warnings: {s['warnings']}\n"
                       f"Repaired file: {s['fixed_path']}\nReport: {s['report_path']}\n")
            self.write(f"Verdict: {s['verdict']}\n")
        except Exception as e:
            self.write(f"\nError: {e}\n")
        finally:
            self.btn.config(state="normal")


if __name__ == "__main__":
    App().mainloop()
