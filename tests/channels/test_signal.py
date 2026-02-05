"""Tests for Signal channel implementation."""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from nanobot.channels.signal import SignalChannel, UniversalHandler, _markdown_to_signal
from nanobot.config.schema import SignalConfig
from nanobot.bus.queue import MessageBus
from nanobot.bus.events import OutboundMessage


class TestMarkdownConversion:
    """Test markdown to Signal format conversion."""

    def test_empty_text(self):
        """Empty text returns empty string."""
        assert _markdown_to_signal("") == ""

    def test_bold_conversion(self):
        """Bold markdown stays as ** in Signal."""
        text = "This is **bold** text"
        result = _markdown_to_signal(text)
        assert "**bold**" in result

    def test_italic_conversion(self):
        """Italic _text_ converts to *text*."""
        text = "This is _italic_ text"
        result = _markdown_to_signal(text)
        assert "*italic*" in result

    def test_code_inline(self):
        """Inline code backticks are preserved."""
        text = "Use `code` here"
        result = _markdown_to_signal(text)
        assert "`code`" in result

    def test_code_block(self):
        """Code blocks are preserved."""
        text = "```python\nprint('hello')\n```"
        result = _markdown_to_signal(text)
        assert "```" in result
        assert "print('hello')" in result

    def test_headers_stripped(self):
        """Headers # are stripped to plain text."""
        text = "# Heading\n## Subheading"
        result = _markdown_to_signal(text)
        assert "Heading" in result
        assert "Subheading" in result
        assert "#" not in result

    def test_links_converted(self):
        """Links [text](url) convert to text: url."""
        text = "Check [this link](https://example.com)"
        result = _markdown_to_signal(text)
        assert "this link (https://example.com)" in result

    def test_bullet_lists(self):
        """Bullet lists convert to bullet points."""
        text = "- Item 1\n- Item 2"
        result = _markdown_to_signal(text)
        assert "• Item 1" in result
        assert "• Item 2" in result

    def test_blockquotes_stripped(self):
        """Blockquotes > are stripped."""
        text = "> This is a quote"
        result = _markdown_to_signal(text)
        assert "This is a quote" in result
        assert ">" not in result

    def test_complex_markdown(self):
        """Complex markdown with multiple elements."""
        text = """# Title

This has **bold** and _italic_ and `code`.

- Bullet 1
- Bullet 2

```python
def test():
    pass
```

[Link](https://example.com)
"""
        result = _markdown_to_signal(text)
        assert "Title" in result
        assert "**bold**" in result
        assert "*italic*" in result
        assert "`code`" in result
        assert "• Bullet 1" in result
        assert "```" in result
        assert "Link (https://example.com)" in result


class TestSignalConfig:
    """Test SignalConfig schema."""

    def test_default_values(self):
        """Default config has correct values."""
        config = SignalConfig()
        assert config.enabled is False
        assert config.phone_number == ""
        assert config.signal_service == ""
        assert config.allow_from == []

    def test_custom_values(self):
        """Custom config values are set correctly."""
        config = SignalConfig(
            enabled=True,
            phone_number="+14206942069",
            signal_service="127.0.0.1:8080",
            allow_from=["+13072310423"]
        )
        assert config.enabled is True
        assert config.phone_number == "+14206942069"
        assert config.signal_service == "127.0.0.1:8080"
        assert config.allow_from == ["+13072310423"]


