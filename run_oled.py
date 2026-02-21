#!/usr/bin/python3
import time
from oled_wrapper import OLEDDisplay
'''
oled = OLEDDisplay()
oled.clear()
oled.display_text("Hello OLED!", x=0, y=0, font_size="medium")
time.sleep(3)
oled.clear()
oled.display_multiline_text(["Line 1 make this long", "Line 2", "Line 3"], x=0, y=0, font_size="small")
time.sleep(90)
oled.clear()
oled.display_centered_text("DONE", font_size="large")
time.sleep(3)

oled.clear()
oled.shutdown()
'''

oled = OLEDDisplay()

text = (
	"""How are you doing? I hope you are doing well and that your family is also doing well. I will go no please take care and take your time. I hope you have an exellent day
	"""
)

try:
    oled.scroll_paragraph(text, font_size="small", speed_fps=60, loop=True, step = 4)
except KeyboardInterrupt:
    pass
finally:
    # Clear twice + small sleep helps on some drivers
    time.sleep(0.1)
    oled.clear()
    oled.shutdown()
