"""Read single XML returns out of the IRS's monthly e-file zip batches without
downloading the whole zip (HTTP range requests against apps.irs.gov).

    members = central_directory(zip_url)            # {filename: (offset, csize, usize, method)}
    xml = read_member(zip_url, members[name])

The IRS posts a new batch each month at
https://apps.irs.gov/pub/epostcard/990/xml/<year>/<year>_TEOS_XML_<NN><A|B|...>.zip
with an index at .../<year>/index_<year>.csv. A batch the index calls "05A" can be split
across 05A.zip and 05B.zip, so callers look up a filename in every sibling zip.
"""

import struct
import zlib

import inflate64
from common import http

EOCD_SIG = b"PK\x05\x06"
EOCD64_LOC_SIG = b"PK\x06\x07"
CD_SIG = 0x02014B50
LOCAL_SIG = 0x04034B50


def _range(url, start, end):
    """Bytes [start, end] inclusive."""
    with http(url, headers={"Range": f"bytes={start}-{end}"}, timeout=180) as r:
        if r.status != 206:
            raise RuntimeError(f"{url}: range request answered {r.status}")
        return r.read()


def zip_size(url):
    with http(url, method="HEAD") as r:
        return int(r.headers["Content-Length"]), r.headers.get("Last-Modified", "")


def central_directory(url):
    size, _ = zip_size(url)
    tail_len = min(size, 65536 + 22)
    tail = _range(url, size - tail_len, size - 1)
    i = tail.rfind(EOCD_SIG)
    if i < 0:
        raise RuntimeError(f"{url}: no end-of-central-directory record")
    (_, _, _, _, n_total, cd_size, cd_off, _) = struct.unpack("<4sHHHHIIH", tail[i:i + 22])
    if cd_off == 0xFFFFFFFF or cd_size == 0xFFFFFFFF or n_total == 0xFFFF:
        j = tail.rfind(EOCD64_LOC_SIG, 0, i)
        if j < 0:
            raise RuntimeError(f"{url}: zip64 locator missing")
        (_, _, eocd64_off, _) = struct.unpack("<4sIQI", tail[j:j + 20])
        rec = _range(url, eocd64_off, eocd64_off + 55)
        (_, _, _, _, _, _, _, n_total, cd_size, cd_off) = struct.unpack("<4sQHHIIQQQQ", rec[:56])
    cd = _range(url, cd_off, cd_off + cd_size - 1)
    out = {}
    p = 0
    while p + 46 <= len(cd):
        (sig, _, _, _, method, _, _, crc, csize, usize, nlen, xlen, clen, _, _, _, off) = struct.unpack(
            "<IHHHHHHIIIHHHHHII", cd[p:p + 46])
        if sig != CD_SIG:
            break
        name = cd[p + 46:p + 46 + nlen].decode("utf-8", "replace")
        extra = cd[p + 46 + nlen:p + 46 + nlen + xlen]
        if 0xFFFFFFFF in (csize, usize, off):
            q = 0
            while q + 4 <= len(extra):
                hid, hlen = struct.unpack("<HH", extra[q:q + 4])
                if hid == 1:
                    vals = list(struct.unpack("<" + "Q" * (hlen // 8), extra[q + 4:q + 4 + (hlen // 8) * 8]))
                    if usize == 0xFFFFFFFF:
                        usize = vals.pop(0)
                    if csize == 0xFFFFFFFF:
                        csize = vals.pop(0)
                    if off == 0xFFFFFFFF:
                        off = vals.pop(0)
                    break
                q += 4 + hlen
        out[name.rsplit("/", 1)[-1]] = (off, csize, usize, method, crc)
        p += 46 + nlen + xlen + clen
    return out


def read_member(url, entry):
    off, csize, usize, method = entry[:4]
    # Local header is 30 bytes + name + extra; the extra field can differ from the
    # central directory's, so read a little more than needed and parse it.
    blob = _range(url, off, off + 30 + 512 + csize)
    (sig, _, _, m, _, _, _, _, _, nlen, xlen) = struct.unpack("<IHHHHHIIIHH", blob[:30])
    if sig != LOCAL_SIG:
        raise RuntimeError(f"{url}: bad local header at {off}")
    start = 30 + nlen + xlen
    if start + csize > len(blob):
        blob += _range(url, off + len(blob), off + start + csize - 1)
    data = blob[start:start + csize]
    if method == 0:
        out = data
    elif method == 8:
        out = zlib.decompressobj(-15).decompress(data)
    elif method == 9:  # Deflate64: zlib can't, so a pure-Python inflater does
        out = inflate64.inflate(data, deflate64=True)
    else:
        raise RuntimeError(f"{url}: unsupported compression method {method}")
    if len(entry) > 4 and zlib.crc32(out) & 0xFFFFFFFF != entry[4]:
        raise RuntimeError(f"{url}: CRC mismatch at {off}")
    return out


def batch_zip_urls(base, batch_id):
    """Every existing zip for a batch id: 2026_TEOS_XML_05A -> [..05A.zip, ..05B.zip] (probed)."""
    stem = batch_id[:-1] if batch_id[-1:].isalpha() else batch_id
    urls = []
    for letter in "ABCDEFGH":
        url = f"{base}{stem}{letter}.zip"
        try:
            zip_size(url)
        except RuntimeError:
            if letter == "A" and batch_id[-1:].isalpha():
                continue
            break
        urls.append(url)
    return urls
