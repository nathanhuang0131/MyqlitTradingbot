from dataclasses import dataclass, field


@dataclass
class EventLog:
    lines: list[str] = field(default_factory=list)

    def add(self, message: str) -> None:
        self.lines.append(message)
        if len(self.lines) > 200:
            self.lines = self.lines[-200:]
