"""Entry point — thin GUI shell wiring all modules together."""

import tkinter as tk
from serial_reader import SerialReader
from app_state import AppState, MODE_WRITE, MODE_CAPTION
from renderer import OLEDBuffer, OLEDCanvasRenderer, DirectionPlot

SERIAL_PORT = "/dev/tty.usbmodem1102"
BAUD_RATE = 115200

# N-gram level badge colours
_LEVEL_COLORS = {
    "5G": "#ff0000",   # red    — pentagram hit
    "4G": "#ff8800",   # orange — quadrigram hit
    "3G": "#ffaa33",   # amber  — trigram hit
    "2G": "#4499ff",   # blue   — bigram hit
    "1G": "#44cc88",   # green  — unigram fallback
    "—":  "#666666",   # grey   — no suggestions yet
}


class HeadMouseGUI:
    def __init__(self, root: tk.Tk):
        self.root = root
        root.title("Head Mouse — Communicator")
        root.geometry("620x800")
        root.configure(bg="#222")

        self.reader = SerialReader(SERIAL_PORT, BAUD_RATE)
        self.state = AppState()
        self.oled = OLEDBuffer()

        self._build_ui()
        self.oled_renderer = OLEDCanvasRenderer(self.screen)

        if not self.reader.connect():
            self.lbl_raw.config(text=f"Error: {self.reader.last_error}", fg="red")
        self._loop()

    def _build_ui(self):
        # OLED mirror
        frame_oled = tk.Frame(self.root, bg="#111", pady=10)
        frame_oled.pack()
        tk.Label(frame_oled, text="SSD1306 FRAMEBUFFER VIEW",
                 fg="#555", bg="#111").pack()

        sw = OLEDBuffer.WIDTH * OLEDCanvasRenderer.PIXEL_SCALE
        sh = OLEDBuffer.HEIGHT * OLEDCanvasRenderer.PIXEL_SCALE
        self.screen = tk.Canvas(frame_oled, width=sw, height=sh,
                                bg="black", highlightthickness=0)
        self.screen.pack()

        # Debug frame
        frame_dbg = tk.Frame(self.root, bg="#2d2d2d")
        frame_dbg.pack(fill="both", expand=True, padx=10, pady=10)

        self.lbl_raw = tk.Label(frame_dbg, text="Waiting…",
                                font=("Consolas", 10), fg="yellow", bg="#2d2d2d")
        self.lbl_raw.pack(anchor="w")

        self.lbl_state = tk.Label(frame_dbg, text="",
                                  font=("Consolas", 10), fg="#aaa", bg="#2d2d2d")
        self.lbl_state.pack(anchor="w")

        self.lbl_sent = tk.Label(frame_dbg, text="Sentence: ",
                                 font=("Consolas", 12), fg="white", bg="#2d2d2d")
        self.lbl_sent.pack(anchor="w")

        # N-gram context row: coloured badge + context words label side by side
        frame_ngram = tk.Frame(frame_dbg, bg="#2d2d2d")
        frame_ngram.pack(anchor="w", pady=(2, 0))

        self.lbl_ngram_badge = tk.Label(
            frame_ngram, text="—", width=3,
            font=("Consolas", 10, "bold"), fg="#666", bg="#2d2d2d",
        )
        self.lbl_ngram_badge.pack(side="left")

        self.lbl_ngram_ctx = tk.Label(
            frame_ngram, text="no context",
            font=("Consolas", 10), fg="#666", bg="#2d2d2d",
        )
        self.lbl_ngram_ctx.pack(side="left", padx=(4, 0))

        # Direction plot
        self.plot = DirectionPlot(frame_dbg)

    def _loop(self):
        data = self.reader.read_latest()
        if data is not None:
            roll, pitch = data
            self.state.update(roll, pitch)

            s = self.state
            inp = s.input

            self.lbl_raw.config(
                text=f"Roll: {roll:.3f}  Pitch: {pitch:.3f}  "
                     f"Dir: {inp.direction}  Dwell: {s.dwell_percent:.0%}"
            )
            self.lbl_state.config(
                text=f"Mode: {s.mode}  Cursor: {s.cursor_index}  "
                     f"Sugg: {s.sugg_index}  Prefix: '{s.prefix}'"
            )
            self.lbl_sent.config(text=f"SENT: {s.sentence}{s.prefix}")

            # N-gram context badge
            level = s.ngram_level
            color = _LEVEL_COLORS.get(level, "#666666")
            ctx = s.ngram_context or "—"
            self.lbl_ngram_badge.config(text=level, fg=color)
            self.lbl_ngram_ctx.config(
                text=f"context: [{ctx}]  →  {', '.join(s.suggestions) or '—'}",
                fg=color,
            )

            # Draw OLED
            self.oled.clear()
            if s.mode == MODE_WRITE:
                self.oled.draw_write_scene(
                    sentence=s.sentence,
                    prefix=s.prefix,
                    cursor_index=s.cursor_index,
                    sugg_index=s.sugg_index,
                    suggestions=s.suggestions,
                    dwell_percent=s.dwell_percent,
                    direction=inp.direction,
                )
            else:
                self.oled.draw_caption_scene(
                    transcript=s.captioner.transcript,
                    scroll_offset=s.transcript_scroll,
                    paused=s.captioner.paused,
                )
            self.oled_renderer.render(self.oled)

            # Debug plot
            self.plot.update(
                roll, pitch,
                inp.direction,
                s.dwell_percent,
                s.flash_direction,
                s.mode,
            )

        self.root.after(16, self._loop)


if __name__ == "__main__":
    root = tk.Tk()
    HeadMouseGUI(root)
    root.mainloop()
