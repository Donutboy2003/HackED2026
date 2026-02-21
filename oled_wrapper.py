#!/usr/bin/python3
# oled_display.py

import sys
import os
import time
from PIL import Image, ImageDraw, ImageFont

# --------------------------
# Add ./lib to Python path so "waveshare_OLED" can be imported
# --------------------------
base_dir = os.path.dirname(os.path.abspath(__file__))
libdir = os.path.join(base_dir, "lib")

if libdir not in sys.path:
    sys.path.append(libdir)

from waveshare_OLED import OLED_1in51


class OLEDDisplay:
    def __init__(self, font_path=None, rotate=0):
        """
        Initialize OLED display.
        rotate can be 0, 90, 180, 270.
        """
        self.disp = OLED_1in51.OLED_1in51()
        self.disp.Init()
        self.disp.clear()

        self.width = self.disp.width
        self.height = self.disp.height

        self.rotate = rotate

        # Default font path (expects ./pic/Font.ttc)
        if font_path is None:
            font_path = os.path.join(base_dir, "pic", "Font.ttc")

        self.font_small = ImageFont.truetype(font_path, 14)
        self.font_medium = ImageFont.truetype(font_path, 18)
        self.font_large = ImageFont.truetype(font_path, 24)

    # --------------------------
    # Core helper
    # --------------------------
    def _show_image(self, image):
        """
        Internal helper to send image to OLED
        """
        if self.rotate != 0:
            image = image.rotate(self.rotate, expand=False)
        self.disp.ShowImage(self.disp.getbuffer(image))

    def _get_font(self, size):
        if size == "small":
            return self.font_small
        elif size == "large":
            return self.font_large
        else:
            return self.font_medium

    def _wrap_text_pixels(self, text: str, font, max_width: int):
        """
        Word-wrap text so each line fits within max_width pixels.
        """
        words = text.split()
        lines = []
        current = ""

        for w in words:
            test = w if current == "" else current + " " + w

            if font.getlength(test) <= max_width:
                current = test
            else:
                if current:
                    lines.append(current)
                    current = w
                else:
                    # Hard split long word
                    chunk = ""
                    for ch in w:
                        if font.getlength(chunk + ch) <= max_width:
                            chunk += ch
                        else:
                            if chunk:
                                lines.append(chunk)
                            chunk = ch
                    current = chunk

        if current:
            lines.append(current)

        return lines

    # --------------------------
    # Public API
    # --------------------------
    def clear(self):
        self.disp.clear()

    def display_text(self, text, x=0, y=0, font_size="medium"):
        font = self._get_font(font_size)

        image = Image.new("1", (self.width, self.height), 255)
        draw = ImageDraw.Draw(image)
        draw.text((x, y), text, font=font, fill=0)

        self._show_image(image)

    def display_multiline_text(self, lines, x=0, y=0, line_spacing=4, font_size="medium"):
        font = self._get_font(font_size)

        image = Image.new("1", (self.width, self.height), 255)
        draw = ImageDraw.Draw(image)

        current_y = y
        for line in lines:
            draw.text((x, current_y), line, font=font, fill=0)
            current_y += font.size + line_spacing

        self._show_image(image)

    def display_centered_text(self, text, font_size="medium"):
        font = self._get_font(font_size)

        image = Image.new("1", (self.width, self.height), 255)
        draw = ImageDraw.Draw(image)

        bbox = draw.textbbox((0, 0), text, font=font)

        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]

        x = (self.width - text_width) // 2
        y = (self.height - text_height) // 2

        draw.text((x, y), text, font=font, fill=0)
        self._show_image(image)

    def display_image(self, image_path):
        image = Image.open(image_path).convert("1")
        self._show_image(image)

    def draw_rectangle(self, x1, y1, x2, y2):
        image = Image.new("1", (self.width, self.height), 255)
        draw = ImageDraw.Draw(image)
        draw.rectangle((x1, y1, x2, y2), outline=0)
        self._show_image(image)

    def scroll_paragraph(
        self,
        text: str,
        font_size: str = "small",
        margin: int = 2,
        line_spacing: int = 2,
        speed_fps: int = 20,
        pause_at_end: float = 1.0,
        step: int = 1,
        loop: bool = False,
    ):
        """
        Scroll a long paragraph upward with pixel-accurate wrapping.
        """
        font = self._get_font(font_size)

        max_width_px = self.width - 2 * margin
        lines = self._wrap_text_pixels(text, font, max_width_px)

        ascent, descent = font.getmetrics()
        line_h = ascent + descent + line_spacing

        total_h = max(self.height, margin * 2 + len(lines) * line_h)

        tall = Image.new("1", (self.width, total_h), 255)
        draw = ImageDraw.Draw(tall)

        y = margin
        for line in lines:
            draw.text((margin, y), line, font=font, fill=0)
            y += line_h

        start_y = 0
        end_y = total_h - self.height
        delay = 1.0 / max(1, speed_fps)

        while True:
            for offset in range(start_y, end_y + 1, step):
                frame = tall.crop((0, offset, self.width, offset + self.height))
                self._show_image(frame)
                time.sleep(delay)

            time.sleep(pause_at_end)

            if not loop:
                break

    def shutdown(self):
        self.disp.clear()
        self.disp.module_exit()
