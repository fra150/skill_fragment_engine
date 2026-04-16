from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from enum import Enum
import importlib
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class PluginType(Enum):
    ADAPTER = "adapter"
    STORAGE = "storage"
    EMBEDDING = "embedding"
    VALIDATION = "validation"
    EXECUTION = "execution"
    RETRIEVAL = "retrieval"
    ANALYTICS = "analytics"


class PluginState(Enum):
    UNLOADED = "unloaded"
    LOADED = "loaded"
    INITIALIZED = "initialized"
    ACTIVE = "active"
    FAILED = "failed"


class BasePlugin(ABC):
    def __init__(self, name: str, version: str, plugin_type: PluginType):
        self.name = name
        self.version = version
        self.plugin_type = plugin_type
        self.state = PluginState.UNLOADED
        self.config: Dict[str, Any] = {}
        self.dependencies: List[str] = []
        self._hooks: Dict[str, List[callable]] = {}

    @abstractmethod
    def initialize(self, config: Dict[str, Any]) -> bool:
        pass

    @abstractmethod
    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        pass

    @abstractmethod
    def cleanup(self) -> None:
        pass

    def register_hook(self, event: str, callback: callable) -> None:
        if event not in self._hooks:
            self._hooks[event] = []
        self._hooks[event].append(callback)

    def trigger_hook(self, event: str, *args, **kwargs) -> List[Any]:
        results = []
        if event in self._hooks:
            for callback in self._hooks[event]:
                try:
                    results.append(callback(*args, **kwargs))
                except Exception as e:
                    logger.error(f"Hook {event} failed in {self.name}: {e}")
        return results


class PluginManager:
    def __init__(self, plugin_dir: Optional[Path] = None):
        self.plugins: Dict[str, BasePlugin] = {}
        self.plugin_dir = plugin_dir or Path("./plugins")
        self._hooks: Dict[str, List[BasePlugin]] = {}

    def discover_plugins(self) -> List[str]:
        discovered = []
        if not self.plugin_dir.exists():
            return discovered
        
        for file in self.plugin_dir.glob("*.py"):
            if file.stem.startswith("_"):
                continue
            discovered.append(file.stem)
        return discovered

    def load_plugin(self, name: str, config: Optional[Dict[str, Any]] = None) -> bool:
        try:
            module = importlib.import_module(f"plugins.{name}")
            plugin_class = getattr(module, "Plugin", None)
            if not plugin_class:
                logger.error(f"No Plugin class found in {name}")
                return False
            
            plugin = plugin_class()
            self.plugins[name] = plugin
            
            if config:
                plugin.config = config
            
            plugin.state = PluginState.LOADED
            logger.info(f"Plugin {name} loaded successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to load plugin {name}: {e}")
            return False

    def initialize_plugin(self, name: str) -> bool:
        if name not in self.plugins:
            return False
        
        plugin = self.plugins[name]
        try:
            success = plugin.initialize(plugin.config)
            if success:
                plugin.state = PluginState.INITIALIZED
            return success
        except Exception as e:
            logger.error(f"Failed to initialize plugin {name}: {e}")
            plugin.state = PluginState.FAILED
            return False

    def activate_plugin(self, name: str) -> bool:
        if name not in self.plugins:
            return False
        
        plugin = self.plugins[name]
        if plugin.state != PluginState.INITIALIZED:
            if not self.initialize_plugin(name):
                return False
        
        plugin.state = PluginState.ACTIVE
        self._register_plugin_hooks(plugin)
        logger.info(f"Plugin {name} activated")
        return True

    def _register_plugin_hooks(self, plugin: BasePlugin) -> None:
        for event in plugin._hooks.keys():
            if event not in self._hooks:
                self._hooks[event] = []
            self._hooks[event].append(plugin)

    def deactivate_plugin(self, name: str) -> bool:
        if name not in self.plugins:
            return False
        
        plugin = self.plugins[name]
        plugin.cleanup()
        plugin.state = PluginState.LOADED
        
        if name in self._hooks:
            del self._hooks[name]
        
        logger.info(f"Plugin {name} deactivated")
        return True

    def unload_plugin(self, name: str) -> bool:
        if name not in self.plugins:
            return False
        
        if self.plugins[name].state == PluginState.ACTIVE:
            self.deactivate_plugin(name)
        
        del self.plugins[name]
        logger.info(f"Plugin {name} unloaded")
        return True

    def get_plugin(self, name: str) -> Optional[BasePlugin]:
        return self.plugins.get(name)

    def list_plugins(self, state: Optional[PluginState] = None) -> List[str]:
        if state:
            return [n for n, p in self.plugins.items() if p.state == state]
        return list(self.plugins.keys())

    def trigger_event(self, event: str, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        results = []
        if event in self._hooks:
            for plugin in self._hooks[event]:
                try:
                    result = plugin.execute(context)
                    results.append({"plugin": plugin.name, "result": result})
                except Exception as e:
                    logger.error(f"Plugin {plugin.name} failed: {e}")
        return results


_global_plugin_manager: Optional[PluginManager] = None


def get_plugin_manager() -> PluginManager:
    global _global_plugin_manager
    if _global_plugin_manager is None:
        _global_plugin_manager = PluginManager()
    return _global_plugin_manager
