/* fm1-eight's master bus stages (dsp/mbus.c) and the limiter (dsp/master.c), measured with sines:
 *   cc -std=c99 -O2 -ffp-contract=off -Iapp/dsp app/tests/mbus_unit.c app/dsp/mbus.c app/dsp/master.c -lm -o mbus_unit
 *   ./mbus_unit            (exit 0: every check passed; it prints each)
 * The EQ's response is checked against its own drawn curve (mbus_eq_db) and against the cookbook's targets; TAPE,
 * STEREO, the limiter's ceiling and the loudness meter against what they should do. Last, the chain's cost on this
 * computer against X0X's master alone (a ratio: the FM-1 is slower, the ratio is what carries over). */
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include "mbus.h"
#include "master.h"

#define FS 44100.0
#define N 256
static int fails, checks;

static void check(int ok, const char *what, double got, double lo, double hi)
{
    checks++;
    if (!ok)
        fails++;
    printf("  %s %-58s %9.3f  [%g .. %g]\n", ok ? "ok  " : "FAIL", what, got, lo, hi);
}
static void within(const char *what, double got, double lo, double hi) { check(got >= lo && got <= hi, what, got, lo, hi); }

/* a sine through the EQ (both sides), its gain in dB once settled */
static double eq_gain(mbus_t *m, double hz, double amp)
{
    static float l[N], r[N];
    double ph = 0.0, in2 = 0.0, out2 = 0.0;
    int b, i;
    for (b = 0; b < 400; b++) {           /* 2.3 s: the lowest band (20 Hz) settles */
        for (i = 0; i < N; i++) {
            l[i] = r[i] = (float)(amp * sin(ph));
            ph += 2.0 * M_PI * hz / FS;
        }
        if (b >= 200)
            for (i = 0; i < N; i++)
                in2 += (double)l[i] * l[i];
        mbus_eq(m, l, r, N);
        if (b >= 200)
            for (i = 0; i < N; i++)
                out2 += (double)l[i] * l[i];
    }
    return 10.0 * log10(out2 / in2);
}

static void eq_case(const char *name, int pots[][2], int np, const double (*pts)[3], int npts)
{
    mbus_t m;
    int i;
    char t[96];
    mbus_init(&m);
    for (i = 0; i < np; i++)
        mbus_set(&m, pots[i][0], pots[i][1]);
    for (i = 0; i < npts; i++) {
        double g = eq_gain(&m, pts[i][0], 0.25), d = mbus_eq_db(&m, (float)pts[i][0]);
        snprintf(t, sizeof t, "%s: %g Hz, dB", name, pts[i][0]);
        within(t, g, pts[i][1], pts[i][2]);
        snprintf(t, sizeof t, "%s: %g Hz, the drawn curve - measured", name, pts[i][0]);
        within(t, d - g, -0.15, 0.15);
    }
}

static double goertzel(const float *x, int n, double hz)
{
    double w = 2.0 * M_PI * hz / FS, c = 2.0 * cos(w), s1 = 0.0, s2 = 0.0;
    int i;
    for (i = 0; i < n; i++) {
        double s = x[i] + c * s1 - s2;
        s2 = s1;
        s1 = s;
    }
    return sqrt(s1 * s1 + s2 * s2 - c * s1 * s2) * 2.0 / n;
}

