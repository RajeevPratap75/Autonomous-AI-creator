from dataclasses import dataclass


@dataclass
class DiscoveredTopic:
    title: str
    url: str
    summary: str
    source: str
    discovered_at: str
    signal_strength: float = 0.5
