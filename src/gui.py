"""가벼운 Tkinter 진행 GUI.

수집/분석은 백그라운드 스레드에서 실행하고, 메인 스레드(GUI)는 큐를 통해
로그·진행률만 갱신합니다. 따라서 작업 중에도 창이 멈추거나 렉이 걸리지 않습니다.
"""

import queue
import threading
import webbrowser
from pathlib import Path

import tkinter as tk
from tkinter import ttk, messagebox

import pipeline


class BriefingApp:
    def __init__(self, root):
        self.root = root
        self.q = queue.Queue()
        self.worker = None
        self.report_path = None

        root.title("보안 · AI 데일리 브리핑")
        root.geometry("720x560")
        root.minsize(560, 440)

        pad = {"padx": 14, "pady": 6}

        header = ttk.Frame(root)
        header.pack(fill="x", **pad)
        ttk.Label(header, text="🛰️ 보안 · AI 데일리 브리핑",
                  font=("Segoe UI", 15, "bold")).pack(side="left")

        ctrl = ttk.Frame(root)
        ctrl.pack(fill="x", **pad)
        self.run_btn = ttk.Button(ctrl, text="▶ 오늘 보고서 생성", command=self.start)
        self.run_btn.pack(side="left")
        self.open_btn = ttk.Button(ctrl, text="📄 보고서 열기", command=self.open_report,
                                   state="disabled")
        self.open_btn.pack(side="left", padx=8)
        self.folder_btn = ttk.Button(ctrl, text="📁 폴더 열기", command=self.open_folder)
        self.folder_btn.pack(side="left")

        self.status = ttk.Label(root, text="대기 중 — '오늘 보고서 생성'을 누르세요.")
        self.status.pack(fill="x", **pad)

        self.bar = ttk.Progressbar(root, mode="determinate", maximum=100)
        self.bar.pack(fill="x", padx=14, pady=(0, 6))

        logframe = ttk.LabelFrame(root, text="진행 로그")
        logframe.pack(fill="both", expand=True, padx=14, pady=(6, 14))
        self.log = tk.Text(logframe, wrap="word", height=16, state="disabled",
                           font=("Consolas", 10))
        scroll = ttk.Scrollbar(logframe, command=self.log.yview)
        self.log.configure(yscrollcommand=scroll.set)
        self.log.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        self.root.after(100, self._drain)

    # ------------------------------------------------------------------ #
    def _append(self, text):
        self.log.configure(state="normal")
        self.log.insert("end", text + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def start(self):
        if self.worker and self.worker.is_alive():
            return
        self.run_btn.configure(state="disabled")
        self.open_btn.configure(state="disabled")
        self.bar.configure(value=0)
        self.status.configure(text="수집을 시작합니다…")
        self._append("──────── 작업 시작 ────────")

        def log_cb(msg):
            self.q.put(("log", msg))

        def progress_cb(cur, total):
            self.q.put(("progress", cur, total))

        def work():
            try:
                result = pipeline.run(progress_cb=progress_cb, log_cb=log_cb)
                self.q.put(("done", result))
            except Exception as e:  # noqa: BLE001 — GUI는 어떤 오류에도 죽지 않아야 함
                self.q.put(("error", str(e)))

        self.worker = threading.Thread(target=work, daemon=True)
        self.worker.start()

    def _drain(self):
        try:
            while True:
                item = self.q.get_nowait()
                kind = item[0]
                if kind == "log":
                    self._append(item[1])
                elif kind == "progress":
                    cur, total = item[1], item[2]
                    pct = int(cur / total * 100) if total else 0
                    self.bar.configure(value=pct)
                    self.status.configure(text=f"진행 중… {cur}/{total} 소스 ({pct}%)")
                elif kind == "done":
                    self._on_done(item[1])
                elif kind == "error":
                    self._on_error(item[1])
        except queue.Empty:
            pass
        self.root.after(100, self._drain)

    def _on_done(self, result):
        self.report_path = result["report_path"]
        n = result["new_count"]
        self.bar.configure(value=100)
        self.status.configure(text=f"완료 — 신규 {n}건. 보고서가 생성되었습니다.")
        self._append(f"✅ 완료: 신규 {n}건 / 보고서 {self.report_path.name}")
        self.run_btn.configure(state="normal")
        self.open_btn.configure(state="normal")
        self.open_report()  # 완료 시 자동으로 보고서 열기

    def _on_error(self, msg):
        self.status.configure(text="오류가 발생했습니다.")
        self._append(f"❌ 오류: {msg}")
        self.run_btn.configure(state="normal")
        messagebox.showerror("오류", f"작업 중 오류가 발생했습니다:\n{msg}")

    def open_report(self):
        if self.report_path and Path(self.report_path).exists():
            webbrowser.open(Path(self.report_path).resolve().as_uri())

    def open_folder(self):
        folder = pipeline.REPORTS_DIR
        folder.mkdir(parents=True, exist_ok=True)
        webbrowser.open(folder.resolve().as_uri())


def main():
    root = tk.Tk()
    try:
        ttk.Style().theme_use("vista")  # Windows 기본 테마
    except tk.TclError:
        pass
    BriefingApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
