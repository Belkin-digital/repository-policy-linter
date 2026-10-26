from dataclasses import asdict, dataclass


class PolicyError(Exception):
    """Invalid configuration, unsafe path, or failed execution (exit 2)."""


@dataclass(frozen=True, order=True)
class Diagnostic:
    file: str
    line: int
    column: int
    rule: str
    severity: str
    message: str
    fixable: bool = False

    def json(self):
        return asdict(self)
