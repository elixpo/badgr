"""Pure Python QR Code Generator for MicroPython & OreoOS.

Generates 100% ISO/IEC 18004 compliant QR code matrices (Versions 1-6, ECC L)
with Reed-Solomon GF(256) error correction, standard interleaving, alignment,
and BCH(15,5) format info masking. Scannable with Google Lens, iOS Camera,
and standard 2D barcode scanners with zero external dependencies.
"""

_EXP = [0] * 512
_LOG = [0] * 256

def _init_gf():
    x = 1
    for i in range(255):
        _EXP[i] = x
        _EXP[i + 255] = x
        _LOG[x] = i
        x = ((x << 1) ^ 0x11D) if (x & 0x80) else (x << 1)
    _LOG[0] = 0

_init_gf()


def _poly_mul(p1, p2):
    r = [0] * (len(p1) + len(p2) - 1)
    for i, c1 in enumerate(p1):
        if c1 == 0:
            continue
        l1 = _LOG[c1]
        for j, c2 in enumerate(p2):
            if c2 != 0:
                r[i + j] ^= _EXP[l1 + _LOG[c2]]
    return r


def _rs_generator(num_ec):
    g = [1]
    for i in range(num_ec):
        g = _poly_mul(g, [1, _EXP[i]])
    return g


def _rs_encode(data, num_ec):
    gen = _rs_generator(num_ec)
    msg = list(data) + [0] * num_ec
    for i in range(len(data)):
        lead = msg[i]
        if lead != 0:
            log_lead = _LOG[lead]
            for j in range(len(gen)):
                msg[i + j] ^= _EXP[log_lead + _LOG[gen[j]]]
    return msg[len(data):]


# Version table for ECC-L: (total_cw, ec_cw_per_block, [(b1_count, b1_data), (b2_count, b2_data)], align_coords)
_V_TABLE = {
    1: (26, 7, [(1, 19)], []),
    2: (44, 10, [(1, 34)], [6, 18]),
    3: (70, 15, [(1, 55)], [6, 22]),
    4: (100, 20, [(1, 80)], [6, 26]),
    5: (134, 26, [(1, 108)], [6, 30]),
    6: (172, 18, [(2, 68)], [6, 34]),
}


def _bch_format(ec_level=1, mask=0):
    data = (ec_level << 3) | mask
    d = data << 10
    g = 0x537
    for i in range(14, 9, -1):
        if (d >> i) & 1:
            d ^= (g << (i - 10))
    raw = (data << 10) | d
    return raw ^ 0x5412


