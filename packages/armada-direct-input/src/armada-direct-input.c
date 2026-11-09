/* SPDX-License-Identifier: GPL-3.0-or-later */
/* armada-direct-input - extra buttons for the raw rsinput gamepad when the
 * direct controller mode runs without InputPlumber. Writes into the gamepad's
 * own evdev node, so games and Steam see one controller:
 *   left back paddle (BTN_Z on gpio-keys-paddles)  -> BTN_SOUTH (A)
 *   right back paddle (BTN_C on gpio-keys-paddles) -> BTN_EAST (B)
 *   bottom right button (BTN_BACK on the gamepad)  -> Guide + A, which Steam
 *   opens as the Quick Access Menu. SDL maps no gamepad button to BTN_BACK.
 * The paddles are optional; boards without gpio-keys-paddles only get the
 * Quick Access chord.
 * Ported from odin3-paddles in odin3-direct. The Guide + A chord and its 80 ms
 * steps follow InputPlumber's xpad target (src/input/target/xpad.rs,
 * write_event, MIN_CHORD_TIME), https://github.com/ShadowBlip/InputPlumber
 * Exits on any device error so systemd restarts it. */
#include <fcntl.h>
#include <linux/input.h>
#include <poll.h>
#include <stdio.h>
#include <string.h>
#include <time.h>
#include <unistd.h>

#define GAMEPAD_PHYS "rsinput-gamepad/input0"
#define PADDLES_NAME "gpio-keys-paddles"
#define CHORD_STEP_MS 80
#define MAX_QUEUED 8

struct queued_key {
    long long due_ms;
    unsigned short code;
    int value;
};

static struct queued_key queue[MAX_QUEUED];
static int queued;

static long long now_ms(void)
{
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return ts.tv_sec * 1000LL + ts.tv_nsec / 1000000;
}

/* Opens the first event node whose sysfs attribute (name or phys) equals want. */
static int find(const char *attribute, const char *want, int flags)
{
    char path[80], value[128];
    for (int i = 0; i < 64; i++) {
        snprintf(path, sizeof path, "/sys/class/input/event%d/device/%s", i, attribute);
        FILE *f = fopen(path, "r");
        if (!f)
            continue;
        if (!fgets(value, sizeof value, f)) {
            fclose(f);
            continue;
        }
        fclose(f);
        value[strcspn(value, "\n")] = 0;
        if (strcmp(value, want) == 0) {
            snprintf(path, sizeof path, "/dev/input/event%d", i);
            return open(path, flags | O_CLOEXEC);
        }
    }
    return -1;
}

static int send_key(int dst, unsigned short code, int value)
{
    struct input_event out[2];
    memset(out, 0, sizeof out);
    out[0].type = EV_KEY;
    out[0].code = code;
    out[0].value = value;
    out[1].type = EV_SYN;
    out[1].code = SYN_REPORT;
    return write(dst, out, sizeof out) == (ssize_t)sizeof out ? 0 : -1;
}

static void queue_key(long long due_ms, unsigned short code, int value)
{
    if (queued < MAX_QUEUED)
        queue[queued++] = (struct queued_key){ due_ms, code, value };
}

/* Press: Guide now, A one step later. Release: A after two steps, Guide after
 * three, so Steam always sees A inside a held Guide. */
static void queue_quick_access(int pressed)
{
    long long t = now_ms();
    if (pressed) {
        queue_key(t, BTN_MODE, 1);
        queue_key(t + CHORD_STEP_MS, BTN_SOUTH, 1);
    } else {
        queue_key(t + 2 * CHORD_STEP_MS, BTN_SOUTH, 0);
        queue_key(t + 3 * CHORD_STEP_MS, BTN_MODE, 0);
    }
}

static int send_due_keys(int dst)
{
    long long t = now_ms();
    int kept = 0;
    for (int i = 0; i < queued; i++) {
        if (queue[i].due_ms <= t) {
            if (send_key(dst, queue[i].code, queue[i].value) < 0)
                return -1;
        } else {
            queue[kept++] = queue[i];
        }
    }
    queued = kept;
    return 0;
}

static int ms_until_next_key(void)
{
    if (!queued)
        return -1;
    long long next = queue[0].due_ms;
    for (int i = 1; i < queued; i++)
        if (queue[i].due_ms < next)
            next = queue[i].due_ms;
    long long wait = next - now_ms();
    return wait > 0 ? (int)wait : 0;
}

static int handle_paddles(int paddles, int dst)
{
    struct input_event in[64];
    ssize_t n = read(paddles, in, sizeof in);
    if (n <= 0)
        return -1;
    for (size_t i = 0; i < (size_t)n / sizeof *in; i++) {
        if (in[i].type != EV_KEY || in[i].value > 1)
            continue;
        if (in[i].code == BTN_Z && send_key(dst, BTN_SOUTH, in[i].value) < 0)
            return -1;
        if (in[i].code == BTN_C && send_key(dst, BTN_EAST, in[i].value) < 0)
            return -1;
    }
    return 0;
}

static int handle_gamepad(int gamepad)
{
    struct input_event in[64];
    ssize_t n = read(gamepad, in, sizeof in);
    if (n <= 0)
        return -1;
    for (size_t i = 0; i < (size_t)n / sizeof *in; i++)
        if (in[i].type == EV_KEY && in[i].code == BTN_BACK && in[i].value <= 1)
            queue_quick_access(in[i].value);
    return 0;
}

int main(void)
{
    int gamepad = find("phys", GAMEPAD_PHYS, O_RDWR);
    if (gamepad < 0) {
        fprintf(stderr, "no gamepad with phys %s\n", GAMEPAD_PHYS);
        return 1;
    }
    int paddles = find("name", PADDLES_NAME, O_RDONLY);
    struct pollfd fds[2] = {
        { .fd = gamepad, .events = POLLIN },
        { .fd = paddles, .events = POLLIN }, /* poll ignores a negative fd */
    };
    for (;;) {
        if (poll(fds, 2, ms_until_next_key()) < 0)
            return 1;
        if ((fds[0].revents | fds[1].revents) & (POLLERR | POLLHUP | POLLNVAL))
            return 1;
        if ((fds[0].revents & POLLIN) && handle_gamepad(gamepad) < 0)
            return 1;
        if ((fds[1].revents & POLLIN) && handle_paddles(paddles, gamepad) < 0)
            return 1;
        if (send_due_keys(gamepad) < 0)
            return 1;
    }
}
