#ifndef ADXL343_H
#define ADXL343_H

#include <stdio.h>
#include "pico/stdlib.h"
#include "hardware/i2c.h"
#include "config.h"
#include <math.h>

// A simple struct to hold our 3D vector
struct Vector3 {
    float x;
    float y;
    float z;
};

class Adxl343 {
public:
    // Constructor
    Adxl343(i2c_inst_t *i2c, uint sda, uint scl);

    // Initialize the sensor (Turn on measurement mode)
    bool init();

    // Read raw acceleration data (returns G-force values)
    Vector3 readAccel();

    // Convert raw data into Roll (Tilt Left/Right) in Radians
    float getRoll(Vector3 accel);

    // Convert raw data into Pitch (Nod Up/Down) in Radians
    float getPitch(Vector3 accel);

private:
    i2c_inst_t *_i2c;
    uint _sda;
    uint _scl;

    // Helper to write to a register
    void writeRegister(uint8_t reg, uint8_t value);
    
    // Helper to read from a register
    void readRegisters(uint8_t reg, uint8_t *buf, uint8_t len);
};

#endif // ADXL343_H
