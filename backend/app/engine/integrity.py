import hashlib


def sha256_file(path, chunk=1 << 20):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while b := f.read(chunk):
            h.update(b)
    return h.hexdigest()


def verify(path, expected):
    """Match means the bytes equal the recorded hash. It does not prove authenticity."""
    return sha256_file(path) == expected