class TestSignalChannel:
    """Test SignalChannel class."""

    @pytest.fixture
    def config(self):
        """Create test config."""
        return SignalConfig(
            enabled=True,
            phone_number="+14206942069",
            signal_service="127.0.0.1:8080",
            allow_from=["+13072310423"]
        )

    @pytest.fixture
    def bus(self):
        """Create mock message bus."""
        bus = MagicMock(spec=MessageBus)
        bus.subscribe_outbound = MagicMock()
        bus.unsubscribe_outbound = MagicMock()
        return bus

    @pytest.fixture
    def channel(self, config, bus):
        """Create SignalChannel instance."""
        return SignalChannel(config, bus)

    def test_channel_initialization(self, channel, config, bus):
        """Channel initializes with correct attributes."""
        assert channel.name == "signal"
        assert channel.config == config
        assert channel.bus == bus
        assert channel._bot is None
        assert channel._bot_task is None
        assert channel._universal_handler is None

    def test_is_allowed_empty_list(self, channel):
        """Empty allow_from list allows everyone."""
        channel.config.allow_from = []
        assert channel.is_allowed("+11111111111") is True

    def test_is_allowed_with_list(self, channel):
        """allow_from list restricts access."""
        channel.config.allow_from = ["+13072310423"]
        assert channel.is_allowed("+13072310423") is True
        assert channel.is_allowed("+10000000000") is False

    @pytest.mark.asyncio
    async def test_start_without_phone_number(self, channel):
        """Start fails without phone number."""
        channel.config.phone_number = ""
        await channel.start()
        assert channel._bot is None
        assert channel.is_running is False

    @pytest.mark.asyncio
    async def test_start_without_service(self, channel):
        """Start fails without signal service."""
        channel.config.signal_service = ""
        await channel.start()
        assert channel._bot is None
        assert channel.is_running is False

    @pytest.mark.asyncio
    async def test_stop_channel(self, channel, bus):
        """Stop cleans up resources."""
        channel._running = True

        await channel.stop()

        assert channel._running is False
        bus.unsubscribe_outbound.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_without_bot(self, channel):
        """Send logs warning when bot not initialized."""
        msg = OutboundMessage(
            channel="signal",
            chat_id="+13072310423",
            content="Test message"
        )

        # Should not raise, just log warning
        await channel.send(msg)

    @pytest.mark.asyncio
    async def test_on_outbound_routes_correctly(self, channel):
        """_on_outbound only handles signal channel messages."""
        channel.send = AsyncMock()

        # Signal message - should send
        signal_msg = OutboundMessage(
            channel="signal",
            chat_id="+13072310423",
            content="Test"
        )
        await channel._on_outbound(signal_msg)
        channel.send.assert_called_once_with(signal_msg)

        # Telegram message - should ignore
        channel.send.reset_mock()
        telegram_msg = OutboundMessage(
            channel="telegram",
            chat_id="123",
            content="Test"
        )
        await channel._on_outbound(telegram_msg)
        channel.send.assert_not_called()


class TestUniversalHandler:
    """Test UniversalHandler class."""

    @pytest.fixture
    def channel(self):
        """Create mock channel."""
        channel = MagicMock(spec=SignalChannel)
        channel.is_allowed = MagicMock(return_value=True)
        channel._handle_message = AsyncMock()
        return channel

    @pytest.fixture
    def handler(self, channel):
        """Create handler instance."""
        return UniversalHandler(channel)

    @pytest.fixture
    def mock_context(self):
        """Create mock signalbot Context."""
        context = MagicMock()
        context.message.account = "+13072310423"
        context.message.recipient = "+14206942069"
        context.message.text = "Hello bot"
        context.message.timestamp = 1234567890
        context.message.attachments = []
        return context

    @pytest.mark.asyncio
    async def test_handle_message_success(self, handler, channel, mock_context):
        """Handler forwards message to channel."""
        await handler.handle(mock_context)

        # Should call _handle_message
        channel._handle_message.assert_called_once()
        call_kwargs = channel._handle_message.call_args[1]
        assert call_kwargs['sender_id'] == "+13072310423"
        assert call_kwargs['chat_id'] == "+14206942069"
        assert call_kwargs['content'] == "Hello bot"

    @pytest.mark.asyncio
    async def test_handle_empty_message(self, handler, channel, mock_context):
        """Handler processes empty messages."""
        mock_context.message.text = None

        await handler.handle(mock_context)

        # Should still call _handle_message with empty content
        channel._handle_message.assert_called_once()
        call_kwargs = channel._handle_message.call_args[1]
        assert call_kwargs['content'] == ""

    @pytest.mark.asyncio
    async def test_handle_with_attachments(self, handler, channel, mock_context):
        """Handler includes attachment info."""
        mock_context.message.attachments = ["attachment1", "attachment2"]

        await handler.handle(mock_context)

        # Should include attachments in media
        call_kwargs = channel._handle_message.call_args[1]
        assert "attachment1" in call_kwargs['media']


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
