"""Robots snapshots with correct group boundaries and wildcard matching."""

import base64
import hashlib
import re
from dataclasses import asdict, dataclass
from datetime import UTC, datetime

from protego import Protego

from app.ingestion.errors import IngestionError

USER_AGENT = "BankSalaryResearch/0.1"


def applicable_groups(text: str) -> tuple[tuple[str, ...], str]:
    groups: list[tuple[list[str], list[str]]] = []
    agents: list[str] = []
    rules: list[str] = []
    for line in text.splitlines():
        clean = line.split("#", 1)[0].strip()
        key, separator, value = clean.partition(":")
        if not separator:
            continue
        if key.strip().lower() == "user-agent":
            if rules:
                groups.append((agents, rules))
                agents, rules = [], []
            if value.strip():
                agents.append(value.strip())
        elif agents and key.strip().lower() in ("allow", "disallow", "crawl-delay", "request-rate"):
            rules.append(clean)
    if agents:
        groups.append((agents, rules))
    specific = {
        agent
        for names, _ in groups
        for agent in names
        if agent != "*" and re.search(r"(?<![a-z0-9_-])" + re.escape(agent), USER_AGENT, re.I)
    }
    longest = max((len(agent) for agent in specific), default=0)
    chosen = {agent for agent in specific if len(agent) == longest} if specific else {"*"}
    matching = [(names, rules) for names, rules in groups if chosen.intersection(names)]
    names = tuple(
        dict.fromkeys(agent for names, _ in matching for agent in names if agent in chosen)
    )
    # Select the applicable group ourselves. This also avoids a one-letter token
    # tying with Protego's '*' score; Protego still performs wildcard/path matching.
    filtered = "\n".join("User-agent: *\n" + "\n".join(rules) for _, rules in matching)
    return names, filtered


@dataclass(frozen=True)
class RobotsSnapshot:
    url: str
    raw_base64: str
    sha256: str
    checked_at: str
    user_agent: str
    matched_groups: tuple[str, ...]
    text: str

    def audit(self) -> dict[str, object]:
        return asdict(self)

    def check(self, target: str) -> None:
        _, filtered = applicable_groups(self.text)
        if not Protego.parse(filtered).can_fetch(target, self.user_agent):
            raise IngestionError("ROBOTS_DISALLOWED")


def parse_robots(url: str, status: int, body: bytes) -> RobotsSnapshot:
    if status == 403:
        raise IngestionError("HTTP_FORBIDDEN")
    if status != 200:
        raise IngestionError("ROBOTS_UNKNOWN")
    if len(body) > 512 * 1024:
        raise IngestionError("ROBOTS_INVALID")
    try:
        text = body.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise IngestionError("ROBOTS_INVALID") from exc
    if re.search(r"<\s*(html|script|!doctype)|user_blocked|captcha", text, re.I):
        raise IngestionError("CHALLENGE")
    agents = re.findall(r"^\s*user-agent\s*:\s*([^\s#]+)", text, re.M | re.I)
    if not agents:
        raise IngestionError("ROBOTS_INVALID")
    groups, _ = applicable_groups(text)
    return RobotsSnapshot(
        url,
        base64.b64encode(body).decode(),
        hashlib.sha256(body).hexdigest(),
        datetime.now(UTC).isoformat(),
        USER_AGENT,
        groups,
        text,
    )
