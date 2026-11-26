/* SPDX-License-Identifier: GPL-3.0-or-later */
/*
 * armada-direct-motion - feed the Snapdragon Sensor Core IMU into the rsinput
 * "Motion Sensors" node (rsinput motion_sensors=1).
 *
 * libssc and GLib are loaded at runtime with the same sonames and calls as
 * InputPlumber's src/drivers/ssc/bindings.rs and runtime.rs
 * (ShadowBlip/InputPlumber PR #590 as patched by Armada,
 * packages/inputplumber/patches/0005). libssc reports m/s^2 and rad/s.
 * Samples are rotated by a mount matrix into SDL's axes (X right, Y top,
 * Z toward the player) and written as EV_ABS events into the motion node,
 * scaled by the resolutions rsinput sets (4096 per g, 16 per deg/s).
 *
 * Usage: armada-direct-motion [--raw] [--rate HZ] [--matrix a,b,c,d,e,f,g,h,i]
 *                       [--accel-offset x,y,z] [--accel-scale x,y,z]
 *   --raw           print unrotated samples instead of writing them
 *   --matrix        row-major 3x3 matrix, output = matrix * libssc vector
 *   --accel-offset  per-axis accelerometer offset in m/s^2, sensor axes
 *   --accel-scale   per-axis accelerometer gain, sensor axes; applied as
 *                   (reading - offset) * scale before the matrix. Both come
 *                   from a six-position calibration (each axis up and down).
 */
#include <dirent.h>
#include <dlfcn.h>
#include <fcntl.h>
#include <linux/input.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>

#define ACCEL_RES_PER_G   4096.0
#define GYRO_RES_PER_DPS  16.0
#define STANDARD_GRAVITY  9.80665
#define MOTION_PHYS       "rsinput-gamepad/input1"

typedef struct { unsigned int domain; int code; char *message; } GError;
typedef int (*FnIteration)(void *context, int may_block);
typedef void (*FnSignalConnect)(void *instance, const char *signal, void (*handler)(void),
                                void *data, void *destroy, unsigned int flags);
typedef void *(*FnSensorNew)(void *cancellable, GError **error);
typedef unsigned int (*FnSensorOpen)(void *sensor, void *cancellable, GError **error);
typedef void (*FnSetRate)(void *sensor, float rate);

enum sensor_kind { ACCEL, GYRO };

static int motion_fd = -1;
static int raw_mode;
static double matrix[9] = { 1, 0, 0, 0, 1, 0, 0, 0, 1 };
static double accel_offset[3] = { 0, 0, 0 };
static double accel_scale[3] = { 1, 1, 1 };

static void *load(const char *soname)
{
    void *handle = dlopen(soname, RTLD_NOW | RTLD_GLOBAL);
    if (!handle) {
        fprintf(stderr, "dlopen %s: %s\n", soname, dlerror());
        exit(1);
    }
    return handle;
}

static void *symbol(void *handle, const char *name, int required)
{
    void *sym = dlsym(handle, name);
    if (!sym && required) {
        fprintf(stderr, "missing symbol %s\n", name);
        exit(1);
    }
    return sym;
}

static int open_motion_node(void)
{
    char path[300], phys[64];
    DIR *dir = opendir("/sys/class/input");
    struct dirent *entry;
    int fd = -1;
    while (dir && (entry = readdir(dir)) && fd < 0) {
        if (strncmp(entry->d_name, "event", 5) != 0)
            continue;
        snprintf(path, sizeof path, "/sys/class/input/%s/device/phys", entry->d_name);
        FILE *f = fopen(path, "r");
        if (!f)
            continue;
        if (fgets(phys, sizeof phys, f) && strncmp(phys, MOTION_PHYS, strlen(MOTION_PHYS)) == 0) {
            snprintf(path, sizeof path, "/dev/input/%s", entry->d_name);
            fd = open(path, O_WRONLY | O_CLOEXEC);
        }
        fclose(f);
    }
    if (dir)
        closedir(dir);
    return fd;
}

static void write_sample(unsigned int first_axis, const double counts[3])
{
    struct input_event ev[5];
    struct timespec ts;
    memset(ev, 0, sizeof ev);
    for (int i = 0; i < 3; i++) {
        ev[i].type = EV_ABS;
        ev[i].code = first_axis + i;
        ev[i].value = (int)lround(counts[i]);
    }
    clock_gettime(CLOCK_MONOTONIC, &ts);
    ev[3].type = EV_MSC;
    ev[3].code = MSC_TIMESTAMP;
    ev[3].value = (int)(ts.tv_sec * 1000000LL + ts.tv_nsec / 1000);
    ev[4].type = EV_SYN;
    ev[4].code = SYN_REPORT;
    if (write(motion_fd, ev, sizeof ev) != (ssize_t)sizeof ev) {
        perror("write motion node");
        exit(1);
    }
}

