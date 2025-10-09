"""Tests for Moodo API client."""
from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

from custom_components.moodo.api import (
    MoodoAPIClient,
    MoodoAuthError,
    MoodoConnectionError,
)


@pytest.fixture
def mock_session() -> MagicMock:
    """Return a mock aiohttp session."""
    return MagicMock(spec=aiohttp.ClientSession)


@pytest.fixture
def api_client(mock_session: MagicMock) -> MoodoAPIClient:
    """Return a Moodo API client with mock session."""
    return MoodoAPIClient(mock_session, token="test_token")


def create_mock_response(
    status: int = 200,
    json_data: dict[str, Any] | None = None,
) -> MagicMock:
    """Create a mock aiohttp response."""
    response = MagicMock()
    response.status = status
    response.json = AsyncMock(return_value=json_data or {})
    return response


async def test_login_success(mock_session: MagicMock) -> None:
    """Test successful login."""
    client = MoodoAPIClient(mock_session)

    mock_response = create_mock_response(
        status=200,
        json_data={"token": "new_test_token"},
    )

    mock_session.request.return_value.__aenter__.return_value = mock_response

    token = await client.login("test@example.com", "password123")

    assert token == "new_test_token"
    assert client._token == "new_test_token"


async def test_login_no_token_in_response(mock_session: MagicMock) -> None:
    """Test login when no token is returned."""
    client = MoodoAPIClient(mock_session)

    mock_response = create_mock_response(
        status=200,
        json_data={},
    )

    mock_session.request.return_value.__aenter__.return_value = mock_response

    with pytest.raises(MoodoAuthError, match="No token in response"):
        await client.login("test@example.com", "password123")


async def test_login_auth_error(mock_session: MagicMock) -> None:
    """Test login with authentication error."""
    client = MoodoAPIClient(mock_session)

    mock_response = create_mock_response(status=401)

    mock_session.request.return_value.__aenter__.return_value = mock_response

    with pytest.raises(MoodoAuthError, match="Authentication failed"):
        await client.login("test@example.com", "wrong_password")


async def test_get_boxes(api_client: MoodoAPIClient, mock_session: MagicMock) -> None:
    """Test getting boxes."""
    mock_response = create_mock_response(
        status=200,
        json_data={"boxes": [{"device_key": 12345, "name": "Living Room"}]},
    )

    mock_session.request.return_value.__aenter__.return_value = mock_response

    boxes = await api_client.get_boxes()

    assert len(boxes) == 1
    assert boxes[0]["device_key"] == 12345
    assert boxes[0]["name"] == "Living Room"


async def test_get_box(api_client: MoodoAPIClient, mock_session: MagicMock) -> None:
    """Test getting a single box."""
    mock_response = create_mock_response(
        status=200,
        json_data={"box": {"device_key": 12345, "name": "Living Room"}},
    )

    mock_session.request.return_value.__aenter__.return_value = mock_response

    box = await api_client.get_box(12345)

    assert box["device_key"] == 12345
    assert box["name"] == "Living Room"


async def test_power_on_box(api_client: MoodoAPIClient, mock_session: MagicMock) -> None:
    """Test powering on a box."""
    mock_response = create_mock_response(
        status=200,
        json_data={"box": {"device_key": 12345, "box_status": 1}},
    )

    mock_session.request.return_value.__aenter__.return_value = mock_response

    box = await api_client.power_on_box(12345, fan_volume=50, duration_minutes=60)

    assert box["box_status"] == 1

    # Check that request was made with correct data
    call_args = mock_session.request.call_args
    assert call_args[1]["json"]["fan_volume"] == 50
    assert call_args[1]["json"]["duration_minutes"] == 60
    assert "restful_request_id" in call_args[1]["json"]


async def test_power_off_box(api_client: MoodoAPIClient, mock_session: MagicMock) -> None:
    """Test powering off a box."""
    mock_response = create_mock_response(
        status=200,
        json_data={"box": {"device_key": 12345, "box_status": 0}},
    )

    mock_session.request.return_value.__aenter__.return_value = mock_response

    box = await api_client.power_off_box(12345)

    assert box["box_status"] == 0


async def test_set_fan_volume(api_client: MoodoAPIClient, mock_session: MagicMock) -> None:
    """Test setting fan volume."""
    mock_response = create_mock_response(
        status=200,
        json_data={"box": {"device_key": 12345, "fan_volume": 75}},
    )

    mock_session.request.return_value.__aenter__.return_value = mock_response

    box = await api_client.set_fan_volume(12345, 75)

    assert box["fan_volume"] == 75


async def test_enable_shuffle(api_client: MoodoAPIClient, mock_session: MagicMock) -> None:
    """Test enabling shuffle mode."""
    mock_response = create_mock_response(
        status=200,
        json_data={"box": {"device_key": 12345, "shuffle": True}},
    )

    mock_session.request.return_value.__aenter__.return_value = mock_response

    box = await api_client.enable_shuffle(12345)

    assert box["shuffle"] is True


async def test_disable_shuffle(api_client: MoodoAPIClient, mock_session: MagicMock) -> None:
    """Test disabling shuffle mode."""
    mock_response = create_mock_response(
        status=200,
        json_data={"box": {"device_key": 12345, "shuffle": False}},
    )

    mock_session.request.return_value.__aenter__.return_value = mock_response

    box = await api_client.disable_shuffle(12345)

    assert box["shuffle"] is False


