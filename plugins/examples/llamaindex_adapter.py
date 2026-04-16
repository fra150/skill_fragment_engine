from skill_fragment_engine.services.plugin_system import BasePlugin, PluginType, get_plugin_manager


class LlamaIndexAdapter(BasePlugin):
    def __init__(self):
        super().__init__(
            name="llamaindex_adapter",
            version="1.0.0",
            plugin_type=PluginType.ADAPTER
        )
        self.dependencies = ["llama-index"]

    def initialize(self, config):
        self.config.update(config)
        try:
            from llama_index.core import VectorStoreIndex, SimpleDirectoryReader
            from llama_index.llms.openai import OpenAI
            
            self.llm = OpenAI(
                model=config.get("model", "gpt-4"),
                api_key=config.get("api_key")
            )
            self.index = None
            return True
        except ImportError:
            return False
        except Exception as e:
            self.config["error"] = str(e)
            return False

    def execute(self, context):
        query = context.get("query", "")
        try:
            if self.index:
                response = self.index.as_query_engine(llm=self.llm).query(query)
                return {"success": True, "response": str(response)}
            return {"success": False, "error": "Index not initialized"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def cleanup(self):
        self.index = None
        self.llm = None


Plugin = LlamaIndexAdapter