class QRCode:
    @staticmethod
    def encode(text):
        """Encode text or URL into a 2D boolean matrix where True = black module."""
        data = text.encode("utf-8") if isinstance(text, str) else bytes(text)
        n_bytes = len(data)

        # Select smallest version that fits (4 bits mode + 8 bits len + data)
        version = None
        for v in sorted(_V_TABLE.keys()):
            tot, ec, blocks, align = _V_TABLE[v]
            data_cap = sum(cnt * dcw for cnt, dcw in blocks)
            if 12 + n_bytes * 8 <= data_cap * 8:
                version = v
                break
        if version is None:
            version = 6

        tot, ec, blocks, align = _V_TABLE[version]
        data_cap = sum(cnt * dcw for cnt, dcw in blocks)

        # 1. Assemble bitstream
        bits = []
        # Mode: Byte (0100)
        bits.extend([0, 1, 0, 0])
        # Char count (8 bits for Versions 1-9)
        for i in range(7, -1, -1):
            bits.append((n_bytes >> i) & 1)
        for b in data:
            for i in range(7, -1, -1):
                bits.append((b >> i) & 1)

        # Terminator
        rem_bits = data_cap * 8 - len(bits)
        term = min(4, rem_bits)
        bits.extend([0] * term)

        # Pad to byte boundary
        if len(bits) % 8 != 0:
            bits.extend([0] * (8 - (len(bits) % 8)))

        # Standard pad bytes (0xEC, 0x11)
        pad_bytes = [0xEC, 0x11]
        p_idx = 0
        while len(bits) < data_cap * 8:
            pb = pad_bytes[p_idx % 2]
            for i in range(7, -1, -1):
                bits.append((pb >> i) & 1)
            p_idx += 1

        data_codewords = []
        for i in range(0, len(bits), 8):
            byte_val = 0
            for bit in bits[i:i + 8]:
                byte_val = (byte_val << 1) | bit
            data_codewords.append(byte_val)

        # 2. Block division & Reed-Solomon ECC calculation
        block_data = []
        block_ec = []
        c_offset = 0
        for b_count, b_data_len in blocks:
            for _ in range(b_count):
                d_block = data_codewords[c_offset : c_offset + b_data_len]
                c_offset += b_data_len
                ec_block = _rs_encode(d_block, ec)
                block_data.append(d_block)
                block_ec.append(ec_block)

        # 3. Interleaving data & ECC codewords
        final_codewords = []
        max_d_len = max(len(b) for b in block_data)
        for i in range(max_d_len):
            for b in block_data:
                if i < len(b):
                    final_codewords.append(b[i])
        for i in range(ec):
            for b in block_ec:
                if i < len(b):
                    final_codewords.append(b[i])

        final_bits = []
        for cw in final_codewords:
            for i in range(7, -1, -1):
                final_bits.append((cw >> i) & 1)

        # 4. Matrix construction
        size = 17 + version * 4
        matrix = [[None] * size for _ in range(size)]
        is_function = [[False] * size for _ in range(size)]

        def set_fn(r, c, val):
            matrix[r][c] = val
            is_function[r][c] = True

        # Finders with 1-module quiet separators
        def add_finder(top, left):
            for r in range(-1, 8):
                for c in range(-1, 8):
                    mr, mc = top + r, left + c
                    if 0 <= mr < size and 0 <= mc < size:
                        if 0 <= r <= 6 and 0 <= c <= 6:
                            val = (r in (0, 6) or c in (0, 6) or (2 <= r <= 4 and 2 <= c <= 4))
                            set_fn(mr, mc, val)
                        else:
                            set_fn(mr, mc, False)

        add_finder(0, 0)
        add_finder(0, size - 7)
        add_finder(size - 7, 0)

        # Timing patterns (alternating on row 6 and col 6)
        for i in range(8, size - 8):
            if not is_function[6][i]:
                set_fn(6, i, i % 2 == 0)
            if not is_function[i][6]:
                set_fn(i, 6, i % 2 == 0)

        # Alignment patterns (for Version >= 2)
        if align:
            for r in align:
                for c in align:
                    if (r <= 8 and c <= 8) or (r <= 8 and c >= size - 9) or (r >= size - 9 and c <= 8):
                        continue
                    for dr in range(-2, 3):
                        for dc in range(-2, 3):
                            val = (abs(dr) == 2 or abs(dc) == 2 or (dr == 0 and dc == 0))
                            set_fn(r + dr, c + dc, val)

        # Dark module
        set_fn(size - 8, 8, True)

        # Reserve format info areas
        for i in range(9):
            is_function[8][i] = True
            is_function[i][8] = True
        for i in range(8):
            is_function[8][size - 1 - i] = True
            is_function[size - 1 - i][8] = True

        # 5. Place data & ECC bits (right-to-left zig-zag)
        bit_idx = 0
        direction = -1
        c = size - 1
        while c > 0:
            if c == 6: c -= 1
            for row_step in range(size):
                r = (size - 1 - row_step) if direction == -1 else row_step
                for col_step in (c, c - 1):
                    if not is_function[r][col_step]:
                        b = final_bits[bit_idx] if bit_idx < len(final_bits) else 0
                        bit_idx += 1
                        # Mask pattern 0: (r + col) % 2 == 0
                        mask = ((r + col_step) % 2 == 0)
                        matrix[r][col_step] = bool(b ^ mask)
            direction = -direction
            c -= 2

        # 6. Apply format info bits (BCH 15,5 error-corrected)
        bits_val = _bch_format(ec_level=1, mask=0)
        for i in range(15):
            mod = ((bits_val >> i) & 1) == 1
            if i < 6:
                matrix[i][8] = mod
            elif i < 8:
                matrix[i + 1][8] = mod
            else:
                matrix[size - 15 + i][8] = mod

        for i in range(15):
            mod = ((bits_val >> i) & 1) == 1
            if i < 8:
                matrix[8][size - i - 1] = mod
            elif i < 9:
                matrix[8][15 - i - 1 + 1] = mod
            else:
                matrix[8][15 - i - 1] = mod

        return matrix
