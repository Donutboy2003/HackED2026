#include <cstdio>
#include <cmath>
#include <unistd.h>     // usleep
#include "config.h"
#include "adxl343.h"

static float roll_offset  = 0.0f;
static float pitch_offset = 0.0f;
static float filtered_roll  = 0.0f;
static float filtered_pitch = 0.0f;

int main() {
    Adxl343 sensor(I2C_DEVICE, ADXL343_ADDR);
    if (!sensor.init()) return 1;

    // --- Calibration: 50-sample average ---
    float sum_r = 0, sum_p = 0;
    for (int i = 0; i < 50; i++) {
        Vector3 v = sensor.readAccel();
        sum_r += sensor.getRoll(v);
        sum_p += sensor.getPitch(v);
        usleep(20'000); // 20 ms
    }
    roll_offset  = sum_r / 50.0f;
    pitch_offset = sum_p / 50.0f;
    usleep(1'000'000); // 1 s settle

    // --- Main loop: stream roll,pitch to stdout ---
    while (true) {
        Vector3 v = sensor.readAccel();
        float raw_roll  = sensor.getRoll(v)  - roll_offset;
        float raw_pitch = sensor.getPitch(v) - pitch_offset;

        filtered_roll  = filtered_roll  * 0.8f + raw_roll  * 0.2f;
        filtered_pitch = filtered_pitch * 0.8f + raw_pitch * 0.2f;

        // Same wire protocol as the Pico version
        printf("%.4f,%.4f\n", filtered_roll, filtered_pitch);
        fflush(stdout);     // essential — Python reads line-by-line

        usleep(16'000); // ~60 Hz
    }

    return 0;
}
