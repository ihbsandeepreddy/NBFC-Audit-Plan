"""
WebSocket connection manager for real-time engagement updates
Manages rooms per engagement and broadcasts events to all connected users
"""

import json
import logging
from typing import Dict, Set, List
from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages WebSocket connections per engagement"""

    def __init__(self):
        # engagement_id -> set of connected websocket connections
        self.active_connections: Dict[str, Set[WebSocket]] = {}
        # engagement_id -> activity log
        self.activity_log: Dict[str, List[dict]] = {}

    async def connect(self, websocket: WebSocket, engagement_id: str):
        """Accept and register a new connection"""
        await websocket.accept()
        if engagement_id not in self.active_connections:
            self.active_connections[engagement_id] = set()
            self.activity_log[engagement_id] = []

        self.active_connections[engagement_id].add(websocket)
        logger.info(f"User connected to engagement {engagement_id}. Active: {len(self.active_connections[engagement_id])}")

    def disconnect(self, websocket: WebSocket, engagement_id: str):
        """Unregister and disconnect a connection"""
        if engagement_id in self.active_connections:
            self.active_connections[engagement_id].discard(websocket)
            if not self.active_connections[engagement_id]:
                del self.active_connections[engagement_id]
                del self.activity_log[engagement_id]
        logger.info(f"User disconnected from engagement {engagement_id}")

    async def broadcast(self, engagement_id: str, message: str):
        """Broadcast a message to all users in an engagement room"""
        if engagement_id not in self.active_connections:
            return

        try:
            message_data = json.loads(message)

            # Log activity
            if engagement_id in self.activity_log:
                self.activity_log[engagement_id].append(message_data)

            # Broadcast to all connected clients
            disconnected = set()
            for connection in self.active_connections[engagement_id]:
                try:
                    await connection.send_text(message)
                except Exception as e:
                    logger.error(f"Error broadcasting to connection: {e}")
                    disconnected.add(connection)

            # Remove disconnected clients
            for conn in disconnected:
                self.disconnect(conn, engagement_id)

        except json.JSONDecodeError:
            logger.error("Invalid JSON message received")

    async def send_personal(self, websocket: WebSocket, message: dict):
        """Send a message to a specific connection"""
        try:
            await websocket.send_text(json.dumps(message))
        except Exception as e:
            logger.error(f"Error sending personal message: {e}")

    def get_activity_log(self, engagement_id: str, limit: int = 100) -> List[dict]:
        """Get recent activity log for an engagement"""
        if engagement_id in self.activity_log:
            return self.activity_log[engagement_id][-limit:]
        return []


# Global connection manager instance
connection_manager = ConnectionManager()
