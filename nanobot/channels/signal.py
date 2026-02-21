"""Signal channel implementation using signalbot library."""

import asyncio
import threading
import re
from typing import Awaitable, Callable

from loguru import logger

from nanobot.bus.events import OutboundMessage
from nanobot.bus.queue import MessageBus
from nanobot.channels.base import BaseChannel
from nanobot.config.schema import SignalConfig


def _markdown_to_signal(text: str) -> str:
    """Convert markdown to Signal-supported formatting."""
    if not text:
        return ""

    # Code blocks
    code_blocks = []
    def save_code_block(m):
        code_blocks.append(m.group(1))
        return f"\x00CB{len(code_blocks) - 1}\x00"
    text = re.sub(r"```[\w]*\n?([\s\S]*?)```", save_code_block, text)

    # Inline code
    inline_codes = []
    def save_inline_code(m):
        inline_codes.append(m.group(1))
        return f"\x00IC{len(inline_codes) - 1}\x00"
    text = re.sub(r"`([^`]+)`", save_inline_code, text)

    # Headers
    text = re.sub(r"^#{1,6}\s+(.+)$", r"\1", text, flags=re.MULTILINE)

    # Blockquotes
    text = re.sub(r"^>\s*(.*)$", r"\1", text, flags=re.MULTILINE)

    # Links
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1 (\2)", text)

    # Bold
    text = re.sub(r"\*\*(.+?)\*\*", r"**\1**", text)
    text = re.sub(r"__(.+?)__", r"**\1**", text)

    # Italic
    text = re.sub(r"(?<![a-zA-Z0-9*])\*([^*]+)\*(?![a-zA-Z0-9*])", r"*\1*", text)

    # Strikethrough
    text = re.sub(r"~~(.+?)~~", r"~\1~", text)

    # Bullet lists
    text = re.sub(r"^[-*]\s+", "• ", text, flags=re.MULTILINE)

    # Restore inline code
    for i, code in enumerate(inline_codes):
        text = text.replace(f"\x00IC{i}\x00", f"`{code}`")

    # Restore code blocks
    for i, code in enumerate(code_blocks):
        text = text.replace(f"\x00CB{i}\x00", f"```\n{code}\n```")

    return text


class UniversalHandler:
    """Catch-all handler for Signal messages."""

    def __init__(self, channel: "SignalChannel"):
        self.channel = channel
        self.bot = None  # Set by signalbot after registration

    def setup(self) -> None:
        """Called by signalbot during registration."""
        return

    async def handle(self, c) -> None:
        """Forward Signal messages to nanobot bus."""
        try:
            # Debug logging
            logger.info(f"Raw envelope keys: {c.message.raw_message[:200] if c.message.raw_message else 'None'}...")
            logger.info(f"Message source: {c.message.source}, source_number: {c.message.source_number}, source_uuid: {c.message.source_uuid}")
            
            sender_id = c.message.source_number or c.message.source
            chat_id = c.message.source_number or c.message.source  # Reply to sender
            content = c.message.text or ""

            logger.debug(f"Signal message from {sender_id}: {content[:50]}...")

            await self.channel._handle_message(
                sender_id=sender_id,
                chat_id=chat_id,
                content=content,
                media=[],
                metadata={
                    "timestamp": c.message.timestamp,
                    "uuid": c.message.source_uuid,
                },
            )
        except Exception as e:
            logger.error(f"Error handling Signal message: {e}")


