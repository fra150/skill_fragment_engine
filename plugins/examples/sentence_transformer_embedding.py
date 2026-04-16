from skill_fragment_engine.services.plugin_system import BasePlugin, PluginType, get_plugin_manager


class SentenceTransformerEmbedding(BasePlugin):
    def __init__(self):
        super().__init__(
            name="sentence_transformer_embedding",
            version="1.0.0",
            plugin_type=PluginType.EMBEDDING
        )
        self.dependencies = ["sentence-transformers"]
        self.dimension = 384

    def initialize(self, config):
        self.config.update(config)
        try:
            from sentence_transformers import SentenceTransformer
            
            model_name = config.get("model", "all-MiniLM-L6-v2")
            self.model = SentenceTransformer(model_name)
            self.dimension = self.model.get_sentence_embedding_dimension()
            return True
        except ImportError:
            return False
        except Exception as e:
            self.config["error"] = str(e)
            return False

    def execute(self, context):
        texts = context.get("texts", [])
        try:
            embeddings = self.model.encode(texts)
            return {"success": True, "embeddings": embeddings.tolist()}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def cleanup(self):
        self.model = None


Plugin = SentenceTransformerEmbedding
