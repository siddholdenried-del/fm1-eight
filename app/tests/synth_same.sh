#!/bin/sh
# fm1-eight: 0.2's factory sounds render the same, byte for byte, before (app/attic/synth_v1) and after the synth
# update (app/dsp). From fm1-eight: sh app/tests/synth_same.sh  (needs app/build/gen/fe_tables.h: a host build first)
set -e
T=$(mktemp -d)
mkdir -p "$T/old/felucca"
cp app/attic/synth_v1/synth.c app/attic/synth_v1/synth.h "$T/old/"
cp app/attic/synth_v1/eng_analog.c "$T/old/felucca/"
cp app/dsp/felucca/dsp.c app/dsp/felucca/felucca_engine.h "$T/old/felucca/"
CF="-std=c99 -O2 -ffp-contract=off -Iapp/build/gen"
cc $CF -I"$T/old" app/tests/synth_dump.c "$T/old/synth.c" -o "$T/old_dump"
cc $CF -Iapp/dsp app/tests/synth_dump.c app/dsp/synth.c -o "$T/new_dump"
"$T/old_dump" "$T/old.raw"
"$T/new_dump" "$T/new.raw"
ls -l "$T/old.raw" "$T/new.raw" | awk '{print $5, $9}'
if cmp -s "$T/old.raw" "$T/new.raw"; then echo "same: 0.2's 15 sounds, byte for byte"; rm -rf "$T"; else echo "DIFFERENT"; cmp "$T/old.raw" "$T/new.raw" | head -1; exit 1; fi
