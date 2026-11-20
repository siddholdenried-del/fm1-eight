/* SPDX-License-Identifier: GPL-3.0-only */
/* GhettoMachine: the few maths functions the screen's curves need (filter responses, the tape curve, dB), from X0X's
 * fastmath.h in a unit of their own (fm1.toml o2), so fastmath never meets the platform's headers in app.c. */
#pragma once
float um_exp2(float x);
float um_log2(float x);
float um_sin(float x);                     /* radians */
float um_tanh(float x);
float um_db(float lin);                    /* 20 log10; -120 for 0 */
float um_sqrt(float x);
