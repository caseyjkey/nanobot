from nanobot.bus.queue import MessageBus


def test_signal_channel_accepts_legacy_connection_keys():
    from nanobot.channels.signal import SignalChannel, SignalConfig

    cfg = SignalConfig.model_validate({
        "enabled": True,
        "phoneNumber": "+16282170054",
        "signalService": "127.0.0.1:8080",
    })
    channel = SignalChannel(cfg, MessageBus())

    assert channel.config.account == "+16282170054"
    assert channel.config.daemon_host == "127.0.0.1"
    assert channel.config.daemon_port == 8080
    assert channel._is_allowed("+15551234567", "+15551234567", is_group=False) is True
    assert channel._is_allowed("+15551234567", "group-1", is_group=True) is False


def test_signal_channel_legacy_allow_from_preserves_dm_allowlist():
    from nanobot.channels.signal import SignalChannel, SignalConfig

    cfg = SignalConfig.model_validate({
        "enabled": True,
        "phoneNumber": "+16282170054",
        "signalService": "127.0.0.1:8080",
        "allowFrom": ["+15551234567"],
    })
    channel = SignalChannel(cfg, MessageBus())

    assert channel._is_allowed("+15551234567", "+15551234567", is_group=False) is True
    assert channel._is_allowed("+16667778888", "+16667778888", is_group=False) is False
