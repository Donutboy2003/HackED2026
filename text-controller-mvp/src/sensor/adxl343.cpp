#include "adxl343.h"
#include <math.h>

// Constructor: Configure the I2C instance
Adxl343::Adxl343(i2c_inst_t *i2c, uint sda, uint scl) {
    _i2c = i2c;
    _sda = sda;
    _scl = scl;
}

bool Adxl343::init() {
    // 1. Initialize I2C Hardware
    i2c_init(_i2c, 400 * 1000);
    gpio_set_function(_sda, GPIO_FUNC_I2C);
    gpio_set_function(_scl, GPIO_FUNC_I2C);
    
    // Enable pull-ups on I2C pins (critical for stability)
    gpio_pull_up(_sda);
    gpio_pull_up(_scl);

    sleep_ms(100); // Give sensor time to boot

    // 2. Wake up the ADXL343 (It starts in Sleep Mode)
    // Write 0x08 to Power Control Register (0x2D) to enable "Measurement Mode"
    uint8_t power_ctl = 0x2D;
    uint8_t measure_mode = 0x08;
    
    uint8_t buf[] = {power_ctl, measure_mode};
    int ret = i2c_write_blocking(_i2c, ADXL343_ADDR, buf, 2, false);

    if (ret < 0) {
        printf("ADXL343 Init Failed! Check wiring.\n");
        return false;
    }

    printf("ADXL343 Initialized.\n");
    return true;
}

Vector3 Adxl343::readAccel() {
    uint8_t reg = 0x32; // Start reading from DATAX0
    uint8_t buffer[6];

    // Read 6 bytes: X_L, X_H, Y_L, Y_H, Z_L, Z_H
    i2c_write_blocking(_i2c, ADXL343_ADDR, &reg, 1, true); // True to keep master control
    i2c_read_blocking(_i2c, ADXL343_ADDR, buffer, 6, false);

    // Convert 2 bytes into a 16-bit integer (Little Endian)
    int16_t x = (buffer[1] << 8) | buffer[0];
    int16_t y = (buffer[3] << 8) | buffer[2];
    int16_t z = (buffer[5] << 8) | buffer[4];

    // Scale to G-Force (Default sensitivity is roughly 256 LSB/g)
    // We keep it raw-ish but normalized for math
    Vector3 v;
    v.x = (float)x / 256.0f;
    v.y = (float)y / 256.0f;
    v.z = (float)z / 256.0f;

    return v;
}

// Calculate Roll (Tilt Left/Right)
// Returns angle in Radians. 
// +Roll = Tilted Right, -Roll = Tilted Left
float Adxl343::getRoll(Vector3 a) {
    return atan2(a.y, a.z);
}

// Calculate Pitch (Nod Up/Down)
// Returns angle in Radians.
// +Pitch = Tilted Back, -Pitch = Tilted Forward (Nod)
float Adxl343::getPitch(Vector3 a) {
    // Note: We use sqrt(y*y + z*z) to stabilize pitch even if rolled
    return atan2(-a.x, sqrt(a.y * a.y + a.z * a.z));
}
