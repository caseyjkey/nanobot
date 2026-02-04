# Signal Setup Guide

Complete guide to setting up Signal messenger integration with nanobot.

## Prerequisites

- Docker (recommended) OR standalone signal-cli installation
- Signal mobile app on your phone
- Nanobot installed (`pip install -e .`)

## Quick Start

### 1. Run signal-cli-rest-api

**Option A: Docker (Recommended)**

```bash
docker run -d \
  --name signal-cli \
  -p 8080:8080 \
  -v signal-data:/home/.local/share/signal-cli \
  bbernhard/signal-cli-rest-api
```

**Option B: Native Installation**

See [signal-cli-rest-api documentation](https://github.com/bbernhard/signal-cli-rest-api)

### 2. Link Your Device

Generate a QR code to link Signal:

```bash
curl -X POST http://localhost:8080/v1/qrcodelink?device_name=nanobot
```

This will display a QR code in your terminal. Scan it with Signal mobile app:
1. Open Signal on your phone
2. Go to **Settings → Linked Devices**
3. Tap **+ (Link new device)**
4. Scan the QR code

Wait for "Successfully linked" message.

### 3. Verify Phone Number

Confirm your phone number was registered:

```bash
curl http://localhost:8080/v1/about | jq
```

You should see your phone number in the response.

### 4. Configure Nanobot

Create or edit `~/.nanobot/config.json`:

```json
{
  "channels": {
    "signal": {
      "enabled": true,
      "phone_number": "+14206942069",
      "signal_service": "127.0.0.1:8080",
      "allow_from": ["+13072310423"]
    }
  },
  "agents": {
    "defaults": {
      "model": "zai/glm-4.7",
      "workspace": "~/.nanobot/workspace"
    }
  },
  "providers": {
    "zhipu": {
      "api_key": "your-zai-api-key-here",
      "coding_plan": true
    }
  }
}
```

**Configuration Fields:**

| Field | Description | Example |
|-------|-------------|---------|
| `enabled` | Enable Signal channel | `true` |
| `phone_number` | Bot's phone number (linked device) | `"+14206942069"` |
| `signal_service` | signal-cli-rest-api address | `"127.0.0.1:8080"` |
| `allow_from` | Whitelist of allowed senders | `["+13072310423"]` |

**Security Note:** Leave `allow_from` empty to allow messages from anyone, or specify phone numbers to restrict access.

### 5. Install Dependencies

```bash
cd /path/to/nanobot
pip install -e .
```

This installs nanobot with `signalbot>=0.19.1` dependency.

### 6. Start Nanobot

```bash
nanobot gateway
```

You should see:
```
✓ Signal channel started (bot: +14206942069)
```

### 7. Test It!

Send a message from your phone (+13072310423) to the bot (+14206942069):

```
Hello nanobot!
```

The bot should respond using your configured Z.AI model.

## Configuration Examples

### Using OpenRouter (instead of Z.AI)

```json
{
  "channels": {
    "signal": {
      "enabled": true,
      "phone_number": "+14206942069",
      "signal_service": "127.0.0.1:8080",
      "allow_from": ["+13072310423"]
    }
  },
  "agents": {
    "defaults": {
      "model": "openrouter/anthropic/claude-3.5-sonnet"
    }
  },
  "providers": {
    "openrouter": {
      "api_key": "sk-or-..."
    }
  }
}
```

### Multiple Allowed Users

```json
{
  "channels": {
    "signal": {
      "enabled": true,
      "phone_number": "+14206942069",
      "signal_service": "127.0.0.1:8080",
      "allow_from": [
        "+13072310423",
        "+19999999999",
        "+15551234567"
      ]
    }
  }
}
```

### Remote signal-cli-rest-api

If running signal-cli-rest-api on a different machine:

```json
{
  "channels": {
    "signal": {
      "signal_service": "192.168.1.100:8080"
    }
  }
}
```

## Troubleshooting

### Bot doesn't respond

1. **Check logs:**
   ```bash
   nanobot gateway  # Look for errors in output
   ```

2. **Verify signal-cli is running:**
   ```bash
   curl http://localhost:8080/v1/about
   ```

3. **Check phone number format:**
   - Must include country code: `+1` for US
   - Format: `+14206942069` (no spaces or dashes)

4. **Verify allowlist:**
   - If `allow_from` is set, your number must be in the list
   - Use exact format (including `+`)

### "signalbot not installed" error

```bash
pip install signalbot>=0.19.1
# or reinstall nanobot:
pip install -e .
```

### "Signal service address not configured"

Ensure `signal_service` is set in config.json:
```json
{
  "channels": {
    "signal": {
      "signal_service": "127.0.0.1:8080"
    }
  }
}
```

### signal-cli-rest-api connection refused

1. Check Docker container is running:
   ```bash
   docker ps | grep signal-cli
   ```

2. Check port mapping:
   ```bash
   docker port signal-cli
   # Should show: 8080/tcp -> 0.0.0.0:8080
   ```

3. Test connection:
   ```bash
   curl http://localhost:8080/v1/about
   ```

### Messages not reaching bot

1. **Check sender is authorized:**
   - Either remove `allow_from` (allow all)
   - Or add sender's number to `allow_from`

2. **Verify device is linked:**
   - Check Signal mobile app → Settings → Linked Devices
   - Should show "nanobot" as linked

3. **Check signal-cli logs:**
   ```bash
   docker logs signal-cli
   ```

## Advanced Configuration

### Using with Telegram

Run multiple channels simultaneously:

```json
{
  "channels": {
    "signal": {
      "enabled": true,
      "phone_number": "+14206942069",
      "signal_service": "127.0.0.1:8080",
      "allow_from": ["+13072310423"]
    },
    "telegram": {
      "enabled": true,
      "token": "your-telegram-bot-token"
    }
  }
}
```

### Environment Variables

Override config with environment variables:

```bash
export NANOBOT_CHANNELS__SIGNAL__ENABLED=true
export NANOBOT_CHANNELS__SIGNAL__PHONE_NUMBER="+14206942069"
export NANOBOT_CHANNELS__SIGNAL__SIGNAL_SERVICE="127.0.0.1:8080"

nanobot gateway
```

### Docker Compose Setup

Create `docker-compose.yml`:

```yaml
version: '3.8'
services:
  signal-cli:
    image: bbernhard/signal-cli-rest-api
    ports:
      - "8080:8080"
    volumes:
      - signal-data:/home/.local/share/signal-cli
    restart: unless-stopped

volumes:
  signal-data:
```

Start with: `docker compose up -d`

## Security Best Practices

1. **Use allowlist:** Always set `allow_from` to restrict access
2. **Keep signal-cli private:** Don't expose port 8080 to the internet
3. **Use VPN/firewall:** If running on a server, use firewall rules
4. **Rotate API keys:** Change LLM provider API keys periodically
5. **Monitor usage:** Check logs for unauthorized access attempts

## Uninstalling

1. **Stop nanobot:**
   ```bash
   # Ctrl+C if running in foreground
   ```

2. **Stop signal-cli:**
   ```bash
   docker stop signal-cli
   docker rm signal-cli
   ```

3. **Remove data (optional):**
   ```bash
   docker volume rm signal-data
   ```

4. **Unlink device:**
   - Open Signal mobile app
   - Go to Settings → Linked Devices
   - Remove "nanobot"

## Resources

- [signal-cli-rest-api GitHub](https://github.com/bbernhard/signal-cli-rest-api)
- [signalbot library](https://github.com/filipre/signalbot)
- [Signal API documentation](https://signal.org/docs/)
- [Nanobot documentation](https://github.com/HKUDS/nanobot)

## Support

If you encounter issues:
1. Check [troubleshooting section](#troubleshooting) above
2. Review [signal-cli-rest-api issues](https://github.com/bbernhard/signal-cli-rest-api/issues)
3. Open an issue on [nanobot GitHub](https://github.com/HKUDS/nanobot/issues)
