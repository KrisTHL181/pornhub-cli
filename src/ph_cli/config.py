import functools
import json
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any


class ConfigManager:
    """Manages the configuration for the application, including loading and saving settings."""
    _instance: "ConfigManager | None" = None
    _lock: threading.Lock = threading.Lock()

    def __new__(cls, *args: Any, **kwargs: Any) -> "ConfigManager":
        if not cls._instance:
            with cls._lock:
                if not cls._instance:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self.cache_dir = Path.home() / ".pornhub-cli" / "cache"

        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.header_file = self.cache_dir / "headers.json"
        self.content_dir = self.cache_dir / "content"
        self.content_dir.mkdir(exist_ok=True)

        self.profiles_dir = self.cache_dir / "profiles"
        self.profiles_dir.mkdir(exist_ok=True)
        self.active_profile_file = self.cache_dir / "active_profile"
        self.config_file = self.cache_dir / "config.json"

        self._file_lock = threading.RLock()
        self._initialized = True

    @staticmethod
    def make_thread_safe(fn: Callable | None = None, *, lock_attr: str = "_file_lock") -> Callable:
        def decorator(func: Callable) -> Callable:
            @functools.wraps(func)
            def wrapper(self: ConfigManager, *args: Any, **kwargs: Any) -> Any:
                lock = getattr(self, lock_attr)
                with lock:
                    return func(self, *args, **kwargs)

            return wrapper

        if fn is None:
            return decorator
        return decorator(fn)

    def _atomic_write(self, path: Path, data: str | bytes, mode: str = "w") -> None:
        tmp_path = path.with_suffix(".tmp")
        if mode == "w":
            tmp_path.write_text(data, encoding="utf-8")
        else:
            tmp_path.write_bytes(data)
        tmp_path.replace(path)

    def load_config(self) -> dict:
        """Load the configuration from the file."""
        try:
            with open(self.config_file) as f:
                return json.load(f)
        except FileNotFoundError:
            return {}

config_manager = ConfigManager()
