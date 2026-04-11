import json
import logging
from datetime import datetime
from pathlib import Path


LOGGER = logging.getLogger(__name__)


class MemoryManager:
    def __init__(self, memory_file=None):
        self.memory_file = Path(memory_file) if memory_file else Path(__file__).resolve().parents[1] / "memory.json"
        self.memory_file.parent.mkdir(parents=True, exist_ok=True)
        self._memory = self._load_memory()
        self._save_memory()

    def record_action(self, action, resource):
        action = str(action or "").strip()
        resource = str(resource or "").strip()

        if not action:
            LOGGER.debug("Skipped persistent memory update because action was empty.")
            return

        now = datetime.now().isoformat(timespec="microseconds")
        record = self._find_record(action, resource)

        if record:
            record["count"] += 1
            record["last_used"] = now
            LOGGER.info("Updated persistent memory for action=%s resource=%s count=%s", action, resource, record["count"])
        else:
            record = {
                "action": action,
                "resource": resource,
                "count": 1,
                "last_used": now,
            }
            self._memory.append(record)
            LOGGER.info("Recorded new persistent memory for action=%s resource=%s", action, resource)

        self._save_memory()

    def get_top_actions(self):
        return sorted(
            self._memory,
            key=lambda item: (-item.get("count", 0), item.get("action", ""), item.get("resource", "")),
        )

    def get_last_actions(self, n=5):
        limit = max(int(n or 0), 0)
        return sorted(
            self._memory,
            key=lambda item: item.get("last_used", ""),
            reverse=True,
        )[:limit]

    def _load_memory(self):
        if not self.memory_file.exists():
            LOGGER.info("Persistent memory file not found. Starting fresh: %s", self.memory_file)
            return []

        try:
            data = json.loads(self.memory_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            LOGGER.exception("Failed to load persistent memory from %s", self.memory_file)
            return []

        if not isinstance(data, list):
            LOGGER.warning("Persistent memory file had invalid format. Resetting in-memory state.")
            return []

        valid_records = []

        for item in data:
            if not self._is_valid_record(item):
                continue
            valid_records.append(item)

        return valid_records

    def _save_memory(self):
        try:
            self.memory_file.write_text(
                json.dumps(self._memory, indent=2),
                encoding="utf-8",
            )
        except OSError:
            LOGGER.exception("Failed to save persistent memory to %s", self.memory_file)

    def _find_record(self, action, resource):
        for item in self._memory:
            if item.get("action") == action and item.get("resource") == resource:
                return item

        return None

    @staticmethod
    def _is_valid_record(item):
        return (
            isinstance(item, dict)
            and isinstance(item.get("action"), str)
            and isinstance(item.get("resource"), str)
            and isinstance(item.get("count"), int)
            and isinstance(item.get("last_used"), str)
        )
