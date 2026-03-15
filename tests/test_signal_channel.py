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


def test_signal_channel_legacy_minimal_config_exposes_non_empty_allow_from():
    from nanobot.channels.signal import SignalConfig

    cfg = SignalConfig.model_validate({
        "enabled": True,
        "phoneNumber": "+16282170054",
        "signalService": "127.0.0.1:8080",
    })

    assert cfg.allow_from == ["*"]
    assert cfg.dm.policy == "open"



def test_signal_channel_receive_websocket_url_uses_v1_receive():
    from nanobot.channels.signal import SignalChannel, SignalConfig

    cfg = SignalConfig.model_validate({
        "enabled": True,
        "account": "+16282170054",
        "daemonHost": "127.0.0.1",
        "daemonPort": 8080,
        "allowFrom": ["*"],
        "dm": {"enabled": True, "policy": "open"},
    })
    channel = SignalChannel(cfg, MessageBus())

    assert channel._receive_websocket_url() == "ws://127.0.0.1:8080/v1/receive/+16282170054"


def test_signal_channel_builds_v2_send_payload_for_dm():
    from nanobot.channels.signal import SignalChannel, SignalConfig

    cfg = SignalConfig.model_validate({
        "enabled": True,
        "account": "+16282170054",
        "allowFrom": ["*"],
        "dm": {"enabled": True, "policy": "open"},
    })
    channel = SignalChannel(cfg, MessageBus())

    payload = channel._build_send_payload("+15551234567", "hello")

    assert payload == {
        "number": "+16282170054",
        "message": "hello",
        "recipients": ["+15551234567"],
        "text_mode": "styled",
    }


def test_signal_channel_builds_v2_send_payload_for_group():
    from nanobot.channels.signal import SignalChannel, SignalConfig

    cfg = SignalConfig.model_validate({
        "enabled": True,
        "account": "+16282170054",
        "allowFrom": ["*"],
        "dm": {"enabled": True, "policy": "open"},
    })
    channel = SignalChannel(cfg, MessageBus())

    payload = channel._build_send_payload("group.ABCD123=", "hello")

    assert payload == {
        "number": "+16282170054",
        "message": "hello",
        "recipients": ["group.ABCD123="],
        "text_mode": "styled",
    }
