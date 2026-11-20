/* SPDX-License-Identifier: MPL-2.0
 * Copyright (C) 2026 Charles Vestal (fm1-base's template, which this starts from) */
/* fm1-eight: four tracks, the drums and T2..T4. The app's half of the contract with the platform
 * (device/unity.c, host/plat_host.c). */
#pragma once
#include <stdint.h>
#include "plat.h"

#define APP_NAME "EIGHT"
#define APP_SPLASH_RGB RGB(255, 120, 40)
#define APP_BLOCK 256u                   /* frames per audio block: 5.8 ms at 44.1 kHz */
#define APP_TOUCH                        /* velocity from the keys (lib/touch.h): played pads */

/* the store: the user presets (sounds and kits; the project itself is a file, app.c PROJ_FILE),
 * the panel calibration (the platform's) and Bluetooth's slot (unused: no radio in this build), and their offsets */
enum { OBJ_USER, OBJ_PANEL, OBJ_BLE, OBJ_NOBJ };   /* OBJ_USER: the user presets (app.c user_t) */
#define APP_STORE_MAP {0xFC000u, 0xDC000u, 0xDE000u}

/* the companion's files (fm1.toml companion = true): none yet (the samples come in phase 3); it also brings
 * plat_file_*, which keeps the project */
#define APP_FILES
int app_file(uint32_t i, plat_file_info_t *f);
int app_file_read(uint32_t i, uint32_t off, uint8_t *dst, uint32_t n);
int app_file_begin(uint32_t i, uint32_t size);
int app_file_write(uint32_t i, uint32_t off, const uint8_t *src, uint32_t n);
int app_file_commit(uint32_t i, uint32_t size, uint32_t crc);
int app_file_delete(uint32_t i);
int app_file_busy(void);                 /* 1: no file written now (playing, or sampling) */

/* the contract: the platform calls these */
void app_init(void);                     /* boot: the engines, then the saved project (or the default one) */
void app_render(int32_t *lr, uint32_t n, uint32_t master_q12);   /* audio interrupt: n stereo frames, 24-bit */
void app_panic(void);                    /* silence now (before an update rewrites the flash) */
void app_ui_init(void);                  /* the first screen, after the splash */
void app_frame(void);                    /* the UI: input and a redraw, about 60 times a second */
void app_input_only(void);               /* between frames: input only */
void app_say(const char *a, const char *b);   /* a short message on the screen and to a screen reader */

/* the host simulator's checks (host/plat_host.c "expect") */
#define APP_HOST_EXPECT
int app_expect(const char *what, int *got);
