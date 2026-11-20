#!/usr/bin/env python3
# SPDX-License-Identifier: MPL-2.0
"""fm1-eight's SAMPLER tracks from a Mac: a WAV in, a 12-bit sample out (and back).

    python3 -I tools/fm1_sample.py send LOOP.wav --track 3       convert it and send it to T3 (the FM-1 stopped)
    python3 -I tools/fm1_sample.py send PAD.wav --rate 22050     at 22.05 kHz: twice as long fits, a little darker
    python3 -I tools/fm1_sample.py get OUT.wav --track 3         T3's sample as a 16-bit WAV
    python3 -I tools/fm1_sample.py convert LOOP.wav OUT.s12      the file alone, nothing sent
    python3 -I tools/fm1_sample.py rm --track 3                  empty T3's sample

--track is 2, 3 or 4 (default 2). Any WAV (8 / 16 / 24 / 32-bit, float, mono or stereo, any rate): mixed to mono,
resampled to 44.1 kHz (or --rate 22050), cut to the room the FM-1 says the track has (its bank is shared by the three
tracks: about 3 s at 44.1 kHz in all), peak-normalised (--no-normalize keeps the level), then 12-bit. The track becomes
a SAMPLER playing all of it; C4 plays it at its own pitch. The FM-1 is found over CoreMIDI by its name ("GhettoMachine",
--port to choose); no packages needed. --serve-cmd "app/build/host/ghettomachine_host --serve" talks to the host simulator
instead. The wire format is fm1-base's companion files (docs/COMPANION.md): begin, data in 512-byte chunks, commit, each
answered; the FM-1 checks the CRC-32 before the new sample counts.
"""
import argparse
import ctypes
import shlex
import struct
import subprocess
import sys
import threading
import time
import zlib

RATES = (44100, 22050)
BANK_FRAMES = (53 * 4096 - 32 - 16) * 2 // 3   # the whole bank, for convert (send asks the FM-1 for the track's room)
MAGIC = 0x31323153                      # "S121": the file's head (app.c smp_head_t)
FILES, OP_LIST, OP_READ, OP_BEGIN, OP_DATA, OP_COMMIT, OP_DELETE = 0x61, 0, 1, 3, 4, 5, 6
STATUS = ["ok", "busy (stop the FM-1 first)", "no such file", "not allowed", "out of range", "CRC-32 mismatch",
          "the flash refused", "out of order", "a malformed request", "an unknown operation"]


# ----------------------------------------------------------------------------- the sample file ---
def read_wav(path):
    """-> (rate, [mono floats -1..1]) for PCM 8/16/24/32-bit and IEEE float, plain or extensible"""
    data = open(path, "rb").read()
    if data[:4] != b"RIFF" or data[8:12] != b"WAVE":
        sys.exit(f"{path}: not a WAV file")
    pos, fmt, raw = 12, None, None
    while pos + 8 <= len(data):
        cid, size = data[pos:pos + 4], struct.unpack_from("<I", data, pos + 4)[0]
        body = data[pos + 8:pos + 8 + size]
        if cid == b"fmt ":
            fmt = body
        elif cid == b"data":
            raw = body
        pos += 8 + size + (size & 1)
    if fmt is None or raw is None:
        sys.exit(f"{path}: no fmt or data chunk")
    tag, ch, rate, _, align, bits = struct.unpack_from("<HHIIHH", fmt)
    if tag == 0xFFFE and len(fmt) >= 26:
        tag = struct.unpack_from("<H", fmt, 24)[0]
    if tag not in (1, 3) or ch < 1:
        sys.exit(f"{path}: format {tag} is not PCM or float")
    w, n = bits // 8, len(raw) // align
    out = []
    for i in range(n):
        acc = 0.0
        for c in range(ch):
            o = i * align + c * w
            b = raw[o:o + w]
            if tag == 3:
                v = struct.unpack("<f" if w == 4 else "<d", b)[0]
            elif w == 1:
                v = (b[0] - 128) / 128.0
            else:
                v = int.from_bytes(b, "little", signed=True) / float(1 << (8 * w - 1))
            acc += v
        out.append(acc / ch)
    return rate, out


