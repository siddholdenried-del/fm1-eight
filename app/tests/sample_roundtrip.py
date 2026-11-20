# SPDX-License-Identifier: MPL-2.0
"""fm1-eight: a WAV to T3 and T4 and back through the host simulator, as tools/fm1_sample.py does over USB.

    python3 -I app/tests/sample_roundtrip.py app/tools app/build/host/ghettomachine_host OUTDIR

A 1.5 s 48 kHz 24-bit stereo sweep: sent to T3 at 44.1 kHz and read back byte for byte; sent to T4 at 22.05 kHz;
both tracks SAMPLERs; T3 deleted. Prints ROUND TRIP PASSED or FAILED."""
import sys, struct, math, os
tools, host, tmp = sys.argv[1], sys.argv[2], sys.argv[3]
sys.path.insert(0, tools)
import fm1_sample as fs

def make_wav(path, secs=1.5, rate=48000):
    n = int(secs * rate)
    data = bytearray()
    for i in range(n):
        t = i / rate
        f = 110 * (2 ** (3 * t / secs))
        v = int(0.6 * math.sin(2 * math.pi * f * t) * 8388607)
        for ch in (v, -v // 2):
            data += (ch & 0xFFFFFF).to_bytes(3, "little")
    with open(path, "wb") as w:
        w.write(b"RIFF" + struct.pack("<I", 36 + len(data)) + b"WAVEfmt " +
                struct.pack("<IHHIIHH", 16, 1, 2, rate, rate * 6, 6, 24) + b"data" + struct.pack("<I", len(data)) + data)

def expect(link, what):
    link.p.stdin.write("expect " + what + "\n"); link.p.stdin.flush()
    while True:
        s = link.p.stdout.readline().rstrip("\n")
        if s.startswith("sx "):
            link.q.append(bytes.fromhex(s[3:])); continue
        if "ok" in s or "FAIL" in s:
            print("   ", s.strip()); return "FAIL" not in s

wav = os.path.join(tmp, "sweep48k24.wav")
make_wav(wav)
link = fs.ServeLink([host, "--serve"])
good = True
try:
    i, size, room = fs.find_sample(link, 3)
    print(f"T3 file {i}: size {size}, room {room}")
    rate, x = fs.read_wav(wav)
    blob, frames, note = fs.to_s12(rate, x, True, 44100, (room - 16) * 2 // 3)
    print(f"converted: {frames} frames at 44100, {len(blob)} bytes {note}")
    fs.send(link, blob, 3)
    back = fs.get(link, 3)
    print("T3 read back identical:", back == blob); good &= back == blob
    for w in ("type3 2", f"sframes3 {frames}", "srate3 44100", "sshape3_1 1000"):
        good &= expect(link, w)
    i4, _, room4 = fs.find_sample(link, 4)
    blob4, frames4, note4 = fs.to_s12(rate, x, True, 22050, (room4 - 16) * 2 // 3)
    print(f"T4 at 22050: {frames4} frames, {len(blob4)} bytes, room was {room4}")
    fs.send(link, blob4, 4)
    good &= fs.get(link, 4) == blob4
    for w in ("type4 2", f"sframes4 {frames4}", "srate4 22050"):
        good &= expect(link, w)
    fs.s12_to_wav(fs.get(link, 4), os.path.join(tmp, "t4_back.wav"))
    st, _ = fs.request(link, bytes([fs.OP_DELETE]) + struct.pack("<H", i), fs.OP_DELETE)
    _, size3, room3 = fs.find_sample(link, 3)
    print(f"after rm: T3 size {size3}, room {room3}"); good &= st == 0 and size3 == 0
    good &= expect(link, "sframes3 0")
finally:
    link.close()
print("ROUND TRIP", "PASSED" if good else "FAILED")
