"""OPC UA client discovery and browsing using asyncua.

Open-source: https://github.com/FreeOpcUa/opcua-asyncua
Supports: Discovery, browsing, reading, subscriptions
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

try:
    from asyncua import Client, ua
    from asyncua.common.node import Node
    ASYNCUA_AVAILABLE = True
except ImportError:
    ASYNCUA_AVAILABLE = False

logger = logging.getLogger(__name__)


class OPCUADiscoveryClient:
    """OPC UA client for device discovery and tag browsing."""

    def __init__(self, endpoint_url: str = "opc.tcp://localhost:4840"):
        self.endpoint_url = endpoint_url
        self._client: Client | None = None

    async def connect(self) -> bool:
        """Connect to the OPC UA server."""
        if not ASYNCUA_AVAILABLE:
            logger.error("asyncua not installed. Run: pip install asyncua")
            return False

        try:
            self._client = Client(url=self.endpoint_url)
            await self._client.connect()
            return True
        except Exception as e:
            logger.error(f"Failed to connect to OPC UA server: {e}")
            return False

    async def disconnect(self) -> None:
        """Disconnect from the OPC UA server."""
        if self._client:
            await self._client.disconnect()
            self._client = None

    async def get_server_info(self) -> dict[str, Any]:
        """Get OPC UA server information."""
        if not self._client:
            return {"error": "Not connected"}

        server = self._client.get_server_node()
        endpoints = await self._client.get_endpoints()

        return {
            "endpoint_url": self.endpoint_url,
            "application_uri": str(await server.read_browse_name()),
            "endpoints": [
                {
                    "url": str(ep.EndpointUrl),
                    "security_mode": str(ep.SecurityMode),
                    "security_policy": str(ep.SecurityPolicyUri),
                }
                for ep in endpoints
            ],
        }

    async def browse_tags(self, node_id: str | None = None) -> list[dict[str, Any]]:
        """Browse OPC UA tags recursively.

        Returns a flat list of all Variable nodes with their browse names and node IDs.
        """
        if not self._client:
            return [{"error": "Not connected"}]

        root = self._client.get_node(node_id) if node_id else self._client.get_objects_node()
        tags = []

        async def _browse_recursive(node: Node, depth: int = 0, max_depth: int = 5) -> None:
            if depth > max_depth:
                return

            try:
                children = await node.get_children()
                for child in children:
                    try:
                        browse_name = await child.read_browse_name()
                        node_class = await child.read_node_class()

                        if node_class == ua.NodeClass.Variable:
                            try:
                                data_value = await child.read_data_value()
                                value = data_value.Value.Value if data_value.Value else None
                                variant_type = str(data_value.Value.VariantType) if data_value.Value else None
                            except Exception:
                                value = None
                                variant_type = None

                            tags.append({
                                "node_id": str(child.nodeid),
                                "browse_name": str(browse_name.Name),
                                "display_name": str((await child.read_display_name()).Text),
                                "value": value,
                                "data_type": variant_type,
                                "path": str(browse_name),
                            })
                        elif node_class == ua.NodeClass.Object:
                            await _browse_recursive(child, depth + 1, max_depth)
                    except Exception as e:
                        logger.debug(f"Error reading child node: {e}")
            except Exception as e:
                logger.debug(f"Error browsing node: {e}")

        await _browse_recursive(root)
        return tags

    async def read_tag(self, node_id: str) -> dict[str, Any]:
        """Read a single tag value by node ID."""
        if not self._client:
            return {"error": "Not connected"}

        try:
            node = self._client.get_node(node_id)
            data_value = await node.read_data_value()
            return {
                "node_id": node_id,
                "value": data_value.Value.Value if data_value.Value else None,
                "timestamp": str(data_value.SourceTimestamp) if data_value.SourceTimestamp else None,
                "status": str(data_value.StatusCode) if data_value.StatusCode else None,
            }
        except Exception as e:
            logger.error(f"Error reading tag {node_id}: {e}")
            return {"node_id": node_id, "error": str(e)}

    async def subscribe_to_tag(
        self, node_id: str, callback: Any, publishing_interval: float = 1000.0
    ) -> dict[str, Any]:
        """Subscribe to a tag for value changes."""
        if not self._client:
            return {"error": "Not connected"}

        try:
            node = self._client.get_node(node_id)
            handler = _SubscriptionHandler(callback)
            subscription = await self._client.create_subscription(
                publishing_interval, handler
            )
            await subscription.subscribe_data_change(node)
            return {
                "node_id": node_id,
                "subscription_id": subscription.subscription_id,
                "status": "subscribed",
            }
        except Exception as e:
            logger.error(f"Error subscribing to tag {node_id}: {e}")
            return {"node_id": node_id, "error": str(e)}

    async def __aenter__(self) -> "OPCUADiscoveryClient":
        await self.connect()
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.disconnect()


class _SubscriptionHandler:
    """Handler for OPC UA subscription callbacks."""

    def __init__(self, callback: Any):
        self.callback = callback

    async def datachange_notification(self, node: Node, val: Any, data: Any) -> None:
        """Called when a subscribed tag value changes."""
        await self.callback(str(node.nodeid), val, data)

    async def event_notification(self, event: Any) -> None:
        """Called when an event is received."""
        pass

    async def status_change_notification(self, status: Any) -> None:
        """Called when the subscription status changes."""
        pass


async def discover_local_servers(discovery_url: str = "opc.tcp://localhost:4840") -> list[dict[str, Any]]:
    """Discover OPC UA servers on the local network.

    Uses the Local Discovery Server (LDS) if available.
    """
    if not ASYNCUA_AVAILABLE:
        return [{"error": "asyncua not installed"}]

    try:
        client = Client(url=discovery_url)
        await client.connect()
        servers = await client.find_servers()
        await client.disconnect()

        return [
            {
                "application_uri": str(s.ApplicationUri),
                "product_uri": str(s.ProductUri),
                "application_name": str(s.ApplicationName.Text) if s.ApplicationName else None,
                "discovery_urls": list(s.DiscoveryUrls) if s.DiscoveryUrls else [],
            }
            for s in servers
        ]
    except Exception as e:
        logger.error(f"Discovery failed: {e}")
        return [{"error": str(e)}]
