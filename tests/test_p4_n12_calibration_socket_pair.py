"""Deterministic N12 two-socket setup controls, without live sockets."""
import unittest

from qa.p4_native import n12_calibration as calibration


class FakeSocket:
    def __init__(self, family, kind, attempt, *, udp_denied=False, tcp_denied=False):
        self.family = family
        self.kind = kind
        self.attempt = attempt
        self.udp_denied = udp_denied
        self.tcp_denied = tcp_denied
        self.closed = False
        self.bound = False
        self.address = ("127.0.0.1", 41000 + attempt)

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.closed = True

    def bind(self, address):
        if self.kind == calibration.socket.SOCK_DGRAM and self.udp_denied:
            raise OSError(10048, "private-win32-error")
        if self.kind == calibration.socket.SOCK_STREAM and self.tcp_denied:
            raise OSError(10048, "private-win32-error")
        if self.kind == calibration.socket.SOCK_STREAM:
            assert address == ("127.0.0.1", 0)
        else:
            assert address == self.address
        self.bound = True

    def listen(self, _count):
        pass

    def settimeout(self, _seconds):
        pass

    def getsockname(self):
        return self.address


class FakeFactory:
    def __init__(self, denied_udp_attempts=(), *, denied_tcp_attempts=()):
        self.denied_udp_attempts = set(denied_udp_attempts)
        self.denied_tcp_attempts = set(denied_tcp_attempts)
        self.sockets = []
        self.attempt = 0

    def __call__(self, family, kind):
        if kind == calibration.socket.SOCK_STREAM:
            self.attempt += 1
        obj = FakeSocket(family, kind, self.attempt,
                         udp_denied=(self.attempt in self.denied_udp_attempts),
                         tcp_denied=(self.attempt in self.denied_tcp_attempts))
        self.sockets.append(obj)
        return obj


class MatchingLoopbackSocketsTests(unittest.TestCase):
    def test_first_pair_success_preserves_same_tcp_udp_port(self):
        factory = FakeFactory()
        with calibration.matching_loopback_sockets(socket_factory=factory) as (tcp, udp, address):
            self.assertEqual(address, ("127.0.0.1", 41001))
            self.assertTrue(tcp.bound)
            self.assertTrue(udp.bound)
        self.assertEqual(factory.attempt, 1)
        self.assertTrue(all(s.closed for s in factory.sockets))

    def test_transient_udp_bind_retries_with_fresh_closed_socket_pair(self):
        factory = FakeFactory({1})
        with calibration.matching_loopback_sockets(socket_factory=factory) as (tcp, udp, address):
            self.assertEqual(address, ("127.0.0.1", 41002))
            self.assertTrue(tcp.bound and udp.bound)
            self.assertTrue(all(s.closed for s in factory.sockets[:2]))
        self.assertEqual(factory.attempt, 2)
        self.assertTrue(all(s.closed for s in factory.sockets))

    def test_persistent_udp_denial_fails_closed_at_bounded_attempts(self):
        factory = FakeFactory({1, 2, 3})
        with self.assertRaises(calibration.CalibrationFailure) as raised:
            with calibration.matching_loopback_sockets(socket_factory=factory):
                self.fail("UDP bind failure must never produce a live calibration")
        self.assertEqual(str(raised.exception), "N12 calibration failed at udp-listener.")
        self.assertEqual(factory.attempt, calibration.SOCKET_PAIR_ATTEMPTS)
        self.assertTrue(all(s.closed for s in factory.sockets))
        self.assertNotIn("private", str(raised.exception))

    def test_tcp_denial_is_never_retried_or_reclassified_as_udp(self):
        factory = FakeFactory(denied_tcp_attempts={1})
        with self.assertRaises(calibration.CalibrationFailure) as raised:
            with calibration.matching_loopback_sockets(socket_factory=factory):
                self.fail("TCP failure must never start calibration")
        self.assertEqual(str(raised.exception), "N12 calibration failed at tcp-listener.")
        self.assertEqual(factory.attempt, 1)
        self.assertTrue(all(s.closed for s in factory.sockets))


if __name__ == "__main__":
    unittest.main()
