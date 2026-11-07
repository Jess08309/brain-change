import tempfile
import threading
import unittest
from pathlib import Path

from sandbox.box import HOST, confine, serve


class SandboxTest(unittest.TestCase):
    def test_confine_refuses_a_path_outside_the_box(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            box = root / "box"
            box.mkdir()
            outside = root / "outside.txt"
            outside.write_text("no", encoding="utf-8")
            with self.assertRaises(PermissionError):
                confine(outside, box)
            self.assertEqual(confine(box / "note.txt", box).name, "note.txt")

    def test_serve_accepts_one_local_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            thread = threading.Thread(target=serve, args=(root, 8766), daemon=True)
            thread.start()
            import socket
            import time

            for _ in range(20):
                try:
                    sock = socket.create_connection((HOST, 8766), timeout=0.2)
                    break
                except OSError:
                    time.sleep(0.05)
            else:
                self.fail("sandbox did not listen")
            with sock:
                peer = sock.getpeername()
                self.assertEqual(peer[0], HOST)
                sock.sendall(b"Check the box.\n")
                data = sock.recv(2000).decode("utf-8")
            self.assertIn("Target: laptop surface", data)
            self.assertIn("Next step:", data)
            self.assertTrue((root / "local" / "sandbox" / "debug.log").is_file())


if __name__ == "__main__":
    unittest.main()
