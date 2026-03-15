from copy import deepcopy
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from nanobot.agent.loop import AgentLoop
from nanobot.bus.events import InboundMessage
from nanobot.bus.queue import MessageBus
from nanobot.providers.base import LLMResponse


PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"0" * 32


def _make_loop(tmp_path: Path) -> AgentLoop:
    bus = MessageBus()
    provider = MagicMock()
    provider.get_default_model.return_value = "test-model"
    loop = AgentLoop(bus=bus, provider=provider, workspace=tmp_path, model="test-model")
    loop.tools.get_definitions = MagicMock(return_value=[{"type": "function", "function": {"name": "analyze_image"}}])
    return loop


@pytest.mark.asyncio
async def test_process_message_retries_image_unsupported_with_hint_and_stripped_media(tmp_path: Path) -> None:
    loop = _make_loop(tmp_path)

    calls: list[list[dict]] = []

    async def scripted_chat_with_retry(*, messages, **kwargs):
        calls.append(deepcopy(messages))
        if len(calls) == 1:
            return LLMResponse(content="image input is not supported", finish_reason="error")
        return LLMResponse(content="Use the analyze_image tool", tool_calls=[])

    loop.provider.chat_with_retry = AsyncMock(side_effect=scripted_chat_with_retry)

    image = tmp_path / "cake.png"
    image.write_bytes(PNG_BYTES)

    msg = InboundMessage(
        channel="discord",
        sender_id="user1",
        chat_id="chat123",
        content="how make cake",
        media=[str(image)],
    )

    result = await loop._process_message(msg)

    assert result is not None
    assert result.content == "Use the analyze_image tool"
    assert loop.provider.chat_with_retry.await_count == 2

    first_messages, second_messages = calls
    first_user = first_messages[-1]["content"]
    second_system = second_messages[0]["content"]
    second_user = second_messages[-1]["content"]

    assert isinstance(first_user, list)
    assert any(block.get("type") == "image_url" for block in first_user)

    assert "could not inspect the attached image directly" in second_system.lower()
    assert "if image-analysis tools are available, use them before answering" in second_system.lower()

    assert isinstance(second_user, list)
    assert all(block.get("type") != "image_url" for block in second_user)
    assert any(block.get("text") == "[image omitted]" for block in second_user)


@pytest.mark.asyncio
async def test_process_message_does_not_inject_hint_when_model_handles_images(tmp_path: Path) -> None:
    loop = _make_loop(tmp_path)
    seen_messages: list[list[dict]] = []

    async def scripted_chat_with_retry(*, messages, **kwargs):
        seen_messages.append(deepcopy(messages))
        return LLMResponse(content="looks like a cake", tool_calls=[])

    loop.provider.chat_with_retry = AsyncMock(side_effect=scripted_chat_with_retry)

    image = tmp_path / "cake.png"
    image.write_bytes(PNG_BYTES)

    msg = InboundMessage(
        channel="signal",
        sender_id="user1",
        chat_id="chat123",
        content="what is this",
        media=[str(image)],
    )

    result = await loop._process_message(msg)

    assert result is not None
    assert result.content == "looks like a cake"
    assert loop.provider.chat_with_retry.await_count == 1
    assert "could not inspect the attached image directly" not in seen_messages[0][0]["content"].lower()
