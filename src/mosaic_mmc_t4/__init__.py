"""Explicit MMC T4 interface extension. No native host is auto-bound."""
from ._pins import VERSION as __version__
from .views import snapshot,assess_view,replay_view,journal_view
from .work import make_work_order,review_submission
from .host import AgentHost,ReadSession
from .sdk import Registry
from .abi import dispatch,capabilities
__all__=['snapshot','assess_view','replay_view','journal_view','make_work_order','review_submission','AgentHost','ReadSession','Registry','dispatch','capabilities']