static void on_measurement(void *sensor, float x, float y, float z, void *data)
{
    enum sensor_kind kind = (enum sensor_kind)(long)data;
    double in[3] = { x, y, z };
    double out[3];
    (void)sensor;
    if (raw_mode) {
        printf("%s %.4f %.4f %.4f\n", kind == ACCEL ? "accel" : "gyro", x, y, z);
        fflush(stdout);
        return;
    }
    if (kind == ACCEL)
        for (int i = 0; i < 3; i++)
            in[i] = (in[i] - accel_offset[i]) * accel_scale[i];
    for (int r = 0; r < 3; r++) {
        out[r] = matrix[r * 3] * in[0] + matrix[r * 3 + 1] * in[1] + matrix[r * 3 + 2] * in[2];
        out[r] *= kind == ACCEL ? ACCEL_RES_PER_G / STANDARD_GRAVITY : GYRO_RES_PER_DPS * 180.0 / M_PI;
    }
    write_sample(kind == ACCEL ? ABS_X : ABS_RX, out);
}

static void parse_vector(const char *text, double vec[3], const char *option)
{
    if (sscanf(text, "%lf,%lf,%lf", &vec[0], &vec[1], &vec[2]) != 3) {
        fprintf(stderr, "%s needs 3 comma-separated numbers\n", option);
        exit(2);
    }
}

static void parse_args(int argc, char **argv, float *rate)
{
    for (int i = 1; i < argc; i++) {
        if (strcmp(argv[i], "--raw") == 0) {
            raw_mode = 1;
        } else if (strcmp(argv[i], "--rate") == 0 && i + 1 < argc) {
            *rate = strtof(argv[++i], NULL);
        } else if (strcmp(argv[i], "--matrix") == 0 && i + 1 < argc) {
            if (sscanf(argv[++i], "%lf,%lf,%lf,%lf,%lf,%lf,%lf,%lf,%lf", &matrix[0], &matrix[1], &matrix[2],
                       &matrix[3], &matrix[4], &matrix[5], &matrix[6], &matrix[7], &matrix[8]) != 9) {
                fprintf(stderr, "--matrix needs 9 comma-separated numbers\n");
                exit(2);
            }
        } else if (strcmp(argv[i], "--accel-offset") == 0 && i + 1 < argc) {
            parse_vector(argv[++i], accel_offset, "--accel-offset");
        } else if (strcmp(argv[i], "--accel-scale") == 0 && i + 1 < argc) {
            parse_vector(argv[++i], accel_scale, "--accel-scale");
        } else {
            fprintf(stderr, "usage: %s [--raw] [--rate HZ] [--matrix a,b,c,d,e,f,g,h,i] "
                            "[--accel-offset x,y,z] [--accel-scale x,y,z]\n", argv[0]);
            exit(2);
        }
    }
}

int main(int argc, char **argv)
{
    float rate = 200.0f;
    parse_args(argc, argv, &rate);
    if (!raw_mode && (motion_fd = open_motion_node()) < 0) {
        fprintf(stderr, "no input node with phys %s; load rsinput with motion_sensors=1\n", MOTION_PHYS);
        return 1;
    }
    void *glib = load("libglib-2.0.so.0");
    void *gobject = load("libgobject-2.0.so.0");
    load("libgio-2.0.so.0");
    void *ssc = load("libssc.so.2");
    FnIteration iterate = symbol(glib, "g_main_context_iteration", 1);
    FnSignalConnect connect = symbol(gobject, "g_signal_connect_data", 1);
    FnSetRate set_rate = symbol(ssc, "ssc_sensor_set_sample_rate", 0);
    const char *names[2][2] = {
        { "ssc_sensor_accelerometer_new_sync", "ssc_sensor_accelerometer_open_sync" },
        { "ssc_sensor_gyroscope_new_sync", "ssc_sensor_gyroscope_open_sync" },
    };
    for (long kind = ACCEL; kind <= GYRO; kind++) {
        GError *error = NULL;
        void *sensor = ((FnSensorNew)symbol(ssc, names[kind][0], 1))(NULL, &error);
        if (!sensor) {
            fprintf(stderr, "%s: %s\n", names[kind][0], error ? error->message : "failed");
            return 1;
        }
        if (set_rate)
            set_rate(sensor, rate);
        connect(sensor, "measurement", (void (*)(void))on_measurement, (void *)kind, NULL, 0);
        if (!((FnSensorOpen)symbol(ssc, names[kind][1], 1))(sensor, NULL, &error)) {
            fprintf(stderr, "%s: %s\n", names[kind][1], error ? error->message : "failed");
            return 1;
        }
    }
    fprintf(stderr, "armada-direct-motion: accelerometer and gyroscope open at %.0f Hz%s\n", rate, raw_mode ? " (raw)" : "");
    for (;;)
        iterate(NULL, 1);
}
