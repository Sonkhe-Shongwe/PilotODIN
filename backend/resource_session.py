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


class _ProductBinding:
    def __init__(self, coordinator, autonomy, insight):
        self.coordinator = coordinator
        self.autonomy = autonomy
        self.insight = insight

    def scope_app(self, app):
        async def dispatch(scope, receive, send):
            if "pilotodin.owned_session" in scope:
                raise RuntimeError("Duplicate desktop session binding")
            owned = dict(scope)
            owned["pilotodin.owned_session"] = self
            await app(owned,receive,send)
        return dispatch


def bind_product_routes(source, coordinator, autonomy_owner, owned_insight, *,
                        upload_endpoint, lifespan):
    """Bind the actual endpoint ASGI apps after route match, inside existing
    auth/workspace middleware, before FastAPI reads request bodies.

    The clone is separate from the legacy server. Exact inventory mismatch
    fails startup before publishing any route. No native adapter default.
    """
    from copy import copy
    from fastapi import FastAPI, HTTPException
    from fastapi.routing import APIRoute
    from fastapi.encoders import jsonable_encoder
    from starlette.responses import JSONResponse
    try:
        from .resource_routes import ROUTES
        from .resource_http import OwnedHTTP, settlement
        from .resource_upload import bounded_upload, UploadRefusal
        from .resource_training import TrainingHTTP
    except ImportError:
        from resource_routes import ROUTES
        from resource_http import OwnedHTTP, settlement
        from resource_upload import bounded_upload, UploadRefusal
        from resource_training import TrainingHTTP
    if (not isinstance(coordinator,Coordinator)
            or autonomy_owner.stages.coordinator is not coordinator
            or not callable(owned_insight)):
        raise ValueError("Owned product requires one shared coordinator and host insight adapter")
    observed = {}
    for route in source.router.routes:
        if not isinstance(route, APIRoute):
            if route.path.startswith("/api/"):
                raise RuntimeError("Unclassified product ASGI route")
            continue
        for method in route.methods:
            key=(method,route.path)
            plan=ROUTES.get(key)
            if key in observed or plan is None or route.endpoint.__name__ != plan.endpoint:
                raise RuntimeError("Product resource route inventory changed")
            observed[key]=route
    if set(observed)!=set(ROUTES) or len(set(map(id,observed.values())))!=len(observed):
        raise RuntimeError("Incomplete product resource route inventory")
    if observed[("POST","/api/projects")].endpoint is not upload_endpoint:
        raise RuntimeError("Upload publication endpoint identity changed")
    binding=_ProductBinding(coordinator,autonomy_owner,owned_insight)
    target=FastAPI(title=source.title,version=source.version,lifespan=lifespan,
                   docs_url=None,redoc_url=None,openapi_url=None,
                   exception_handlers=dict(source.exception_handlers))
    target.user_middleware=list(source.user_middleware)

    async def upload(scope,receive,send):
        from starlette.requests import Request
        witness=settlement(scope)
        try:
            async with bounded_upload(Request(scope,receive=receive)) as file:
                witness.begin()
                try:
                    result=await upload_endpoint(file)
                except HTTPException as exc:
                    if exc.status_code < 500:
                        witness.confirm()
                    response=JSONResponse({"detail":exc.detail},status_code=exc.status_code)
                else:
                    witness.confirm()
                    response=JSONResponse(jsonable_encoder(result),status_code=201)
        except UploadRefusal as exc:
            response=JSONResponse({"detail":str(exc)},status_code=exc.status)
        await response(scope,receive,send)

    for original in source.router.routes:
        if not isinstance(original,APIRoute):
            continue
        route=copy(original)
        plan=ROUTES[(next(iter(route.methods)),route.path)]
        if plan.lifetime in ("request","stream"):
            route.app=OwnedHTTP(original.app,coordinator,plan)
        elif plan.lifetime=="training_handoff":
            route.app=TrainingHTTP(original.app,coordinator)
        elif plan.lifetime=="upload":
            class UploadRoute(OwnedHTTP):
                _lifetimes=("upload",)
            route.app=UploadRoute(upload,coordinator,plan)
        elif plan.lifetime in ("autonomy_handoff","staged_inference","control"):
            route.app=binding.scope_app(original.app)
        elif plan.lifetime not in ("metadata","integrity_status"):
            raise RuntimeError("Unclassified resource lifetime")
        target.router.routes.append(route)
    return target
