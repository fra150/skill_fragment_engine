from skill_fragment_engine.services.plugin_system import BasePlugin, PluginType, get_plugin_manager


class LangChainAdapter(BasePlugin):
    def __init__(self):
        super().__init__(
            name="langchain_adapter",
            version="1.0.0",
            plugin_type=PluginType.ADAPTER
        )
        self.dependencies = ["langchain"]

    def initialize(self, config):
        self.config.update(config)
        try:
            from langchain_openai import ChatOpenAI
            from langchain.schema import HumanMessage
            
            self.llm = ChatOpenAI(
                model=config.get("model", "gpt-4"),
                temperature=config.get("temperature", 0.7),
                api_key=config.get("api_key")
            )
            return True
        except ImportError:
            return False
        except Exception as e:
            self.config["error"] = str(e)
            return False

    def execute(self, context):
        prompt = context.get("prompt", "")
        try:
            from langchain.schema import HumanMessage
            response = self.llm.invoke([HumanMessage(content=prompt)])
            return {"success": True, "response": response.content}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def cleanup(self):
        self.llm = None


def get_langchain_fragment_loader():
    return LangChainAdapter()


Plugin = LangChainAdapter
