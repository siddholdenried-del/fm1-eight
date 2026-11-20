/* SPDX-License-Identifier: GPL-3.0-only */
/* GhettoMachine: the drum track's two kits (see drums.h). */
#include "drums.h"
#include "drum909.h"
#include "drum808.h"

static drum909_t d909;
static drum808_t d808;
static float k8_l[DRUMS_MAX_BLOCK], k8_r[DRUMS_MAX_BLOCK], k8_rev[DRUMS_MAX_BLOCK], k8_dly[DRUMS_MAX_BLOCK];

/* pad -> the engine's own track */
static const uint8_t PAD808[DRUMS_NPADS] = {D8_BD, D8_SD, D8_LT, D8_MT, D8_HT, D8_RS, D8_CP,
                                            D8_CH, D8_OH, D8_CY, D8_CB};
static const char *const NAME909[DRUMS_NPADS + 1] = {"BD", "SD", "LT", "MT", "HT", "RS", "CP",
                                                     "CH", "OH", "CR", "RD", "KIT"};
static const char *const NAME808[DRUMS_NPADS + 1] = {"BD", "SD", "LT", "MT", "HT", "RS", "CP",
                                                     "CH", "OH", "CY", "CB", "KIT"};

static int voice(int kit, int pad)
{
    if (pad == DRUMS_PAD_KIT)
        return kit == KIT_808 ? D8_KIT : DR_KIT;
    if (pad < 0 || pad >= DRUMS_NPADS)
        return -1;
    return kit == KIT_808 ? PAD808[pad] : pad;
}

void drums_init(void)
{
    drum909_init(&d909);
    drum808_init(&d808);
}

void drums_trigger(int kit, int pad, float vel)
{
    int v = voice(kit, pad);
    if (v < 0 || pad == DRUMS_PAD_KIT)
        return;
    if (vel > 1.0f)
        vel = 1.0f;
    if (kit == KIT_808)                  /* the 808's unaccented hit sits at D8_VEL_NORMAL (as X0X maps it) */
        drum808_trigger(&d808, v, vel >= 0.999f ? 1.0f : vel * (D8_VEL_NORMAL / DRUMS_VEL_NORMAL));
    else
        drum909_trigger(&d909, v, vel);
}

void drums_render(int kit, float *l, float *r, float *rev, float *dly, int n)
{
    int i;
    if (n > DRUMS_MAX_BLOCK)
        n = DRUMS_MAX_BLOCK;
    for (i = 0; i < n; i++)
        l[i] = r[i] = rev[i] = dly[i] = 0.0f;
    if (kit == KIT_909 || drum909_active(&d909))
        drum909_render_st(&d909, l, r, rev, dly, n);
    if (kit == KIT_808 || drum808_active(&d808)) {
        for (i = 0; i < n; i++)
            k8_l[i] = k8_r[i] = k8_rev[i] = k8_dly[i] = 0.0f;
        drum808_render_st(&d808, k8_l, k8_r, k8_rev, k8_dly, n);
        for (i = 0; i < n; i++) {
            l[i] += k8_l[i];
            r[i] += k8_r[i];
            rev[i] += k8_rev[i];
            dly[i] += k8_dly[i];
        }
    }
}

int drums_active(int kit) { return kit == KIT_808 ? drum808_active(&d808) : drum909_active(&d909); }

int drums_nparams(int kit, int pad)
{
    int v = voice(kit, pad);
    if (v < 0)
        return 0;
    return kit == KIT_808 ? drum808_nparams(v) : drum909_nparams(v);
}

const x0x_param_t *drums_param(int kit, int pad, int i)
{
    int v = voice(kit, pad);
    if (v < 0)
        return 0;
    return kit == KIT_808 ? drum808_param(v, i) : drum909_param(v, i);
}

int drums_get(int kit, int pad, int i)
{
    int v = voice(kit, pad);
    if (v < 0)
        return 0;
    return kit == KIT_808 ? drum808_get(&d808, v, i) : drum909_get(&d909, v, i);
}

void drums_set(int kit, int pad, int i, int value)
{
    int v = voice(kit, pad);
    if (v < 0)
        return;
    if (kit == KIT_808)
        drum808_set(&d808, v, i, value);
    else
        drum909_set(&d909, v, i, value);
}

const char *drums_pad_name(int kit, int pad)
{
    if (pad < 0 || pad > DRUMS_NPADS)
        return "";
    return kit == KIT_808 ? NAME808[pad] : NAME909[pad];
}
