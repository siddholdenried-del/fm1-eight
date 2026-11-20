/* SPDX-License-Identifier: GPL-3.0-only */
/* fm1-eight: see uimath.h */
#include "uimath.h"
#include "fastmath.h"

float um_exp2(float x) { return fm_exp2f(x); }
float um_log2(float x) { return x > 0.0f ? fm_log2f(x) : -200.0f; }
float um_sin(float x) { return fm_sinf(x); }
float um_tanh(float x) { return fm_tanhf(x); }
float um_db(float lin) { return lin > 1e-6f ? 6.0206f * fm_log2f(lin) : -120.0f; }
float um_sqrt(float x) { return fm_sqrtf(x); }
