#include <stdio.h>
#include <math.h>
#include "pico/stdlib.h"
#include "hardware/i2c.h"
#include "config.h"
#include "adxl343.h"

// -- GLOBALS --
float roll_offset = 0.0f;
float pitch_offset = 0.0f;
float filtered_roll = 0.0f;
float filtered_pitch = 0.0f;

int main() {
    stdio_init_all();
    sleep_ms(2000);

    Adxl343 sensor(I2C_PORT, I2C_SDA_PIN, I2C_SCL_PIN);
    if (!sensor.init()) {
        while (1) { tight_loop_contents(); }
    }

    // CALIBRATION
    float sum_r = 0, sum_p = 0;
    for (int i = 0; i < 50; i++) {
        Vector3 v = sensor.readAccel();
        sum_r += sensor.getRoll(v);
        sum_p += sensor.getPitch(v);
        sleep_ms(20);
    }
    roll_offset = sum_r / 50.0f;
    pitch_offset = sum_p / 50.0f;
    sleep_ms(1000);

    // MAIN LOOP — just stream roll,pitch
    while (true) {
        Vector3 v = sensor.readAccel();
        float raw_roll  = sensor.getRoll(v)  - roll_offset;
        float raw_pitch = sensor.getPitch(v) - pitch_offset;

        filtered_roll  = (filtered_roll  * 0.8f) + (raw_roll  * 0.2f);
        filtered_pitch = (filtered_pitch * 0.8f) + (raw_pitch * 0.2f);

        // Protocol: roll,pitch
        printf("%.4f,%.4f\n", filtered_roll, filtered_pitch);

        sleep_ms(16);
    }

    return 0;
}
