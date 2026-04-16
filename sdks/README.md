# Skill Fragment Engine - SDKs

Official SDKs for integrating with the Skill Fragment Engine (SFE).

## Available SDKs

| Language | Location | Install |
|----------|----------|---------|
| Python | `sdks/python/` | `pip install skill-fragment-engine` |
| JavaScript/TypeScript | `sdks/javascript/` | `npm install skill-fragment-engine` |
| Java/Kotlin | `sdks/java/` | Maven dependency |

## Quick Start

### Python

```bash
cd sdks/python
pip install -e .
```

```python
from skill_fragment_engine import SFEClient

client = SFEClient(base_url="http://localhost:8000")
result = client.execute(
    task_type="code_generation",
    prompt="Write a function to reverse a string in Python",
    context={"language": "python"}
)
print(result["decision"])  # REUSE, ADAPT, or RECOMPUTE
```

### JavaScript/TypeScript

```bash
cd sdks/javascript
npm install
npm run build
```

```typescript
import { SFEClient } from 'skill-fragment-engine';

const client = new SFEClient({ 
  baseURL: 'http://localhost:8000' 
});

const result = await client.execute({
  task_type: 'code_generation',
  prompt: 'Write a function to reverse a string'
});
```

### Java

```xml
<dependency>
    <groupId>com.fb</groupId>
    <artifactId>skill-fragment-engine</artifactId>
    <version>1.0.0</version>
</dependency>
```

```java
import com.fb.sfe.SFEClient;

SFEClient client = new SFEClient("http://localhost:8000");
ExecuteResponse result = client.execute("code_generation", "Write a function...");
```

## All Methods

### Execute
```python
client.execute(task_type, prompt, context, options)
```

### Search
```python
client.search_fragments(query, top_k, min_score)
```

### Feedback
```python
client.submit_feedback(feedback_type, score, fragment_id, comment)
```

### Metrics
```python
client.get_metrics()
```

### Plugins
```python
client.list_plugins()
client.load_plugin("langchain_adapter")
```

### Clustering
```python
client.run_clustering(method, task_type)
client.get_cluster_info(task_type)
```

### Versioning
```python
client.get_version_history(fragment_id)
client.rollback_to_version(fragment_id, version)
```

### Sharding
```python
client.get_sharding_stats()
client.rebalance_shards(num_shards)
```

## API Key

Set the `SFE_API_KEY` environment variable or pass it to the client:

```python
client = SFEClient(api_key="your-api-key")
```

## License

MIT
