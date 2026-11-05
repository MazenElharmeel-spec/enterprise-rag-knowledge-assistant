from typing import Protocol


class VirusScanner(Protocol):
    async def scan(self, content: bytes, filename: str) -> None: ...


class DemoNoopScanner:
    """Interface placeholder for local demo; production must inject a real scanner."""

    async def scan(self, content: bytes, filename: str) -> None:
        return None


def get_scanner() -> VirusScanner:
    return DemoNoopScanner()