int main(void)
{
    /* ---- EQ */
    {
        int flat[1][2] = {{MB_EQ_LOW, 24}};
        int low[2][2] = {{MB_EQ_LOW, 36}, {MB_EQ_LFREQ, 2}};             /* +6 dB, 80 Hz */
        int mid[3][2] = {{MB_EQ_MID, 12}, {MB_EQ_MFREQ, 61}, {MB_EQ_MQ, 3}};   /* -6 dB, 1 kHz, Q 1.4 */
        int high[2][2] = {{MB_EQ_HIGH, 32}, {MB_EQ_HFREQ, 5}};           /* +4 dB, 8 kHz */
        int cut[1][2] = {{MB_EQ_CUT, 8}};                                 /* 100 Hz */
        const double pflat[][3] = {{50, -0.01, 0.01}, {1000, -0.01, 0.01}};
        const double plow[][3] = {{25, 5.4, 6.1}, {80, 2.5, 3.5}, {2000, -0.1, 0.1}};
        const double pmid[][3] = {{1000, -6.1, -5.9}, {150, -0.4, 0.0}, {8000, -0.4, 0.0}};
        const double phigh[][3] = {{16000, 3.5, 4.1}, {8000, 1.5, 2.5}, {200, -0.1, 0.1}};
        const double pcut[][3] = {{50, -13.0, -11.5}, {100, -3.3, -2.7}, {1000, -0.1, 0.0}};
        eq_case("EQ flat", flat, 1, pflat, 2);
        eq_case("LOW +6 dB at 80 Hz", low, 2, plow, 3);
        eq_case("MID -6 dB at 1 kHz, Q 1.4", mid, 3, pmid, 3);
        eq_case("HIGH +4 dB at 8 kHz", high, 2, phigh, 3);
        eq_case("LOW CUT 100 Hz", cut, 1, pcut, 3);
        {   /* all flat: the stage leaves the samples as they are, bit for bit */
            mbus_t m;
            float l[N], r[N], l0[N];
            int i, same = 1;
            mbus_init(&m);
            for (i = 0; i < N; i++)
                l[i] = r[i] = l0[i] = (float)(0.5 * sin(i * 0.1));
            mbus_eq(&m, l, r, N);
            mbus_tape_stereo(&m, l, r, N);
            for (i = 0; i < N; i++)
                same &= l[i] == l0[i] && r[i] == l0[i];
            within("all flat: EQ, TAPE, STEREO leave it bit for bit", same, 1, 1);
        }
    }
    /* ---- TAPE: unity for quiet sounds, peaks rounded, WARMTH's even harmonics without DC, TONE's roll-off */
    {
        static float l[44100], r[44100];
        mbus_t m;
        int i;
        double q, loud, h2, h3, dc = 0.0;
        mbus_init(&m);
        mbus_set(&m, MB_TP_DRIVE, 95);        /* +9 dB */
        for (i = 0; i < 44100; i++)
            l[i] = r[i] = (float)(0.01 * sin(2 * M_PI * 440 * i / FS));
        for (i = 0; i < 44100; i += N)
            mbus_tape_stereo(&m, l + i, r + i, 44100 - i < N ? 44100 - i : N);
        q = 20 * log10(goertzel(l + 22050, 22050, 440) / 0.01);
        within("TAPE +9 dB: a -40 dBFS sine passes, dB", q, -0.1, 0.1);
        for (i = 0; i < 44100; i++)
            l[i] = r[i] = (float)(0.89 * sin(2 * M_PI * 440 * i / FS));
        for (i = 0; i < 44100; i += N)
            mbus_tape_stereo(&m, l + i, r + i, 44100 - i < N ? 44100 - i : N);
        loud = 0.0;
        for (i = 22050; i < 44100; i++)
            loud = fmax(loud, fabs(l[i]));
        within("TAPE +9 dB: a -1 dBFS sine's peak, dB", 20 * log10(loud / 0.89), -12.0, -3.0);
        h3 = 20 * log10(goertzel(l + 22050, 22050, 1320) / goertzel(l + 22050, 22050, 440));
        within("TAPE +9 dB: its 3rd harmonic, dBc", h3, -40.0, -6.0);
        mbus_set(&m, MB_TP_WARM, 127);
        for (i = 0; i < 44100; i++)
            l[i] = r[i] = (float)(0.5 * sin(2 * M_PI * 440 * i / FS));
        for (i = 0; i < 44100; i += N)
            mbus_tape_stereo(&m, l + i, r + i, 44100 - i < N ? 44100 - i : N);
        h2 = 20 * log10(goertzel(l + 22050, 22050, 880) / goertzel(l + 22050, 22050, 440));
        within("TAPE + WARMTH: its 2nd harmonic, dBc", h2, -40.0, -10.0);
        for (i = 22050; i < 44100; i++)
            dc += l[i];
        within("TAPE + WARMTH: DC after the trap", fabs(dc / 22050), 0.0, 0.002);
        mbus_init(&m);
        mbus_set(&m, MB_TP_TONE, 34);         /* 5 kHz */
        for (i = 0; i < 44100; i++)
            l[i] = r[i] = (float)(0.25 * (sin(2 * M_PI * 200 * i / FS) + sin(2 * M_PI * 12000 * i / FS)));
        for (i = 0; i < 44100; i += N)
            mbus_tape_stereo(&m, l + i, r + i, 44100 - i < N ? 44100 - i : N);
        within("TONE 5k: 200 Hz, dB", 20 * log10(goertzel(l + 22050, 22050, 200) / 0.25), -0.3, 0.0);
        within("TONE 5k: 12 kHz, dB", 20 * log10(goertzel(l + 22050, 22050, 12000) / 0.25), -12.0, -5.0);
    }
    /* ---- STEREO */
    {
        static float l[44100], r[44100];
        mbus_t m;
        int i;
        double d = 0.0, side_lo, side_hi;
        mbus_init(&m);
        mbus_set(&m, MB_ST_WIDTH, 0);
        for (i = 0; i < 4096; i++) {
            l[i] = (float)sin(i * 0.05);
            r[i] = (float)sin(i * 0.031);
        }
        mbus_tape_stereo(&m, l, r, 4096);
        for (i = 0; i < 4096; i++)
            d = fmax(d, fabs(l[i] - r[i]));
        within("WIDTH 0 %: the sides the same", d, 0.0, 0.0);
        mbus_init(&m);
        mbus_set(&m, MB_ST_BASS, 4);          /* 120 Hz */
        for (i = 0; i < 44100; i++) {         /* all side: 40 Hz and 2 kHz, out of phase */
            double s = 0.3 * sin(2 * M_PI * 40 * i / FS) + 0.3 * sin(2 * M_PI * 2000 * i / FS);
            l[i] = (float)s;
            r[i] = (float)-s;
        }
        for (i = 0; i < 44100; i += N)
            mbus_tape_stereo(&m, l + i, r + i, 44100 - i < N ? 44100 - i : N);
        side_lo = 20 * log10(goertzel(l + 22050, 22050, 40) / 0.3);
        side_hi = 20 * log10(goertzel(l + 22050, 22050, 2000) / 0.3);
        within("BASS MONO 120 Hz: the side at 40 Hz, dB", side_lo, -60.0, -15.0);
        within("BASS MONO 120 Hz: the side at 2 kHz, dB", side_hi, -0.3, 0.1);
        mbus_init(&m);
        mbus_set(&m, MB_ST_WIDTH, 40);        /* 200 % */
        for (i = 0; i < 4096; i++) {
            l[i] = 0.5f;
            r[i] = 0.3f;
        }
        mbus_tape_stereo(&m, l, r, 4096);
        within("WIDTH 200 %: the side doubled (0.5 / 0.3 -> 0.6 / 0.2)", l[100] - r[100], 0.3999, 0.4001);
    }
    /* ---- the limiter: GAIN +12 dB into it, CEILING -1 dB: nothing over it; at 0 dB GAIN, a quiet sine untouched */
    {
        static master_t mst;
        static float l[N], r[N];
        int b, i;
        double pk = 0.0, ceil_lin = pow(10.0, -1.0 / 20.0);
        unsigned seed = 1;
        master_init(&mst);
        master_set(&mst, MST_RATIO, 0);
        master_set(&mst, MST_LGAIN, 24);
        master_set(&mst, MST_CEIL, 10);
        for (b = 0; b < 1000; b++) {
            for (i = 0; i < N; i++) {     /* a kick-like burst every 0.3 s over noise */
                int t = (b * N + i) % 13230;
                seed = seed * 1664525u + 1013904223u;
                l[i] = (float)(0.25 * ((double)(seed >> 8) / 8388608.0 - 1.0) + (t < 2000 ? 0.7 * sin(t * 0.01) : 0.0));
                r[i] = l[i] * 0.8f;
            }
            master_post_st(&mst, l, r, N);
            if (b > 4)
                for (i = 0; i < N; i++)
                    pk = fmax(pk, fmax(fabs(l[i]), fabs(r[i])));
        }
        within("limiter, GAIN +12, CEILING -1 dB: the peak, dB", 20 * log10(pk), -3.0, 20 * log10(ceil_lin) + 0.0001);
        within("limiter: its reduction shown, dB", mst.lgr_view, 1.0, 30.0);
        master_init(&mst);
        pk = 0.0;
        for (b = 0; b < 200; b++) {
            for (i = 0; i < N; i++)
                l[i] = r[i] = (float)(0.5 * sin((b * N + i) * 0.0627));
            master_post_st(&mst, l, r, N);
            if (b > 4)
                for (i = 0; i < N; i++)
                    pk = fmax(pk, fabs(l[i]));
        }
        within("limiter at 0 dB GAIN: a -6 dBFS sine's peak, dB", 20 * log10(pk), -6.03, -6.0);
    }
    /* ---- the loudness meter: a 997 Hz sine at -20 dBFS on both sides is -20 LUFS (BS.1770); the correlation */
    {
        static float l[N], r[N];
        mbus_t m;
        int b, i;
        mbus_init(&m);
        mbus_meter_on(&m, 1);
        for (b = 0; b < 4 * 44100 / N; b++) {
            for (i = 0; i < N; i++)
                l[i] = r[i] = (float)(0.1 * sin(2 * M_PI * 997 * (b * N + i) / FS));
            mbus_meter(&m, l, r, N);
        }
        within("loudness: 997 Hz at -20 dBFS, both sides: short-term LUFS", mbus_lufs(&m, 0), -20.15, -19.85);
        within("loudness: momentary LUFS", mbus_lufs(&m, 1), -20.15, -19.85);
        within("correlation: the same both sides", mbus_corr(&m), 0.99, 1.0);
        mbus_meter_on(&m, 0);
        mbus_meter_on(&m, 1);
        for (b = 0; b < 44100 / N; b++) {
            for (i = 0; i < N; i++) {
                l[i] = (float)(0.1 * sin(2 * M_PI * 997 * (b * N + i) / FS));
                r[i] = -l[i];
            }
            mbus_meter(&m, l, r, N);
        }
        within("correlation: out of phase", mbus_corr(&m), -1.0, -0.99);
        mbus_meter_on(&m, 0);
        within("loudness: meters off, nothing shown", mbus_lufs(&m, 0), -70.0, -70.0);
    }
    /* ---- the cost on this computer: the whole chain (every stage on, meters too) against X0X's master alone */
    {
        static master_t mst;
        static mbus_t m;
        static float l[N], r[N];
        int b, i, rep;
        double t_base = 1e9, t_full = 1e9;
        for (rep = 0; rep < 2; rep++) {
            clock_t c;
            master_init(&mst);
            mbus_init(&m);
            if (rep) {
                mbus_set(&m, MB_EQ_LOW, 30);
                mbus_set(&m, MB_EQ_MID, 20);
                mbus_set(&m, MB_EQ_HIGH, 28);
                mbus_set(&m, MB_EQ_CUT, 3);
                mbus_set(&m, MB_TP_DRIVE, 64);
                mbus_set(&m, MB_TP_WARM, 60);
                mbus_set(&m, MB_TP_TONE, 74);
                mbus_set(&m, MB_ST_WIDTH, 28);
                mbus_set(&m, MB_ST_BASS, 4);
                mbus_meter_on(&m, 1);
            }
            master_set(&mst, MST_THRESH, 79);
            master_set(&mst, MST_RATIO, 2);
            c = clock();
            for (b = 0; b < 40000; b++) {   /* 232 s of audio */
                for (i = 0; i < N; i++) {
                    l[i] = (float)(0.3 * sin((b * N + i) * 0.031));
                    r[i] = (float)(0.3 * sin((b * N + i) * 0.027));
                }
                if (rep)
                    mbus_eq(&m, l, r, N);
                master_pre_st(&mst, l, r, N);
                if (rep)
                    mbus_tape_stereo(&m, l, r, N);
                master_post_st(&mst, l, r, N);
                if (rep)
                    mbus_meter(&m, l, r, N);
            }
            *(rep ? &t_full : &t_base) = (double)(clock() - c) / CLOCKS_PER_SEC;
        }
        printf("  cost (this computer, 232 s of audio): X0X's master %.3f s, the whole chain %.3f s: x%.2f\n", t_base,
               t_full, t_full / t_base);
    }
    printf("%d checks, %d failed\n", checks, fails);
    return fails ? 1 : 0;
}
