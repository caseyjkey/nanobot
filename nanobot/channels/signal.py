"""Signal channel implementation using signalbot library."""

import asyncio
import re
from typing import Any

from loguru import logger

# Try to import signalbot, set placeholders if not available
try:
    from signalbot import SignalBot, Command, Context
    SIGNALBOT_AVAILABLE = True
except ImportError:
    SIGNALBOT_AVAILABLE = False
    # Create placeholder classes to avoid import errors
    class SignalBot:  # type: ignore
        pass
    class Command:  # type: ignore
        pass
    class Context:  # type: ignore
        pass

from nanobot.bus.events import OutboundMessage
from nanobot.bus.queue import MessageBus
from nanobot.channels.base import BaseChannel
from nanobot.config.schema import SignalConfig


def _markdown_to_signal(text: str) -> str:
    """
    Convert markdown to Signal-supported formatting.

    Signal supports:
    - **bold**
    - *italic*
    - ~strikethrough~
    - `code`
    """
    if not text:
        return ""

    # Extract and protect code blocks
    code_blocks: list[str] = []
    def save_code_block(m: re.Match) -> str:
        code_blocks.append(m.group(1))
        return f"\x00CB{len(code_blocks) - 1}\x00"

    text = re.sub(r'```[\w]*\n?([\s\S]*?)```', save_code_block, text)

    # Extract and protect inline code
    inline_codes: list[str] = []
    def save_inline_code(m: re.Match) -> str:
        inline_codes.append(m.group(1))
        return f"\x00IC{len(inline_codes) - 1}\x00"

    text = re.sub(r'`([^`]+)`', save_inline_code, text)

    # Headers # Title -> just the title text
    text = re.sub(r'^#{1,6}\s+(.+)$', r'\1', text, flags=re.MULTILINE)

    # Blockquotes > text -> just the text
    text = re.sub(r'^>\s*(.*)$', r'\1', text, flags=re.MULTILINE)

    # Links [text](url) -> text: url
    text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'\1: \2', text)

    # Bold **text** or __text__ stays as-is (Signal supports **)
    # Italic _text_ -> *text* (Signal uses *)
    text = re.sub(r'(?<![a-zA-Z0-9])_([^_]+)_(?![a-zA-Z0-9])', r'*\1*', text)

    # Bullet lists - item -> • item
    text = re.sub(r'^[-*]\s+', '• ', text, flags=re.MULTILINE)

    # Restore inline code
    for i, code in enumerate(inline_codes):
        text = text.replace(f"\x00IC{i}\x00", f"`{code}`")

    # Restore code blocks
    for i, code in enumerate(code_blocks):
        text = text.replace(f"\x00CB{i}\x00", f"```\n{code}\n```")

    return text


class UniversalHandler(Command):
    """Catch-all handler for Signal messages."""

    def __init__(self, channel: 'SignalChannel'):
        if SIGNALBOT_AVAILABLE:
            super().__init__()
        self.channel = channel

    async def handle(self, c: Context) -> None:
        """Forward all messages to nanobot bus."""
        try:
            # Extract sender and content
            sender_id = c.message.source
            if not sender_id:
                logger.warning("Received message with no sender")
                return

            # Get message content
            content = c.message.text or ""
            if not content:
                logger.debug("Received empty message, skipping")
                return

            # Check permissions
            if not self.channel.is_allowed(sender_id):
                logger.warning(f"Message from {sender_id} not allowed")
                await c.send("Sorry, you're not authorized to use this bot.")
                return

            logger.debug(f"Signal message from {sender_id}: {content[:50]}...")

            # Store context for replies
            self.channel._contexts[sender_id] = c

            # Forward to the message bus
            await self.channel._handle_message(
                sender_id=sender_id,
                chat_id=sender_id,  # For Signal, sender = chat in 1-1 conversations
                content=content,
                media=[],
                metadata={
                    "timestamp": c.message.timestamp,
                    "is_group": c.message.group_id is not None,
                    "group_id": c.message.group_id,
                }
            )
        except Exception as e:
            logger.error(f"Error handling Signal message: {e}", exc_info=True)


class SignalChannel(BaseChannel):
    """Signal messenger channel using signalbot library."""

    name = "signal"

    def __init__(self, config: SignalConfig, bus: MessageBus):
        super().__init__(config, bus)
        self.config: SignalConfig = config
        self._bot: SignalBot | None = None
        self._bot_task: asyncio.Task | None = None
        self._contexts: dict[str, Context] = {}  # Map sender_id to Context for replies
        self._subscription_id: str | None = None

    async def start(self) -> None:
        """Start Signal bot and message handling."""
        if not SIGNALBOT_AVAILABLE:
            logger.error("signalbot library not installed. Cannot start Signal channel.")
            logger.error("Install with: pip install signalbot")
            return

        if not self.config.phone_number:
            logger.error("Signal phone number not configured")
            return

        if not self.config.signal_service:
            logger.error("Signal service address not configured")
            return

        try:
            logger.info(f"Starting Signal channel for {self.config.phone_number}...")

            # Create SignalBot instance
            self._bot = SignalBot({
                "signal_service": self.config.signal_service,
                "phone_number": self.config.phone_number
            })

            # Register universal handler
            handler = UniversalHandler(self)
            self._bot.register(handler)

            # Start bot in background
            self._bot_task = asyncio.create_task(self._run_bot())

            # Subscribe to outbound messages from the bus
            self._subscription_id = await self.bus.subscribe_outbound(self._on_outbound)

            self._running = True
            logger.info(f"✓ Signal channel started (bot: {self.config.phone_number})")

        except Exception as e:
            logger.error(f"Failed to start Signal channel: {e}", exc_info=True)
            self._running = False

    async def _run_bot(self) -> None:
        """Run the SignalBot event loop."""
        try:
            if self._bot:
                # signalbot.start() is blocking, so we run it in executor
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, self._bot.start)
        except Exception as e:
            logger.error(f"SignalBot error: {e}", exc_info=True)

    async def stop(self) -> None:
        """Stop Signal bot and cleanup."""
        logger.info("Stopping Signal channel...")

        self._running = False

        # Unsubscribe from bus
        if self._subscription_id:
            await self.bus.unsubscribe_outbound(self._subscription_id)
            self._subscription_id = None

        # Stop bot task
        if self._bot_task:
            self._bot_task.cancel()
            try:
                await self._bot_task
            except asyncio.CancelledError:
                pass
            self._bot_task = None

        self._bot = None
        self._contexts.clear()

        logger.info("✓ Signal channel stopped")

    async def send(self, msg: OutboundMessage) -> None:
        """Send message via Signal."""
        if not self._bot:
            logger.warning("Signal bot not initialized, cannot send message")
            return

        try:
            recipient = msg.chat_id

            # Convert markdown to Signal format
            content = _markdown_to_signal(msg.content)

            # Try to use stored context for rich replies
            context = self._contexts.get(recipient)
            if context:
                await context.send(content)
            else:
                # Fallback: use bot.send directly
                # Note: signalbot API may differ, adjust as needed
                logger.debug(f"Sending to {recipient}: {content[:50]}...")
                # This is a simplified version - actual signalbot API may vary
                # await self._bot.send(recipient, content)
                logger.warning("Direct send not implemented yet, needs Context")

        except Exception as e:
            logger.error(f"Failed to send Signal message: {e}", exc_info=True)

    async def _on_outbound(self, msg: OutboundMessage) -> None:
        """Handle outbound messages from bus."""
        if msg.channel == self.name:
            await self.send(msg)
