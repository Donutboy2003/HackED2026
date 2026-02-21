#ifndef ADXL343_H
#define ADXL343_H

#include <cstdint>

struct Vector3 {
    float x, y, z;
};

class Adxl343 {
public:
    explicit Adxl343(const char* i2c_device, int address);
    ~Adxl343();

    bool init();
    Vector3 readAccel();
    float getRoll(Vector3 a);
    float getPitch(Vector3 a);

private:
    const char* _device;
    int         _address;
    int         _fd;            // open file descriptor for /dev/i2c-X

    bool  writeRegister(uint8_t reg, uint8_t value);
    bool  readRegisters(uint8_t reg, uint8_t* buf, int len);
};

#endif // ADXL343_H
