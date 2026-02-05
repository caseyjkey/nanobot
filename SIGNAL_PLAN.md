# Signal Integration Implementation Plan

## Overview

Integrate Signal messenger support into nanobot using the `signalbot` library, following the existing architecture patterns established by Telegram and WhatsApp channel implementations.

**Goal**: Enable users to interact with their nanobot agent via Signal messenger.

## Research & Context

### signalbot Library
- **Repository**: [filipre/signalbot](https://github.com/filipre/signalbot)
- **PyPI**: [signalbot](https://pypi.org/project/signalbot/)
- **Latest Version**: 0.19.1+
- **Python Version**: Python 3.11+ (matches nanobot requirements)

### Key Features
- Async/await based (compatible with nanobot's async architecture)
- Command-based with decorators (`@triggered`, `@regex_triggered`)
- Context API for send, reply, react, edit, typing indicators
- Producer-consumer architecture for message handling
- WebSocket-based message receiving

### Dependencies Required
```python
signalbot>=0.19.1  # Main library
```

**External Service**: Requires `signal-cli-rest-api` running (Docker or standalone)

## Architecture Analysis

### Current nanobot Channel Pattern

Based on `nanobot/channels/base.py`:

```python
class BaseChannel(ABC):
    name: str = "base"
    
    def __init__(self, config: Any, bus: MessageBus)
    async def start() -> None
    async def stop() -> None
    async def send(msg: OutboundMessage) -> None
    def is_allowed(sender_id: str) -> bool
    async def _handle_message(...)
```

### Telegram Channel Reference
- Uses `python-telegram-bot` library with long polling
- Markdown to HTML conversion for formatting
- Manages chat IDs for replies
- Handles media/file attachments
- Subscribes to bus for outbound messages

### Signal Channel Approach

The Signal implementation will:
1. Use `signalbot.SignalBot` instead of direct polling
2. Register a universal command handler to forward all messages to bus
3. Convert markdown to Signal's supported formatting
4. Handle Signal-specific features (reactions, typing indicators)
5. Subscribe to bus for outbound messages from agents

## Implementation Plan

### Phase 1: Configuration & Setup

**Files to Modify:**
- `nanobot/config/schema.py`

**Changes:**
1. Add `SignalConfig` class:
```python
class SignalConfig(BaseModel):
    """Signal channel configuration."""
    enabled: bool = False
    phone_number: str = ""  # Bot phone number (e.g., +1234567890)
    signal_service: str = ""  # signal-cli-rest-api address (e.g., 127.0.0.1:8080)
    allow_from: list[str] = Field(default_factory=list)  # Allowed phone numbers
```

2. Update `ChannelsConfig`:
```python
class ChannelsConfig(BaseModel):
    """Configuration for chat channels."""
    whatsapp: WhatsAppConfig = Field(default_factory=WhatsAppConfig)
    telegram: TelegramConfig = Field(default_factory=TelegramConfig)
    signal: SignalConfig = Field(default_factory=SignalConfig)  # NEW
```

**Estimated Lines**: ~15 lines

---

### Phase 2: Signal Channel Implementation

**Files to Create:**
- `nanobot/channels/signal.py`

**Implementation Structure:**

```python
"""Signal channel implementation using signalbot library."""

import asyncio
from typing import Any
from loguru import logger
from signalbot import SignalBot, Command, Context

from nanobot.bus.events import OutboundMessage
from nanobot.bus.queue import MessageBus
from nanobot.channels.base import BaseChannel
from nanobot.config.schema import SignalConfig


class UniversalHandler(Command):
    """Catch-all handler for Signal messages."""
    
    def __init__(self, channel: 'SignalChannel'):
        super().__init__()
        self.channel = channel
    
    async def handle(self, c: Context) -> None:
        """Forward all messages to nanobot bus."""
        # Extract sender, chat, content
        # Check permissions via self.channel.is_allowed()
        # Call self.channel._handle_message()


class SignalChannel(BaseChannel):
    """Signal messenger channel using signalbot library."""
    
    name = "signal"
    
    def __init__(self, config: SignalConfig, bus: MessageBus):
        super().__init__(config, bus)
        self.config: SignalConfig = config
        self._bot: SignalBot | None = None
        self._bot_task: asyncio.Task | None = None
    
    async def start(self) -> None:
        """Start Signal bot and message handling."""
        # 1. Validate config
        # 2. Create SignalBot instance
        # 3. Register UniversalHandler
        # 4. Start bot in background task
        # 5. Subscribe to bus for outbound messages
    
    async def stop(self) -> None:
        """Stop Signal bot and cleanup."""
        # 1. Unsubscribe from bus
        # 2. Stop bot gracefully
        # 3. Cancel background tasks
    
    async def send(self, msg: OutboundMessage) -> None:
        """Send message via Signal."""
        # 1. Get recipient from msg.chat_id
        # 2. Convert markdown to Signal format
        # 3. Send via bot.send()
        # 4. Handle media if present
    
    async def _on_outbound(self, msg: OutboundMessage) -> None:
        """Handle outbound messages from bus."""
        if msg.channel == self.name:
            await self.send(msg)


def _markdown_to_signal(text: str) -> str:
    """Convert markdown to Signal's supported formatting."""
    # Signal supports: **bold**, *italic*, ~strikethrough~, `code`
    # Similar to Telegram converter but simpler
    pass
```

**Key Implementation Details:**

1. **Message Flow (Inbound)**:
   ```
   Signal Message → signalbot Context 
   → UniversalHandler.handle() 
   → is_allowed() check 
   → _handle_message() 
   → MessageBus.publish_inbound()
   ```

2. **Message Flow (Outbound)**:
   ```
   Agent → MessageBus.publish_outbound() 
   → _on_outbound() subscription 
   → send() 
   → SignalBot API
   ```

3. **Threading Model**:
   - signalbot runs its own event loop with producer/consumer workers
   - Need to integrate with nanobot's asyncio loop
   - Use `asyncio.create_task()` to run bot in background

**Estimated Lines**: ~250-300 lines (similar to telegram.py)

---

### Phase 3: Channel Manager Integration

**Files to Modify:**
- `nanobot/channels/__init__.py`
- `nanobot/channels/manager.py`

**Changes:**

1. Update `__init__.py`:
```python
from nanobot.channels.signal import SignalChannel  # NEW
__all__ = ["BaseChannel", "TelegramChannel", "WhatsAppChannel", "SignalChannel"]
```

2. Update `manager.py` to register Signal channel:
```python
async def start(self):
    # ... existing code ...
    
    # Start Signal if enabled
    if self.config.channels.signal.enabled:
        from nanobot.channels.signal import SignalChannel
        signal = SignalChannel(self.config.channels.signal, self.bus)
        self.channels.append(signal)
        await signal.start()
```

**Estimated Lines**: ~10 lines

---

### Phase 4: Dependencies & Installation

**Files to Modify:**
- `pyproject.toml`

**Changes:**
```toml
dependencies = [
    # ... existing dependencies ...
    "python-telegram-bot>=21.0",
    "signalbot>=0.19.1",  # NEW
]
```

**External Service Setup (Documentation)**:

Create `docs/signal-setup.md`:
```markdown
# Signal Setup Guide

## Prerequisites
- Docker or standalone signal-cli installation

## Quick Start with Docker

1. Run signal-cli-rest-api:
   ```bash
   docker run -p 8080:8080 \
     -v signal-data:/home/.local/share/signal-cli \
     bbernhard/signal-cli-rest-api
   ```

2. Link device (one-time):
   ```bash
   curl -X POST http://localhost:8080/v1/qrcodelink?device_name=nanobot
   # Scan QR code with Signal mobile app
   ```

3. Configure nanobot:
   ```json
   {
     "channels": {
       "signal": {
         "enabled": true,
         "phone_number": "+1234567890",
         "signal_service": "127.0.0.1:8080",
         "allow_from": ["+1987654321"]
       }
     }
   }
   ```
```

**Estimated Lines**: ~50 lines documentation

---

### Phase 5: Testing

**Files to Create:**
- `tests/channels/test_signal.py`

**Test Cases:**

1. **Unit Tests**:
   - `test_signal_config_schema()` - Config validation
   - `test_markdown_conversion()` - Format conversion
   - `test_is_allowed()` - Permission checking
   - `test_message_parsing()` - Extract sender/content

2. **Integration Tests** (requires signal-cli-rest-api):
   - `test_signal_channel_start_stop()` - Lifecycle
   - `test_receive_message()` - Mock signalbot Context
   - `test_send_message()` - Mock signalbot send

3. **Mock Strategy**:
```python
from unittest.mock import AsyncMock, MagicMock
from signalbot import Context

# Mock SignalBot
mock_bot = MagicMock()
mock_bot.send = AsyncMock()

# Mock Context for testing handlers
mock_context = MagicMock(spec=Context)
mock_context.message.source = "+1234567890"
mock_context.message.text = "Hello bot"
mock_context.send = AsyncMock()
```

**Estimated Lines**: ~200 lines

---

### Phase 6: Documentation & CLI

**Files to Create:**
- `docs/signal-setup.md` (see Phase 4)
- Update `README.md` with Signal example

**Files to Modify:**
- `nanobot/cli/commands.py` - Add Signal onboarding questions

**Changes to onboarding**:
```python
# After Telegram/WhatsApp setup
if typer.confirm("Enable Signal?", default=False):
    phone = typer.prompt("Bot phone number (e.g., +1234567890)")
    service = typer.prompt("signal-cli-rest-api address", default="127.0.0.1:8080")
    config.channels.signal.enabled = True
    config.channels.signal.phone_number = phone
    config.channels.signal.signal_service = service
```

**Estimated Lines**: ~20 lines

---

## Implementation Timeline

| Phase | Estimated Time | Complexity |
|-------|---------------|------------|
| 1. Config | 30 min | Low |
| 2. Channel Impl | 4-6 hours | High |
| 3. Manager Integration | 30 min | Low |
| 4. Dependencies | 15 min | Low |
| 5. Testing | 2-3 hours | Medium |
| 6. Documentation | 1 hour | Low |
| **Total** | **8-11 hours** | **Medium-High** |

## Technical Challenges & Solutions

### Challenge 1: Event Loop Integration
**Problem**: signalbot runs its own event loop  
**Solution**: Use `asyncio.create_task()` to run bot.start() in background, ensure proper cleanup

### Challenge 2: Message Format Differences
**Problem**: Signal uses different markdown syntax than Telegram  
**Solution**: Create `_markdown_to_signal()` converter (simpler than Telegram's HTML)

### Challenge 3: External Service Dependency
**Problem**: Requires signal-cli-rest-api running  
**Solution**: 
- Provide Docker quickstart in docs
- Graceful error handling if service unavailable
- Health check on startup

### Challenge 4: Phone Number Validation
**Problem**: Signal uses E.164 phone numbers  
**Solution**: Add validation regex in config schema

## Testing Strategy

### Local Development
1. Run signal-cli-rest-api via Docker
2. Link test device (secondary Signal account)
3. Use pytest with AsyncMock for most tests
4. Manual E2E test with real Signal messages

### CI/CD Considerations
- Unit tests can run without signal-cli-rest-api
- Integration tests should be optional (requires service)
- Mock external API calls in tests

## Migration & Compatibility

### Backward Compatibility
- New `signal` config section is optional
- Default `enabled: False` means no breaking changes
- Existing Telegram/WhatsApp channels unaffected

### Config Migration
No migration needed - new installations start fresh.

## Security Considerations

1. **Phone Number Privacy**: Store in config.json (gitignored)
2. **Allowlist**: Enforce `allow_from` to prevent spam
3. **Service Access**: signal-cli-rest-api should be localhost or VPN-only
4. **Message Encryption**: Signal handles E2E encryption, we just relay

## Future Enhancements

- **Multi-device support**: Handle multiple linked devices
- **Group chat support**: Forward group messages
- **Reactions**: Support Signal reactions (emoji)
- **Typing indicators**: Show when bot is "typing"
- **Media handling**: Photos, videos, documents
- **Message editing**: Edit previous bot messages
- **Delivery receipts**: Track message delivery status

## Dependencies Summary

```toml
# pyproject.toml additions
dependencies = [
    "signalbot>=0.19.1",
]
```

**External**:
- Docker (recommended) OR standalone signal-cli
- signal-cli-rest-api (bbernhard/signal-cli-rest-api Docker image)

## File Checklist

- [ ] `nanobot/config/schema.py` - Add SignalConfig
- [ ] `nanobot/channels/signal.py` - New implementation
- [ ] `nanobot/channels/__init__.py` - Export SignalChannel
- [ ] `nanobot/channels/manager.py` - Register Signal
- [ ] `pyproject.toml` - Add signalbot dependency
- [ ] `tests/channels/test_signal.py` - Test suite
- [ ] `docs/signal-setup.md` - Setup guide
- [ ] `docs/signal-implementation-plan.md` - This file
- [ ] `nanobot/cli/commands.py` - Onboarding updates
- [ ] `README.md` - Update with Signal example

## References

- [signalbot PyPI](https://pypi.org/project/signalbot/)
- [signalbot GitHub](https://github.com/filipre/signalbot)
- [signalbot-example](https://github.com/filipre/signalbot-example)
- [Signal-Bot Documentation](https://signal-bot.readthedocs.io/)
- [signal-cli-rest-api](https://github.com/bbernhard/signal-cli-rest-api)

## Success Criteria

- [ ] Signal channel can receive messages
- [ ] Signal channel can send messages  
- [ ] Markdown formatting works correctly
- [ ] Allowlist filtering works
- [ ] Graceful error handling when service unavailable
- [ ] Unit tests pass (>80% coverage)
- [ ] Integration test with real Signal works
- [ ] Documentation complete
- [ ] No breaking changes to existing channels

---

**Status**: Ready for implementation  
**Created**: 2026-02-04  
**Branch**: `signal-integration`  
**Base**: `coding-plan-support` (dd19413)
