"""Product inventory and operation discovery for MMC 0.1.0a9."""

from .product import VERSION, REVISION, capabilities, integration_status
from .surface import operation_catalogue
from .protocol import dispatch as dispatch_agent, protocol_manifest, exported_schemas

__all__ = ["VERSION", "REVISION", "capabilities", "integration_status", "operation_catalogue",
           "dispatch_agent", "protocol_manifest", "exported_schemas"]
