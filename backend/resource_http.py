"""Staged C1 full-ASGI lifetime adapter, not registered in the live application.

The caller must select a trusted, matched route plan and run this *inside*
authentication and workspace guards, outside the entire downstream ASGI call.
Do not use BaseHTTPMiddleware.call_next as the completion witness. This adapter
is only for reviewed request/stream operations with no detached work. Upload
parsing, training/autonomy handoff and staged inference require separate
integration. No browser-provided lease or scope flag is accepted.
"""
from starlette.responses import JSONResponse

try:
    from .resource_admission import Coordinator, Operation, Admission, GIB
    from .resource_routes import RoutePlan, ROUTES
except ImportError:
    from resource_admission import Coordinator, Operation, Admission, GIB
    from resource_routes import RoutePlan, ROUTES


class OwnedHTTP:
    """Retain one admission through the complete downstream ASGI lifetime.

    The trusted coordinator's observers must be bounded and must not perform
    heavyweight work. The downstream must await actual worker/stream cleanup.
    Normal ASGI return is a witness only under that reviewed contract; an
    escaping exception or cancellation is deliberately not proof of cleanup.
    """
    _lifetimes = ("request", "stream")

    def __init__(self, app, coordinator: Coordinator, plan: RoutePlan):
        if (plan not in ROUTES.values() or plan.lifetime not in self._lifetimes
                or plan.operation is None):
            raise ValueError("Route requires a different admission lifetime")
        self.app = app
        self.coordinator = coordinator
        self.operation = Operation(plan.operation)

    async def _refuse(self, scope, receive, send, admission: Admission):
        await JSONResponse({"detail": {
            "code": admission.code,
            "operation": self.operation.value,
            "message": "Local resources unavailable. Review status before retrying.",
            "available_gib": (None if admission.available_bytes is None
                              else admission.available_bytes / GIB),
            "required_free_gib": admission.required_bytes / GIB,
            "retryable": True,
        }}, status_code=503)(scope, receive, send)

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http":
            raise ValueError("OwnedHTTP requires an HTTP scope")
        # Synchronous, bounded observation: no cancellation window between
        # obtaining an opaque lease and establishing the ownership handler.
        admission = self.coordinator.try_acquire(self.operation)
        lease = admission.lease
        if lease is None:
            await self._refuse(scope, receive, send, admission)
            return
        if not self.coordinator.start(lease):
            # No downstream work was started. Release only this exact owner.
            self.coordinator.release(lease)
            await self._refuse(scope, receive, send, Admission(
                None, "shutting_down", admission.required_bytes,
                admission.available_bytes))
            return
        try:
            # Includes background callbacks and streaming finalizers only if
            # the downstream actually awaits them. Never release on headers.
            await self.app(scope, receive, send)
        except BaseException:
            self.coordinator.block(lease)
            raise
        else:
            if not self.coordinator.release(lease):
                self.coordinator.block(lease)
                raise RuntimeError("Resource ownership could not be settled")
