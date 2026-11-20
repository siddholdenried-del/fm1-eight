/* SPDX-License-Identifier: GPL-3.0-only */
/* fm1-eight's master bus: the mastering stages around X0X's compressor and limiter (fx.c puts them in order):
 *
 *   EQ      a low cut (12 dB/oct), a low shelf, a mid bell and a high shelf: RBJ biquads, transposed direct form II,
 *           before the compressor. A band at 0 dB (the cut at OFF) is skipped, sample for sample.
 *   TAPE    a soft saturation: tanh, its slope at zero kept at 1 (quiet sounds pass as they are, peaks round off);
 *           WARMTH tilts it for even harmonics (a DC trap after); TONE a gentle high roll-off; MIX dry / wet.
 *   STEREO  WIDTH by mid / side (0 % mono .. 200 %), BASS MONO (the side high-passed: the lows centred), BALANCE.
 *   meters  short-term loudness (ITU-R BS.1770 K-weighting, 3 s, LUFS; momentary 400 ms) and the correlation of the
 *           two sides, on the output: only while the screen shows them (mbus_meter_on).
 *
 * Its own unit (fm1.toml o2): X0X's fastmath.h never meets the platform's headers.
 * Threading: mbus_set runs between render blocks (the main loop inside plat_lock()); the processing in the audio
 * interrupt; mbus_eq_db, mbus_lufs and mbus_corr read from the main loop. */
#pragma once
#include <stdint.h>
#include "x0x_param.h"

enum {
    MB_EQ_LOW, MB_EQ_MID, MB_EQ_HIGH, MB_EQ_CUT,          /* page EQ: the gains (0.5 dB steps, 24 = 0 dB), the low cut */
    MB_EQ_LFREQ, MB_EQ_MFREQ, MB_EQ_MQ, MB_EQ_HFREQ,      /* page EQ 2: where they sit */
    MB_TP_DRIVE, MB_TP_WARM, MB_TP_TONE, MB_TP_MIX,       /* page TAPE */
    MB_ST_WIDTH, MB_ST_BASS, MB_ST_BAL,                   /* page STEREO */
    MB_NPARAMS
};

typedef struct {
    float b0, b1, b2, a1, a2;
    float z1[2], z2[2];                   /* each side's state */
} mb_bq_t;

#define MB_LU_BLOCKS 30                   /* short-term loudness: 30 blocks of 100 ms */

typedef struct {
    uint8_t pot[MB_NPARAMS];
    /* EQ: the low cut, low shelf, mid bell, high shelf; a bit each while it is on */
    mb_bq_t eq[4];
    uint8_t eq_on;
    /* TAPE */
    float drive, bias, tb, norm;          /* input gain; WARMTH's offset, its tanh, 1 / the slope at zero */
    float tone_a, mix;                    /* the roll-off's one-pole coefficient (0: open); wet share */
    float lp[2], dc_x[2], dc_y[2];
    uint8_t tape_on;
    /* STEREO */
    float width, bal_l, bal_r;
    mb_bq_t side_hp;                      /* BASS MONO: the side's high-pass (one side's state used) */
    uint8_t st_on, bass_on;
    /* meters */
    volatile uint8_t meter_on;
    mb_bq_t kw[2];                        /* K-weighting: the head's shelf, then the high-pass */
    float lu_acc;                         /* this block's sum of the weighted power */
    int lu_n;                             /* its samples so far */
    float lu_blk[MB_LU_BLOCKS];           /* the last 3 s, a block each 100 ms */
    int lu_pos, lu_have;
    float c_lr, c_ll, c_rr;               /* the correlation's running averages */
} mbus_t;

void mbus_init(mbus_t *m);
int mbus_nparams(void);
const x0x_param_t *mbus_param(int i);
void mbus_set(mbus_t *m, int i, int v);
int mbus_get(const mbus_t *m, int i);
void mbus_format(const mbus_t *m, int i, char *buf);   /* in its unit ("+3.0dB", "120Hz", "1.2k", "140%"); 16 bytes */
/* in place, stereo (the audio interrupt): before the compressor, the EQ; after it, TAPE and STEREO; on the output,
 * the meters (only while meter_on) */
void mbus_eq(mbus_t *m, float *l, float *r, int n);
void mbus_tape_stereo(mbus_t *m, float *l, float *r, int n);
void mbus_meter(mbus_t *m, const float *l, const float *r, int n);
void mbus_meter_on(mbus_t *m, int on);   /* on from off: the meters start again from silence */
/* the screen's (main loop): the EQ's response at hz, dB; the loudness, LUFS (short-term 3 s, or momentary 400 ms;
 * -70 for silence or not yet measured); the correlation -1..1 */
float mbus_eq_db(const mbus_t *m, float hz);
float mbus_lufs(const mbus_t *m, int momentary);
float mbus_corr(const mbus_t *m);
int mbus_active(const mbus_t *m, int stage);   /* 0 EQ, 1 TAPE, 2 STEREO: doing anything */