class SignalChannel(BaseChannel):
    """Signal messenger channel using signalbot library."""

    name = "signal"

    def __init__(self, config: SignalConfig, bus: MessageBus):
        super().__init__(config, bus)
        self.config: SignalConfig = config
        self._bot = None
        self._bot_thread = None
        self._universal_handler = None
        self._stop_event = threading.Event()

    async def start(self) -> None:
        """Start Signal bot in a separate thread with its own event loop."""
        if not self.config.phone_number:
            logger.error("Signal phone_number not configured")
            return

        if not self.config.signal_service:
            logger.error("Signal signal_service not configured")
            return

        self._running = True
        self._stop_event.clear()

        # Parse service address
        parts = self.config.signal_service.split(":")
        host = parts[0]
        port = int(parts[1]) if len(parts) == 2 else 8080

        # Store config for thread to use
        self._bot_config = {
            "phone_number": self.config.phone_number,
            "signal_service": self.config.signal_service,  # Already a string "host:port"
            "storage": {"type": "in-memory"}
        }

        # Subscribe to outbound messages
        self.bus.subscribe_outbound(self.name, self._on_outbound)

        # Start bot in separate thread - bot will be created IN the thread
        self._bot_thread = threading.Thread(
            target=self._run_bot_in_thread,
            name="signalbot",
            daemon=False
        )
        self._bot_thread.start()

        # Give thread time to start
        await asyncio.sleep(0.1)

        logger.info(f"Signal bot starting for {self.config.phone_number} via {self.config.signal_service}")

    def _run_bot_in_thread(self):
        """Run signalbot in a thread with a fresh event loop policy."""
        logger.info("[Signal thread] Starting...")
        
        # Create a new event loop policy for this thread
        policy = asyncio.DefaultEventLoopPolicy()
        asyncio.set_event_loop_policy(policy)
        logger.info(f"[Signal thread] Event loop policy set: {policy}")

        # Create new event loop for this thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        logger.info(f"[Signal thread] Event loop created: {loop}")

        try:
            # Create the bot HERE in the thread so it gets this loop
            from signalbot import SignalBot
            logger.info("[Signal thread] Creating SignalBot...")
            self._bot = SignalBot(self._bot_config)
            logger.info(f"[Signal thread] SignalBot created: {self._bot}")

            # Create handler
            self._universal_handler = UniversalHandler(self)
            logger.info("[Signal thread] Registering handler...")
            self._bot.register(self._universal_handler)
            logger.info("[Signal thread] Handler registered")

            logger.info("[Signal thread] Starting bot.run_forever()...")
            
            # Now start the bot - it will use this thread's loop
            self._bot.start(run_forever=True)
            logger.info("[Signal thread] Bot.start() returned!")
        except Exception as e:
            import traceback
            logger.error(f"[Signal thread] Error: {e}")
            logger.error(traceback.format_exc())
        finally:
            logger.info("[Signal thread] Thread exiting")
            loop.close()
            self._running = False

    async def stop(self) -> None:
        """Stop Signal bot."""
        self._running = False
        self._stop_event.set()

        # Signal the bot to stop by stopping its event loop
        if self._bot and hasattr(self._bot, '_event_loop'):
            def stop_loop():
                try:
                    self._bot._event_loop.call_soon_threadsafe(self._bot._event_loop.stop)
                except Exception as e:
                    logger.error(f"Error stopping bot loop: {e}")

            # Run stop_loop in the bot's thread context
            if self._bot_thread and self._bot_thread.is_alive():
                self._bot_thread.join(timeout=2)

        self._bot = None
        self._bot_thread = None
        self._universal_handler = None
        logger.info("Signal bot stopped")

    async def send(self, msg: OutboundMessage) -> None:
        """Send a message via Signal."""
        if not self._bot:
            logger.warning("Signal bot not running")
            return

        try:
            signal_content = _markdown_to_signal(msg.content)

            # The bot runs in its own thread with its own event loop
            # We need to schedule the send coroutine on that loop
            bot_loop = self._bot._event_loop
            future = asyncio.run_coroutine_threadsafe(
                self._bot.send(msg.chat_id, signal_content),
                bot_loop
            )
            # Wait for the send to complete
            await asyncio.wrap_future(future)

            logger.debug(f"Sent Signal message to {msg.chat_id}")
        except Exception as e:
            logger.error(f"Error sending Signal message: {e}")

    async def _on_outbound(self, msg: OutboundMessage) -> None:
        """Handle outbound messages from the bus."""
        if msg.channel == self.name:
            await self.send(msg)
