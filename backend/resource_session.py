"""Dormant desktop composition root. No application/OS import side effects.

Only the trusted desktop launcher may construct this session. All factories
are internal, not browser callbacks. They must use the exact coordinator and
must not install legacy admission bypasses. Actual app registration remains
separately gated; this module does not open a socket or launch a native model.
"""
from threading import Lock, Thread
from time import monotonic

try:
    from .resource_admission import Coordinator
    from .resource_host import ControlBootstrap, ProtocolFault
except ImportError:
    from resource_admission import Coordinator
    from resource_host import ControlBootstrap, ProtocolFault


class DesktopResourceSession:
    """Own one control thread and coordinator for the entire server lifetime."""
    def __init__(self, bootstrap, read_mode, read_available_bytes, *,
                 build_autonomy, build_app, build_server):
        if not isinstance(bootstrap, ControlBootstrap):
            raise TypeError("Trusted control bootstrap required")
        self.coordinator = Coordinator(read_mode, read_available_bytes)
        self._bootstrap = bootstrap
        self._guard = Lock()
        self._used = False
        self._stopping = False
        self._control_ok = False
        self._thread = None
        try:
            self.autonomy = build_autonomy(self.coordinator)
            if self.autonomy.stages.coordinator is not self.coordinator:
                raise ValueError("Autonomy must share the desktop coordinator")
            self.app = build_app(self.coordinator, self.autonomy)
            self.server = build_server(self.app)
        except BaseException:
            self.coordinator.begin_shutdown()
            bootstrap.discard_unstarted()
            raise

    def _ready(self):
        with self._guard:
            return (not self._stopping and self.server.started is True
                    and not self.coordinator.status()["stopping"])

    def _stop(self):
        # Do not hold a lock across shutdown callbacks, DB work or joins.
        self.coordinator.begin_shutdown()
        with self._guard:
            self._stopping = True
        self.server.should_exit = True
        self.autonomy.stop_admission()

    def _control(self):
        try:
            self._bootstrap.run(self.coordinator, self._stop, ready=self._ready,
                                exit_on_shutdown=True)
        except BaseException:
            # Fixed failure state; no raw transport or capability logging.
            try:
                self._stop()
            except BaseException:
                pass
        else:
            with self._guard:
                self._control_ok = True

    def run(self, *, join_timeout=5.0):
        if type(join_timeout) not in (int,float) or not 0 <= join_timeout <= 5:
            raise ValueError("Invalid desktop shutdown wait bound")
        with self._guard:
            if self._used:
                raise ProtocolFault("Desktop resource session already used")
            self._used = True
            self._thread = Thread(target=self._control,
                                  name="pilotodin-owned-control", daemon=False)
        try:
            self._thread.start()
        except BaseException:
            # Unknown start acknowledgement; retain exact thread, no discard
            # of a bootstrap that may already be in use and no new session.
            self._stop()
            raise
        server_returned = False
        try:
            if not self.server.should_exit:
                self.server.run()
                server_returned = True
        finally:
            self._stop()
            deadline = monotonic() + join_timeout
            self._thread.join(max(0.0, deadline - monotonic()))
            # The real supervisor's drain retains the exact worker if busy.
            drained = self.autonomy.drain(max(0.0, deadline - monotonic()))
        with self._guard:
            control_ok = self._control_ok
        return (server_returned and self.server.started is True
                and not self._thread.is_alive() and control_ok
                and drained is True and not self.coordinator.status()["active"])

    def control_alive(self):
        return self._thread is not None and self._thread.is_alive()
