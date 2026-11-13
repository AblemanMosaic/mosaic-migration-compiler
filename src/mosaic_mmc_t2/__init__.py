"""Explicitly selected T2-D1 semantics; T1 imports/IDs remain unchanged."""
from .registry import profile_reference,capabilities
from .evaluation import assess_profile,replay_assessment
from .planner import plan
from .lifecycle import assess_retirement,assess_routes,assess_lifecycle
from .compiler import compile_domain,verify_compilation
