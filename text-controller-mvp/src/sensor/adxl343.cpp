#include "adxl343.h"
#include "config.h"

#include <cstdio>
#include <cmath>
#include <fcntl.h>
#include <unistd.h>
#include <sys/ioctl.h>
#include <linux/i2c-dev.h>

Adxl343::Adxl343(const char* i2c_device, int address)
    : _device(i2c_device), _address(address), _fd(-1) {}

Adxl343::~Adxl343() {
    if (_fd >= 0) close(_fd);
}

bool Adxl343::init() {
    // Open the I2C bus
    _fd = open(_device, O_RDWR);
    if (_fd < 0) {
        perror("Failed to open I2C device");
        return false;
    }

    // Claim the slave address
    if (ioctl(_fd, I2C_SLAVE, _address) < 0) {
        perror("Failed to set I2C slave address");
        return false;
    }

    usleep(100'000); // 100 ms boot time

    // Wake up: set Measurement Mode in POWER_CTL (0x2D)
    if (!writeRegister(REG_POWER_CTL, 0x08)) {
        fprintf(stderr, "ADXL343 Init Failed — check wiring and I2C address.\n");
        return false;
    }

    fprintf(stderr, "ADXL343 Initialized on %s @ 0x%02X\n", _device, _address);
    return true;
}

Vector3 Adxl343::readAccel() {
    uint8_t buf[6] = {};
    readRegisters(REG_DATAX0, buf, 6);

    int16_t x = static_cast<int16_t>((buf[1] << 8) | buf[0]);
    int16_t y = static_cast<int16_t>((buf[3] << 8) | buf[2]);
    int16_t z = static_cast<int16_t>((buf[5] << 8) | buf[4]);

    return { x / 256.0f, y / 256.0f, z / 256.0f };
}

float Adxl343::getRoll(Vector3 a) {
    return atan2f(a.y, a.z);
}

float Adxl343::getPitch(Vector3 a) {
    return atan2f(-a.x, sqrtf(a.y * a.y + a.z * a.z));
}

// ── Private helpers ────────────────────────────────────────────────────────

bool Adxl343::writeRegister(uint8_t reg, uint8_t value) {
    uint8_t buf[2] = { reg, value };
    return write(_fd, buf, 2) == 2;
}

bool Adxl343::readRegisters(uint8_t reg, uint8_t* buf, int len) {
    // Write register pointer, then read back `len` bytes
    if (write(_fd, &reg, 1) != 1) return false;
    return read(_fd, buf, len) == len;
}
