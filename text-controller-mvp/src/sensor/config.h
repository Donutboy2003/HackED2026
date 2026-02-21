#ifndef CONFIG_H
#define CONFIG_H

// --- I2C ---
// Enable I2C on RPi5: sudo raspi-config → Interface Options → I2C
// Default bus on RPi5 header is /dev/i2c-1
#define I2C_DEVICE      "/dev/i2c-1"
#define I2C_BAUDRATE    400000          // informational only; set via raspi-config

// --- ADXL343 ---
#define ADXL343_ADDR    0x53            // ALT address = 0x1D
#define REG_POWER_CTL   0x2D
#define REG_DATA_FORMAT 0x31
#define REG_DATAX0      0x32

// --- GESTURE TUNING ---
#define TILT_THRESHOLD  0.25f
#define NOD_THRESHOLD   0.25f
#define SCROLL_SPEED_MS 250
#define CLICK_DEBOUNCE  1000

#endif // CONFIG_H
