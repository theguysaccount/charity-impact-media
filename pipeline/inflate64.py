"""Pure-Python inflate for Deflate64 ("enhanced deflate", zip method 9), which zlib can't
read. The IRS used it for at least one monthly e-file zip (2026_TEOS_XML_05B).

    data = inflate(raw_bytes, deflate64=True)

A port of Mark Adler's puff.c with the three Deflate64 differences: a 64 KiB window,
length code 285 meaning 3 + a 16-bit extra (not a fixed 258), and distance codes 30 and
31 (bases 32769 and 49153, 14 extra bits). With deflate64=False it is plain deflate,
which the tests compare against zlib. Callers verify the CRC-32 of the output.
"""

MAXBITS = 15
LBASE = [3, 4, 5, 6, 7, 8, 9, 10, 11, 13, 15, 17, 19, 23, 27, 31, 35, 43, 51, 59, 67, 83, 99, 115, 131, 163, 195, 227, 258]
LEXT = [0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 2, 2, 2, 2, 3, 3, 3, 3, 4, 4, 4, 4, 5, 5, 5, 5, 0]
DBASE = [1, 2, 3, 4, 5, 7, 9, 13, 17, 25, 33, 49, 65, 97, 129, 193, 257, 385, 513, 769, 1025, 1537, 2049, 3073, 4097,
         6145, 8193, 12289, 16385, 24577, 32769, 49153]
DEXT = [0, 0, 0, 0, 1, 1, 2, 2, 3, 3, 4, 4, 5, 5, 6, 6, 7, 7, 8, 8, 9, 9, 10, 10, 11, 11, 12, 12, 13, 13, 14, 14]
ORDER = [16, 17, 18, 0, 8, 7, 9, 6, 10, 5, 11, 4, 12, 3, 13, 2, 14, 1, 15]


class Error(Exception):
    pass


def _huffman(lengths):
    """Canonical Huffman table as {(bit length, code): symbol} plus the lengths in use."""
    count = [0] * (MAXBITS + 1)
    for n in lengths:
        count[n] += 1
    code, nxt = 0, [0] * (MAXBITS + 2)
    for bits in range(1, MAXBITS + 1):
        code = (code + count[bits - 1]) << 1 if bits > 1 else 0
        nxt[bits] = code
    table = {}
    for sym, n in enumerate(lengths):
        if n:
            table[(n, nxt[n])] = sym
            nxt[n] += 1
    return table


class _Inflater:
    def __init__(self, data, deflate64):
        self.data, self.pos, self.bitbuf, self.bitcnt = data, 0, 0, 0
        self.out = bytearray()
        self.lbase = LBASE[:-1] + [3] if deflate64 else LBASE
        self.lext = LEXT[:-1] + [16] if deflate64 else LEXT
        self.ndist = 32 if deflate64 else 30

    def bits(self, need):
        bb, bc = self.bitbuf, self.bitcnt
        while bc < need:
            if self.pos >= len(self.data):
                raise Error("input ran out")
            bb |= self.data[self.pos] << bc
            self.pos += 1
            bc += 8
        self.bitbuf, self.bitcnt = bb >> need, bc - need
        return bb & ((1 << need) - 1)

    def decode(self, table):
        code = 0
        for n in range(1, MAXBITS + 1):
            code |= self.bits(1)
            sym = table.get((n, code))
            if sym is not None:
                return sym
            code <<= 1
        raise Error("bad Huffman code")

    def stored(self):
        self.bitbuf, self.bitcnt = 0, 0
        if self.pos + 4 > len(self.data):
            raise Error("stored block header ran out")
        n = self.data[self.pos] | (self.data[self.pos + 1] << 8)
        if n != (~(self.data[self.pos + 2] | (self.data[self.pos + 3] << 8)) & 0xFFFF):
            raise Error("stored block length mismatch")
        self.pos += 4
        self.out += self.data[self.pos:self.pos + n]
        self.pos += n

    def codes(self, lencode, distcode):
        out, lbase, lext = self.out, self.lbase, self.lext
        while True:
            sym = self.decode(lencode)
            if sym < 256:
                out.append(sym)
            elif sym == 256:
                return
            else:
                sym -= 257
                if sym >= 29:
                    raise Error("bad length code")
                length = lbase[sym] + self.bits(lext[sym])
                dsym = self.decode(distcode)
                if dsym >= self.ndist:
                    raise Error("bad distance code")
                dist = DBASE[dsym] + self.bits(DEXT[dsym])
                start = len(out) - dist
                if start < 0:
                    raise Error("distance too far back")
                if dist >= length:
                    out += out[start:start + length]
                else:
                    pattern = out[start:]
                    out += (pattern * (length // dist + 1))[:length]

    def fixed(self):
        lengths = [8] * 144 + [9] * 112 + [7] * 24 + [8] * 8
        self.codes(_huffman(lengths), _huffman([5] * 32))

    def dynamic(self):
        nlen, ndist, ncode = self.bits(5) + 257, self.bits(5) + 1, self.bits(4) + 4
        if nlen > 286 or ndist > 32:
            raise Error("bad counts")
        cl = [0] * 19
        for i in range(ncode):
            cl[ORDER[i]] = self.bits(3)
        clcode = _huffman(cl)
        lengths = []
        while len(lengths) < nlen + ndist:
            sym = self.decode(clcode)
            if sym < 16:
                lengths.append(sym)
            elif sym == 16:
                if not lengths:
                    raise Error("repeat with no previous length")
                lengths += [lengths[-1]] * (3 + self.bits(2))
            elif sym == 17:
                lengths += [0] * (3 + self.bits(3))
            else:
                lengths += [0] * (11 + self.bits(7))
        if len(lengths) > nlen + ndist:
            raise Error("too many lengths")
        self.codes(_huffman(lengths[:nlen]), _huffman(lengths[nlen:]))

    def run(self):
        while True:
            last, kind = self.bits(1), self.bits(2)
            if kind == 0:
                self.stored()
            elif kind == 1:
                self.fixed()
            elif kind == 2:
                self.dynamic()
            else:
                raise Error("bad block type")
            if last:
                return bytes(self.out)


def inflate(data, deflate64=True):
    return _Inflater(data, deflate64).run()
