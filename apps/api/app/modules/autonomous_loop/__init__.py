"""
Part 21.8 — AI Autonomous Sales Loop & Event-Driven Orchestration Engine
=========================================================================
Module initializer.
"""
def __getattr__(name: str):
    if name == "autonomous_loop_router":
        from app.modules.autonomous_loop.router import router
        return router
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = ["autonomous_loop_router"]
