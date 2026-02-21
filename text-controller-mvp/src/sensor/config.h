#ifndef CONFIG_H
#define CONFIG_H

#include "pico/stdlib.h"

// --- I2C PINS (MATCHING YOUR PHOTO) ---
// You are wired to the bottom right side of the Pico.
// GP4 = I2C0 SDA
// GP5 = I2C0 SCL
#define I2C_PORT        i2c0
#define I2C_SDA_PIN     4
#define I2C_SCL_PIN     5
#define I2C_BAUDRATE    400000 // 400kHz

// --- ADXL343 REGISTERS ---
#define ADXL343_ADDR    0x53   // Default I2C address (Alternative is 0x1D)
#define REG_DEVID       0x00
#define REG_POWER_CTL   0x2D
#define REG_DATA_FORMAT 0x31
#define REG_DATAX0      0x32

// --- GESTURE TUNING ---
// ADJUST THESE TO CHANGE FEEL
// 1.0 = 90 degrees tilt. 0.2 ~= 15 degrees.
#define TILT_THRESHOLD  0.25f  // How much you lean your head to trigger scrolling
#define NOD_THRESHOLD   0.25f  // How far down you look to "Click"

#define SCROLL_SPEED_MS 250    // Delay between scroll steps (lower = faster)
#define CLICK_DEBOUNCE  1000   // Milliseconds to wait after a click (prevents double clicks)

// --- UI SETTINGS ---
#define ALPHABET "ABCDEFGHIJKLMNOPQRSTUVWXYZ_ <" // < is backspace

#endif // CONFIG_H
