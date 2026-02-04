"""Chat channels module with plugin architecture."""

from nanobot.channels.base import BaseChannel
from nanobot.channels.manager import ChannelManager
from nanobot.channels.signal import SignalChannel

__all__ = ["BaseChannel", "ChannelManager", "SignalChannel"]
