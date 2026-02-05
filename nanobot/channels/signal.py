"""Signal channel implementation using signalbot library."""

import asyncio
import re

from loguru import logger
from signalbot import Command, Context
from signalbot import SignalBot

from nanobot.bus.events import OutboundMessage
from nanobot.bus.queue import MessageBus
from nanobot.channels.base import BaseChannel
from nanobot.config.schema import SignalConfig


def _markdown_to_signal(text: str) -> str:
    """
    Convert markdown to Signal-supported formatting.

    Signal supports: **bold**, *italic*, ~strikethrough~, `code`
    """
    if not text:
        return ""

    # 1. Extract and protect code blocks
    code_blocks: list[str] = []

    def save_code_block(m: re.Match) -> str:
        code_blocks.append(m.group(1))
        return f"\x00CB{len(code_blocks) - 1}\x00"

    text = re.sub(r"```[\w]*\n?([\s\S]*?)```", save_code_block, text)

    # 2. Extract and protect inline code
    inline_codes: list[str] = []

    def save_inline_code(m: re.Match) -> str:
        inline_codes.append(m.group(1))
        return f"\x00IC{len(inline_codes) - 1}\x00"

    text = re.sub(r"`([^`]+)`", save_inline_code, text)

    # 3. Headers - just the text
    text = re.sub(r"^#{1,6}\s+(.+)$", r"\1", text, flags=re.MULTILINE)

    # 4. Blockquotes - just the text
    text = re.sub(r"^>\s*(.*)$", r"\1", text, flags=re.MULTILINE)

    # 5. Links [text](url) - convert to just text (Signal doesn't support markdown links)
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1 (\2)", text)

    # 6. Bold **text** or __text__
    text = re.sub(r"\*\*(.+?)\*\*", r"**\1**", text)
    text = re.sub(r"__(.+?)__", r"**\1**", text)

    # 7. Italic *text* or _text_ (avoid matching inside words)
    text = re.sub(r"(?<![a-zA-Z0-9*])\*([^*]+)\*(?![a-zA-Z0-9*])", r"*\1*", text)
    text = re.sub(r"(?<![a-zA-Z0-9])_([^_]+)_(?![a-zA-Z0-9])", r"*\1*", text)

    # 8. Strikethrough ~~text~~
    text = re.sub(r"~~(.+?)~~", r"~\1~", text)

    # 9. Bullet lists
    text = re.sub(r"^[-*]\s+", "• ", text, flags=re.MULTILINE)

    # 10. Restore inline code
    for i, code in enumerate(inline_codes):
        text = text.replace(f"\x00IC{i}\x00", f"`{code}`")

    # 11. Restore code blocks
    for i, code in enumerate(code_blocks):
        text = text.replace(f"\x00CB{i}\x00", f"```\n{code}\n```")

    return text


class UniversalHandler(Command):
    """
    Catch-all handler for Signal messages.

    Forwards all messages to the nanobot bus for processing.
    """

    def __init__(self, channel: "SignalChannel"):
        super().__init__()
        self.channel = channel

    async def handle(self, c: Context) -> None:
        """Forward all Signal messages to nanobot bus."""
        try:
            # Extract sender and recipient information
            account = c.message.account
            recipient = c.message.recipient

            # Use the account (sender) as sender_id
            sender_id = account
            chat_id = recipient  # Reply to the recipient (the bot)

            # Get message text
            content = c.message.text

            if not content:
                content = ""

            # Extract attachments if present
            media_paths = []
            if hasattr(c.message, "attachments") and c.message.attachments:
                for attachment in c.message.attachments:
                    # Store attachment info - actual download would happen elsewhere
                    media_paths.append(str(attachment))

            logger.debug(f"Signal message from {sender_id}: {content[:50]}...")

            # Forward to the message bus
            await self.channel._handle_message(
                sender_id=sender_id,
                chat_id=chat_id,
                content=content,
                media=media_paths,
                metadata={
                    "timestamp": c.message.timestamp,
                    "account": account,
                    "recipient": recipient,
                },
            )
        except Exception as e:
            logger.error(f"Error handling Signal message: {e}")


class SignalChannel(BaseChannel):
    """
    Signal messenger channel using signalbot library.

    Requires signal-cli-rest-api running locally or accessible via network.
    """

    name = "signal"

    def __init__(self, config: SignalConfig, bus: MessageBus):
        super().__init__(config, bus)
        self.config: SignalConfig = config
        self._bot: SignalBot | None = None
        self._bot_task: asyncio.Task | None = None
        self._universal_handler: UniversalHandler | None = None

    async def start(self) -> None:
        """Start Signal bot and message handling."""
        if not self.config.phone_number:
            logger.error("Signal phone_number not configured")
            return

        if not self.config.signal_service:
            logger.error("Signal signal_service (signal-cli-rest-api address) not configured")
            return

        self._running = True

        try:
            # Parse signal_service address
            # Expected format: "host:port" or just "host"
            service_parts = self.config.signal_service.split(":")
            if len(service_parts) == 2:
                host, port = service_parts[0], int(service_parts[1])
            else:
                host, port = service_parts[0], 8080

            # Create the SignalBot instance
            self._bot = SignalBot(
                phone_number=self.config.phone_number,
                signal_service=(host, port),
            )

            # Create and register the universal handler
            self._universal_handler = UniversalHandler(self)
            self._bot.register_command(self._universal_handler)

            # Subscribe to outbound messages from the bus
            self.bus.subscribe_outbound(self._on_outbound)

            # Start the bot in a background task
            self._bot_task = asyncio.create_task(self._run_bot())

            logger.info(
                f"Signal bot started for {self.config.phone_number} "
                f"via {self.config.signal_service}"
            )

        except Exception as e:
            logger.error(f"Failed to start Signal bot: {e}")
            self._running = False

    async def _run_bot(self) -> None:
        """Run the Signal bot (background task)."""
        if not self._bot:
            return

        try:
            await self._bot.start()
        except Exception as e:
            logger.error(f"Signal bot error: {e}")
        finally:
            self._running = False

    async def stop(self) -> None:
        """Stop Signal bot and cleanup."""
        self._running = False

        # Unsubscribe from outbound messages
        self.bus.unsubscribe_outbound(self._on_outbound)

        # Stop the bot
        if self._bot:
            logger.info("Stopping Signal bot...")
            try:
                await self._bot.stop()
            except Exception as e:
                logger.error(f"Error stopping Signal bot: {e}")

        # Cancel the background task
        if self._bot_task:
            self._bot_task.cancel()
            try:
                await self._bot_task
            except asyncio.CancelledError:
                pass

        self._bot = None
        self._bot_task = None
        self._universal_handler = None

    async def send(self, msg: OutboundMessage) -> None:
        """Send a message via Signal."""
        if not self._bot:
            logger.warning("Signal bot not running")
            return

        try:
            # Convert markdown to Signal format
            signal_content = _markdown_to_signal(msg.content)

            # Send the message using signalbot's API
            # Note: signalbot uses a different API - we need to use the send method
            await self._bot.send(
                recipient=msg.chat_id, message=signal_content
            )

            logger.debug(f"Sent Signal message to {msg.chat_id}")

        except Exception as e:
            logger.error(f"Error sending Signal message: {e}")

    async def _on_outbound(self, msg: OutboundMessage) -> None:
        """Handle outbound messages from the bus."""
        if msg.channel == self.name:
            await self.send(msg)
