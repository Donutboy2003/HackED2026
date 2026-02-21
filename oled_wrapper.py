#!/usr/bin/python3
# oled_display.py

import sys
import os

# Get current file directory
base_dir = os.path.dirname(os.path.abspath(__file__))

# Path to lib folder
libdir = os.path.join(base_dir, "lib")

# Add lib folder to Python path
if libdir not in sys.path:
    sys.path.append(libdir)
    
from PIL import Image, ImageDraw, ImageFont
from waveshare_OLED import OLED_1in51


class OLEDDisplay:
    def __init__(self, font_path=None, rotate=0):
        """
        Initialize OLED display
        """
        self.disp = OLED_1in51.OLED_1in51()
        self.disp.Init()
        self.disp.clear()

        self.width = self.disp.width
        self.height = self.disp.height

        self.rotate = rotate

        # Default font path
        if font_path is None:
            # assumes same folder structure as waveshare example
            base_dir = os.path.dirname(os.path.abspath(__file__))
            font_path = os.path.join(base_dir, "pic", "Font.ttc")

        self.font_small = ImageFont.truetype(font_path, 14)
        self.font_medium = ImageFont.truetype(font_path, 18)
        self.font_large = ImageFont.truetype(font_path, 24)

    # --------------------------
    # Core function
    # --------------------------
    def _show_image(self, image):
        """
        Internal helper to send image to OLED
        """
        if self.rotate != 0:
            image = image.rotate(self.rotate)

        self.disp.ShowImage(self.disp.getbuffer(image))

    # --------------------------
    # Public functions
    # --------------------------

    def clear(self):
        """
        Clear display
        """
        self.disp.clear()

    def display_text(self, text, x=0, y=0, font_size="medium"):
        """
        Display single line of text
        """

        font = self._get_font(font_size)

        image = Image.new("1", (self.width, self.height), 255)
        draw = ImageDraw.Draw(image)

        draw.text((x, y), text, font=font, fill=0)

        self._show_image(image)

    def display_multiline_text(self, lines, x=0, y=0, line_spacing=4, font_size="medium"):
        """
        Display multiple lines
        lines = ["Line 1", "Line 2", ...]
        """

        font = self._get_font(font_size)

        image = Image.new("1", (self.width, self.height), 255)
        draw = ImageDraw.Draw(image)

        current_y = y

        for line in lines:
            draw.text((x, current_y), line, font=font, fill=0)
            current_y += font.size + line_spacing

        self._show_image(image)

    def display_centered_text(self, text, font_size="medium"):
        """
        Display centered text
        """

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
        """
        Display BMP image
        """
        image = Image.open(image_path).convert("1")
        self._show_image(image)

    def draw_rectangle(self, x1, y1, x2, y2):
        """
        Draw rectangle
        """

        image = Image.new("1", (self.width, self.height), 255)
        draw = ImageDraw.Draw(image)

        draw.rectangle((x1, y1, x2, y2), outline=0)

        self._show_image(image)

    # --------------------------
    # Helper
    # --------------------------

    def _get_font(self, size):

        if size == "small":
            return self.font_small
        elif size == "large":
            return self.font_large
        else:
            return self.font_medium

    def shutdown(self):
        self.disp.clear()
        self.disp.module_exit()