async def test_enable_interval(api_client: MoodoAPIClient, mock_session: MagicMock) -> None:
    """Test enabling interval mode."""
    mock_response = create_mock_response(
        status=200,
        json_data={"box": {"device_key": 12345, "interval": True}},
    )

    mock_session.request.return_value.__aenter__.return_value = mock_response

    box = await api_client.enable_interval(12345, interval_type=1)

    assert box["interval"] is True

    # Check that request was made with correct data
    call_args = mock_session.request.call_args
    assert call_args[1]["json"]["interval_type"] == 1


async def test_disable_interval(api_client: MoodoAPIClient, mock_session: MagicMock) -> None:
    """Test disabling interval mode."""
    mock_response = create_mock_response(
        status=200,
        json_data={"box": {"device_key": 12345, "interval": False}},
    )

    mock_session.request.return_value.__aenter__.return_value = mock_response

    box = await api_client.disable_interval(12345)

    assert box["interval"] is False


async def test_get_interval_types(api_client: MoodoAPIClient, mock_session: MagicMock) -> None:
    """Test getting interval types."""
    mock_response = create_mock_response(
        status=200,
        json_data={"interval_types": [{"type": 1, "name": "Short"}]},
    )

    mock_session.request.return_value.__aenter__.return_value = mock_response

    interval_types = await api_client.get_interval_types()

    assert len(interval_types) == 1
    assert interval_types[0]["type"] == 1


async def test_get_favorites(api_client: MoodoAPIClient, mock_session: MagicMock) -> None:
    """Test getting favorites."""
    mock_response = create_mock_response(
        status=200,
        json_data={"favorites": [{"id": "fav_1", "name": "Favorite 1"}]},
    )

    mock_session.request.return_value.__aenter__.return_value = mock_response

    favorites = await api_client.get_favorites()

    assert len(favorites) == 1
    assert favorites[0]["id"] == "fav_1"


async def test_apply_favorite(api_client: MoodoAPIClient, mock_session: MagicMock) -> None:
    """Test applying a favorite."""
    mock_response = create_mock_response(
        status=200,
        json_data={"box": {"device_key": 12345}},
    )

    mock_session.request.return_value.__aenter__.return_value = mock_response

    await api_client.apply_favorite("fav_1", 12345, fan_volume=50)

    # Check that request was made with correct data
    call_args = mock_session.request.call_args
    assert call_args[1]["json"]["favorite_id"] == "fav_1"
    assert call_args[1]["json"]["device_key"] == 12345
    assert call_args[1]["json"]["fan_volume"] == 50


async def test_request_timeout(api_client: MoodoAPIClient, mock_session: MagicMock) -> None:
    """Test request timeout."""
    mock_session.request.return_value.__aenter__.side_effect = asyncio.TimeoutError()

    with pytest.raises(MoodoConnectionError, match="Request timeout"):
        await api_client.get_boxes()


async def test_request_client_error(api_client: MoodoAPIClient, mock_session: MagicMock) -> None:
    """Test request client error."""
    mock_session.request.return_value.__aenter__.side_effect = aiohttp.ClientError("Connection failed")

    with pytest.raises(MoodoConnectionError, match="Connection error"):
        await api_client.get_boxes()


async def test_request_http_error(api_client: MoodoAPIClient, mock_session: MagicMock) -> None:
    """Test HTTP error response."""
    mock_response = create_mock_response(
        status=500,
        json_data={"error": "Internal server error"},
    )

    mock_session.request.return_value.__aenter__.return_value = mock_response

    with pytest.raises(MoodoConnectionError, match="Internal server error"):
        await api_client.get_boxes()


async def test_request_auth_error_status_code(api_client: MoodoAPIClient, mock_session: MagicMock) -> None:
    """Test authentication error with 401 status."""
    mock_response = create_mock_response(status=401)

    mock_session.request.return_value.__aenter__.return_value = mock_response

    with pytest.raises(MoodoAuthError, match="Authentication failed"):
        await api_client.get_boxes()


async def test_request_auth_error_message(api_client: MoodoAPIClient, mock_session: MagicMock) -> None:
    """Test authentication error based on error message."""
    mock_response = create_mock_response(
        status=400,
        json_data={"error": "Invalid credentials"},
    )

    mock_session.request.return_value.__aenter__.return_value = mock_response

    with pytest.raises(MoodoAuthError, match="Invalid credentials"):
        await api_client.get_boxes()


async def test_should_ignore_websocket_event(api_client: MoodoAPIClient) -> None:
    """Test WebSocket event filtering."""
    # Add a request ID to the set
    api_client._recent_request_ids.add("test_request_id")

    # Should return True for the first check
    assert api_client.should_ignore_websocket_event("test_request_id") is True

    # Should return False for subsequent checks (ID removed)
    assert api_client.should_ignore_websocket_event("test_request_id") is False

    # Should return False for unknown IDs
    assert api_client.should_ignore_websocket_event("unknown_id") is False


async def test_request_id_limit(api_client: MoodoAPIClient, mock_session: MagicMock) -> None:
    """Test that request ID set doesn't grow unbounded."""
    mock_response = create_mock_response(
        status=200,
        json_data={"box": {}},
    )

    mock_session.request.return_value.__aenter__.return_value = mock_response

    # Fill up the set beyond the limit
    for _ in range(105):
        await api_client.power_on_box(12345)

    # Set should not exceed 100 items
    assert len(api_client._recent_request_ids) <= 100