def to_s12(rate, x, normalize=True, out_rate=44100, max_frames=BANK_FRAMES):
    """-> (the file's bytes, frames, the note) at out_rate, max_frames at most, 12-bit packed"""
    RATE = out_rate
    if rate != RATE:                       # linear resampling: fine for 12-bit
        n = int(len(x) * RATE / rate)
        step = rate / RATE
        y = []
        for i in range(n):
            p = i * step
            k = int(p)
            f = p - k
            a = x[k] if k < len(x) else 0.0
            b = x[k + 1] if k + 1 < len(x) else a
            y.append(a + (b - a) * f)
        x = y
    note = ""
    if len(x) > max_frames:
        note = f"cut at {max_frames / RATE:.2f} s to fit (it was {len(x) / RATE:.2f} s)"
        x = x[:max_frames]
    if len(x) < 2:
        sys.exit("the sound is too short")
    peak = max(abs(v) for v in x) or 1.0
    g = 0.98 / peak if normalize else 1.0
    q = [max(-2048, min(2047, int(round(v * g * 2047)))) & 0xFFF for v in x]
    if len(q) & 1:
        q.append(0)
    packed = bytearray()
    for i in range(0, len(q), 2):
        a, b = q[i], q[i + 1]
        packed += bytes([a & 0xFF, (a >> 8) | (b & 0x0F) << 4, b >> 4])
    frames = len(x)
    packed = packed[:(frames * 3 + 1) // 2]
    return struct.pack("<IIII", MAGIC, frames, RATE, 0) + bytes(packed), frames, note


def s12_to_wav(blob, path):
    magic, frames, rate, _ = struct.unpack_from("<IIII", blob)
    if magic != MAGIC:
        sys.exit("the FM-1's file is not a sample")
    d = blob[16:]
    out = bytearray()
    for i in range(frames):
        b = d[(i >> 1) * 3:(i >> 1) * 3 + 3]
        v = (b[1] >> 4 | b[2] << 4) if i & 1 else (b[0] | (b[1] & 0x0F) << 8)
        if v & 0x800:
            v -= 4096
        out += struct.pack("<h", v << 4)
    with open(path, "wb") as f:
        f.write(b"RIFF" + struct.pack("<I", 36 + len(out)) + b"WAVEfmt " +
                struct.pack("<IHHIIHH", 16, 1, 1, rate, rate * 2, 2, 16) + b"data" + struct.pack("<I", len(out)) + out)


# ----------------------------------------------------------------------------- the wire ---
def pack7(data):
    out, acc, nb = [], 0, 0
    for b in data:
        acc |= b << nb
        nb += 8
        while nb >= 7:
            out.append(acc & 0x7F)
            acc >>= 7
            nb -= 7
    if nb:
        out.append(acc & 0x7F)
    return bytes(out)


def unpack7(s):
    out, acc, nb = [], 0, 0
    for b in s:
        acc |= (b & 0x7F) << nb
        nb += 7
        while nb >= 8:
            out.append(acc & 0xFF)
            acc >>= 8
            nb -= 8
    return bytes(out)


def frame(cmd, body):
    n = len(body)
    return b"\xF0" + pack7(bytes([0, 0x59, cmd, n & 0xFF, n >> 8 & 0xFF, n >> 16]) + body +
                           bytes([~sum(body) & 0xFF])) + b"\xF7"


def decode(pkt):
    if len(pkt) < 3 or pkt[0] != 0xF0 or pkt[-1] != 0xF7:
        return None
    u = unpack7(pkt[1:-1])
    if len(u) < 7 or u[0] != 0 or u[1] != 0x59:
        return None
    n = u[3] | u[4] << 8 | u[5] << 16
    if len(u) < n + 7 or ~sum(u[6:6 + n]) & 0xFF != u[6 + n]:
        return None
    return u[2], bytes(u[6:6 + n])


class ServeLink:
    """the host simulator (NAME_host --serve) as the FM-1"""

    def __init__(self, cmd):
        self.p = subprocess.Popen(shlex.split(cmd) if isinstance(cmd, str) else cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, bufsize=1)
        self.q = []

    def _cmd(self, line):
        self.p.stdin.write(line + "\n")
        self.p.stdin.flush()
        while True:
            s = self.p.stdout.readline()
            if not s:
                sys.exit("the simulator stopped")
            s = s.rstrip("\n")
            if s.startswith("sx "):
                self.q.append(bytes.fromhex(s[3:]))
            elif s.startswith(("ok", "  ok", "FAIL", "fail")):
                return

    def send(self, pkt):
        self.p.stdin.write("sx " + pkt.hex().upper() + "\n")

    def read(self, timeout):
        if not self.q:
            self._cmd("run 5")
        return self.q.pop(0) if self.q else None

    def close(self):
        if self.p.poll() is None:
            self.p.stdin.write("quit\n")
            self.p.stdin.close()
            self.p.wait(10)


class CoreMidiLink:
    """the FM-1 over CoreMIDI (macOS), with ctypes: its destination for requests, its source for the answers"""

    def __init__(self, want):
        cm = ctypes.cdll.LoadLibrary("/System/Library/Frameworks/CoreMIDI.framework/CoreMIDI")
        cf = ctypes.cdll.LoadLibrary("/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation")
        self.cm, self.cf = cm, cf
        cf.CFStringCreateWithCString.restype = ctypes.c_void_p
        cf.CFStringCreateWithCString.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_uint32]
        cf.CFStringGetCString.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_long, ctypes.c_uint32]
        cf.CFRelease.argtypes = [ctypes.c_void_p]
        cm.MIDIClientCreate.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint32)]
        cm.MIDIOutputPortCreate.argtypes = [ctypes.c_uint32, ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint32)]
        self.READPROC = ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)
        cm.MIDIInputPortCreate.argtypes = [ctypes.c_uint32, ctypes.c_void_p, self.READPROC, ctypes.c_void_p,
                                           ctypes.POINTER(ctypes.c_uint32)]
        cm.MIDIPortConnectSource.argtypes = [ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p]
        cm.MIDIGetNumberOfDestinations.restype = ctypes.c_ulong
        cm.MIDIGetNumberOfSources.restype = ctypes.c_ulong
        cm.MIDIGetDestination.restype = ctypes.c_uint32
        cm.MIDIGetDestination.argtypes = [ctypes.c_ulong]
        cm.MIDIGetSource.restype = ctypes.c_uint32
        cm.MIDIGetSource.argtypes = [ctypes.c_ulong]
        cm.MIDIObjectGetStringProperty.argtypes = [ctypes.c_uint32, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)]
        cm.MIDIPacketListInit.restype = ctypes.c_void_p
        cm.MIDIPacketListInit.argtypes = [ctypes.c_void_p]
        cm.MIDIPacketListAdd.restype = ctypes.c_void_p
        cm.MIDIPacketListAdd.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.c_void_p, ctypes.c_uint64,
                                         ctypes.c_ulong, ctypes.c_char_p]
        cm.MIDISend.argtypes = [ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p]
        self.kname = ctypes.c_void_p.in_dll(cm, "kMIDIPropertyDisplayName")
        utf8 = 0x08000100
        self.cfstr = lambda s: cf.CFStringCreateWithCString(None, s.encode(), utf8)
        client = ctypes.c_uint32()
        if cm.MIDIClientCreate(self.cfstr("fm1-sample"), None, None, ctypes.byref(client)):
            sys.exit("CoreMIDI: no client")
        time.sleep(0.3)
        dests = [(cm.MIDIGetDestination(i), self._name(cm.MIDIGetDestination(i)))
                 for i in range(cm.MIDIGetNumberOfDestinations())]
        srcs = [(cm.MIDIGetSource(i), self._name(cm.MIDIGetSource(i))) for i in range(cm.MIDIGetNumberOfSources())]
        pick = lambda xs: [x for x in xs if want.lower() in x[1].lower()]
        d, s = pick(dests), pick(srcs)
        if len(d) != 1 or len(s) != 1:
            sys.exit(f"need one FM-1 named like {want!r}; MIDI outs {[n for _, n in dests]}, ins {[n for _, n in srcs]}")
        self.dest = d[0][0]
        self.out = ctypes.c_uint32()
        cm.MIDIOutputPortCreate(client, self.cfstr("out"), ctypes.byref(self.out))
        self.q, self.cur, self.cv = [], bytearray(), threading.Condition()
        self.proc = self.READPROC(self._got)
        inp = ctypes.c_uint32()
        cm.MIDIInputPortCreate(client, self.cfstr("in"), self.proc, None, ctypes.byref(inp))
        cm.MIDIPortConnectSource(inp, s[0][0], None)
        print(f"FM-1: {d[0][1]}")

    def _name(self, obj):
        ref = ctypes.c_void_p()
        if self.cm.MIDIObjectGetStringProperty(obj, self.kname, ctypes.byref(ref)) or not ref:
            return "?"
        buf = ctypes.create_string_buffer(256)
        self.cf.CFStringGetCString(ref, buf, 256, 0x08000100)
        self.cf.CFRelease(ref)
        return buf.value.decode("utf-8", "replace")

    def _got(self, plist, _a, _b):          # CoreMIDI's thread: a packet list (4-byte aligned packets on arm64)
        base = plist
        n = ctypes.c_uint32.from_address(base).value
        p = base + 4
        for _ in range(n):
            ln = ctypes.c_uint16.from_address(p + 8).value
            data = ctypes.string_at(p + 10, ln)
            for b in data:
                if b == 0xF0:
                    self.cur = bytearray([b])
                elif self.cur:
                    if b >= 0x80 and b != 0xF7:
                        continue            # (real-time bytes inside a SysEx)
                    self.cur.append(b)
                    if b == 0xF7:
                        with self.cv:
                            self.q.append(bytes(self.cur))
                            self.cv.notify()
                        self.cur = bytearray()
            p = (p + 10 + ln + 3) & ~3

    def send(self, pkt):
        buf = ctypes.create_string_buffer(4096)
        cur = self.cm.MIDIPacketListInit(buf)
        for o in range(0, len(pkt), 256):   # a SysEx over several packets of 256 bytes at most
            part = pkt[o:o + 256]
            cur = self.cm.MIDIPacketListAdd(buf, 4096, cur, 0, len(part), part)
            if not cur:
                sys.exit("CoreMIDI: the request does not fit a packet list")
        self.cm.MIDISend(self.out, self.dest, buf)

    def read(self, timeout):
        with self.cv:
            if not self.q:
                self.cv.wait(timeout)
            return self.q.pop(0) if self.q else None

    def close(self):
        pass


