#!/usr/bin/python3
import time
from oled_wrapper import OLEDDisplay

oled = OLEDDisplay()
oled.clear()
oled.display_text("Hello OLED!", x=0, y=0, font_size="medium")
time.sleep(3)
oled.clear()
oled.display_multiline_text(["Line 1 make this long", "Line 2", "Line 3"], x=0, y=0, font_size="small")
time.sleep(3)
oled.clear()
oled.display_centered_text("DONE", font_size="large")
time.sleep(3)

oled.clear()
oled.shutdown()
