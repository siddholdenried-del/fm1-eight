/* GhettoMachine: the synth's output for 0.2's 15 factory sounds, raw floats (L, R, reverb send, delay send a block), to
 * show the synth update leaves them as they were: built once against app/attic/synth_v1 and once against app/dsp,
 * the two files must be the same byte for byte (app/tests/synth_same.sh). Uses only what both versions have; ACID is
 * played with 0.2's values (0.4 retuned the preset, not the engine). */
#include "synth.h"
#include <stdio.h>

int main(int argc, char **argv)
{
    float l[SYN_CTL], r[SYN_CTL], rv[SYN_CTL], dl[SYN_CTL];
    FILE *f = argc > 1 ? fopen(argv[1], "wb") : 0;
    int p, b;
    if (!f)
        return 2;
    syn_init();
    for (p = 0; p < 15; p++) {
        int8_t v[SP_NUM];
        int mono = syn_preset(p, v);
#ifdef SP_NUM_V1                          /* the update's build: ACID as 0.2 had it (0.4 retuned it for the 303 generator) */
        if (p == 1) {
            static const int8_t ACID_02[SP_NUM_V1] = {0,  0, 0, 0, 0,  0, 64, 25, 42, 108, 48, 0, 64,
                                                      80, 20, 1, 1, 22, 0, 50, 90, 25, 0,  45, 0, 25};
            int k;
            for (k = 0; k < SP_NUM_V1; k++)
                v[k] = ACID_02[k];
            syn_defaults(v, SP_NUM_V1);
        }
#endif
        syn_kill();
        syn_sound(1, v);
        syn_level(1, 0.8f);
        syn_mixer(1, 50, 0.3f, 0.2f);
        for (b = 0; b < 2400; b++) {     /* 1.7 s */
            float lfo = (float)((b / 40) % 2 ? 1 : -1) * 0.5f;
            if (b == 8) {
                syn_note_on(1, 48, 0.9f, -1, mono);
                if (!mono)
                    syn_note_on(1, 55, 0.6f, -1, 0);
            }
            if (b == 500)
                syn_note_on(1, 60, 0.5f, 12000, mono);   /* a gated note (legato on a MONO sound) */
            if (b == 1200) {
                syn_note_off(1, 48);
                syn_note_off(1, 55);
            }
            syn_mod(1, b < 1200 ? SM_CUTOFF : SM_PITCH, lfo, 0.4f);   /* LFO 1, as the app's */
            syn_prepare();
            syn_half(0);
            syn_half(1);
            syn_mix(l, r, rv, dl);
            fwrite(l, sizeof l, 1, f);
            fwrite(r, sizeof r, 1, f);
            fwrite(rv, sizeof rv, 1, f);
            fwrite(dl, sizeof dl, 1, f);
        }
    }
    fclose(f);
    return 0;
}