def request(link, body, op, tries=4, timeout=1.0):
    """one files request -> (status, the answer after op, status, index)"""
    for _ in range(tries):
        link.send(frame(FILES, body))
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            p = link.read(end - time.monotonic())
            if p is None:
                break
            a = decode(p)
            if a and a[0] == FILES and len(a[1]) >= 4 and a[1][0] == op:
                return a[1][1], a[1][4:]
    sys.exit("no answer from the FM-1 (is GhettoMachine running, with its companion?)")


def find_sample(link, track):
    """-> (the file's index, its size, the room it has) of the track's sample"""
    want = f"sample-t{track}"
    st, b = request(link, bytes([OP_LIST]) + struct.pack("<H", 0), OP_LIST)
    count = struct.unpack_from("<H", b)[0] if len(b) >= 2 else 0
    for i in range(count):
        st, b = request(link, bytes([OP_LIST]) + struct.pack("<H", i), OP_LIST)
        name = b[12:].split(b"\0")[0].decode() if st == 0 and len(b) > 12 else ""
        if name == want:
            return i, struct.unpack_from("<I", b, 4)[0], struct.unpack_from("<I", b, 8)[0]
    sys.exit(f"the firmware has no {want} file (is it GhettoMachine with SAMPLER tracks?)")


def check(st, what):
    if st:
        sys.exit(f"{what}: {STATUS[st] if st < len(STATUS) else st}")


