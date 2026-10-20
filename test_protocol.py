import subprocess
import struct
import sys
import time

def put_string(text: str) -> bytes:
    raw = text.encode("utf-8")
    return struct.pack("<H", len(raw)) + raw

def send_msg(proc, payload: bytes):
    proc.stdin.write(struct.pack("<I", len(payload)) + payload)
    proc.stdin.flush()

def read_msg(proc):
    head = proc.stdout.read(4)
    if not head:
        return None
    (size,) = struct.unpack("<I", head)
    return proc.stdout.read(size)

def main():
    print("Launching lt_module with --lang tr...")
    proc = subprocess.Popen(
        [sys.executable, "src/lt_module.py", "--lang", "tr", "--no-update", "--lang-dir", "TR", "--backend", "local"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    # 1. Read handshake from module
    handshake = read_msg(proc)
    if not handshake:
        err = proc.stderr.read().decode('utf-8', 'ignore')
        print(f"Failed to read handshake. Stderr: {err}")
        return 1

    proto, src_lang, res_ver = struct.unpack_from("<IiI", handshake, 0)
    str_len = struct.unpack_from("<H", handshake, 12)[0]
    cache_key = handshake[14:14+str_len].decode("utf-8")
    print(f"Handshake received: proto={proto}, src_lang={src_lang}, res_ver={res_ver}, cache_key={cache_key}")

    # 2. Send test game strings
    test_cases = [
        (1001, 12345678, "Defeat the enemy champion to earn rewards."),
        (1002, 87654321, "Talk to the Scout to reveal the area."),
        (1003, 99999999, "Waypoint"),
    ]

    for key, h, text in test_cases:
        msg = bytes([0]) + struct.pack("<IQ", key, h) + put_string(text)
        print(f"Sending [{key}]: {text}")
        send_msg(proc, msg)

    # 3. Read translated responses
    for _ in range(len(test_cases)):
        resp = read_msg(proc)
        if not resp:
            print("No response received.")
            break
        kind = resp[0]
        if kind == 0:
            key, h = struct.unpack_from("<IQ", resp, 1)
            n = struct.unpack_from("<H", resp, 13)[0]
            translated = resp[15:15+n].decode("utf-8", "replace")
            print(f"Received translation for [{key}]: {translated}")

    proc.terminate()
    print("Test passed successfully!")
    return 0

if __name__ == "__main__":
    sys.exit(main())