def send(link, blob, track):
    i, _, _ = find_sample(link, track)
    crc = zlib.crc32(blob)
    st, b = request(link, bytes([OP_BEGIN]) + struct.pack("<HII", i, len(blob), crc), OP_BEGIN)
    check(st, "begin")
    nxt = struct.unpack_from("<I", b)[0]
    while nxt < len(blob):
        st, b = request(link, bytes([OP_DATA]) + struct.pack("<HI", i, nxt) + blob[nxt:nxt + 512], OP_DATA)
        if st not in (0, 7) or len(b) < 4:
            check(st, f"data at {nxt}")
        nxt = struct.unpack_from("<I", b)[0]
        print(f"\r  {nxt * 100 // len(blob):3d} %", end="", flush=True)
    print()
    st, b = request(link, bytes([OP_COMMIT]) + struct.pack("<H", i), OP_COMMIT, timeout=5.0)
    check(st, "commit")


def get(link, track):
    i, size, _ = find_sample(link, track)
    if not size:
        sys.exit(f"T{track} has no sample")
    out = bytearray()
    while len(out) < size:
        st, b = request(link, bytes([OP_READ]) + struct.pack("<HIH", i, len(out), 256), OP_READ)
        check(st, f"read at {len(out)}")
        out += b[4:]
    return bytes(out[:size])


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("what", choices=["send", "get", "convert", "rm"])
    ap.add_argument("files", nargs="*")
    ap.add_argument("--port", default="GhettoMachine", help="part of the FM-1's MIDI name (default GhettoMachine)")
    ap.add_argument("--serve-cmd", help="a host simulator instead (ghettomachine_host --serve)")
    ap.add_argument("--no-normalize", action="store_true", help="keep the WAV's level")
    ap.add_argument("--track", type=int, choices=[2, 3, 4], default=2, help="the SAMPLER track (default 2)")
    ap.add_argument("--rate", type=int, choices=RATES, default=44100, help="the sample's rate (default 44100)")
    a = ap.parse_args()
    if a.what in ("send", "convert") and not a.files:
        sys.exit("give a WAV file")
    if a.what == "convert":
        rate, x = read_wav(a.files[0])
        blob, frames, note = to_s12(rate, x, not a.no_normalize, a.rate)
        print(f"{a.files[0]}: {frames / a.rate:.3f} s at {a.rate} Hz, 12-bit, {len(blob)} bytes" + (f"; {note}" if note else ""))
        open(a.files[1] if len(a.files) > 1 else a.files[0] + ".s12", "wb").write(blob)
        return
    link = ServeLink(a.serve_cmd) if a.serve_cmd else CoreMidiLink(a.port)
    try:
        if a.what == "send":
            rate, x = read_wav(a.files[0])
            _, _, room = find_sample(link, a.track)
            blob, frames, note = to_s12(rate, x, not a.no_normalize, a.rate, max(2, (room - 16) * 2 // 3))
            print(f"{a.files[0]}: {frames / a.rate:.3f} s at {a.rate} Hz, 12-bit, {len(blob)} bytes" + (f"; {note}" if note else ""))
            send(link, blob, a.track)
            print(f"sent: T{a.track} is a SAMPLER playing it (SAVE on the FM-1 keeps that)")
        elif a.what == "get":
            blob = get(link, a.track)
            s12_to_wav(blob, a.files[0] if a.files else f"t{a.track}.wav")
            print(f"saved {a.files[0] if a.files else f't{a.track}.wav'}")
        elif a.what == "rm":
            i, _, _ = find_sample(link, a.track)
            st, _ = request(link, bytes([OP_DELETE]) + struct.pack("<H", i), OP_DELETE)
            check(st, "delete")
            print(f"T{a.track} has no sample now")
    finally:
        link.close()


if __name__ == "__main__":
    main()
