package com.fb.sfe;

import com.google.gson.Gson;
import com.google.gson.JsonObject;
import com.google.gson.reflect.TypeToken;
import okhttp3.*;
import java.io.IOException;
import java.lang.reflect.Type;
import java.util.*;
import java.util.concurrent.TimeUnit;

/**
 * Java SDK for Skill Fragment Engine.
 * 
 * <p>Example usage:</p>
 * <pre>{@code
 * SFEClient client = new SFEClient("http://localhost:8000", "api-key");
 * 
 * ExecuteResponse result = client.execute("code_generation", 
 *     "Write a function to reverse a string in Python");
 * 
 * System.out.println(result.getDecision());
 * }</pre>
 */
public class SFEClient {
    private final String baseUrl;
    private final String apiKey;
    private final OkHttpClient httpClient;
    private final Gson gson;

    private static final MediaType JSON = MediaType.get("application/json; charset=utf-8");

    public SFEClient() {
        this("http://localhost:8000", null);
    }

    public SFEClient(String baseUrl, String apiKey) {
        this.baseUrl = baseUrl.endsWith("/") ? baseUrl.substring(0, baseUrl.length() - 1) : baseUrl;
        this.apiKey = apiKey;
        this.httpClient = new OkHttpClient.Builder()
                .connectTimeout(30, TimeUnit.SECONDS)
                .readTimeout(30, TimeUnit.SECONDS)
                .writeTimeout(30, TimeUnit.SECONDS)
                .build();
        this.gson = new Gson();
    }

    private Headers getHeaders() {
        Headers.Builder builder = new Headers.Builder()
                .add("Content-Type", "application/json");
        if (apiKey != null && !apiKey.isEmpty()) {
            builder.add("Authorization", "Bearer " + apiKey);
        }
        return builder.build();
    }

    private Request.Builder createRequestBuilder(String path) {
        return new Request.Builder()
                .url(baseUrl + path)
                .headers(getHeaders());
    }

    /**
     * Execute a task through SFE.
     */
    public ExecuteResponse execute(String taskType, String prompt) {
        return execute(taskType, prompt, new HashMap<>(), new HashMap<>());
    }

    public ExecuteResponse execute(String taskType, String prompt, Map<String, Object> context) {
        return execute(taskType, prompt, context, new HashMap<>());
    }

    public ExecuteResponse execute(String taskType, String prompt, Map<String, Object> context, Map<String, Object> options) {
        JsonObject body = new JsonObject();
        body.addProperty("task_type", taskType);
        body.addProperty("prompt", prompt);
        body.add("context", gson.toJsonTree(context));
        body.add("options", gson.toJsonTree(options));

        RequestBody requestBody = RequestBody.create(JSON, gson.toJson(body));
        Request request = createRequestBuilder("/api/v1/execute")
                .post(requestBody)
                .build();

        try (Response response = httpClient.newCall(request).execute()) {
            if (!response.isSuccessful()) {
                throw new IOException("Unexpected response: " + response);
            }
            JsonObject json = gson.fromJson(response.body().string(), JsonObject.class);
            return new ExecuteResponse(json);
        } catch (IOException e) {
            throw new RuntimeException("Execute failed: " + e.getMessage(), e);
        }
    }

    /**
     * Search fragments by similarity.
     */
    public List<FragmentSearchResult> searchFragments(String query) {
        return searchFragments(query, 10, 0.5f);
    }

    public List<FragmentSearchResult> searchFragments(String query, int topK, float minScore) {
        String url = String.format("/api/v1/fragment/search?query=%s&top_k=%d&min_score=%f",
                query.replace(" ", "%20"), topK, minScore);
        
        Request request = createRequestBuilder(url).get().build();

        try (Response response = httpClient.newCall(request).execute()) {
            if (!response.isSuccessful()) {
                throw new IOException("Unexpected response: " + response);
            }
            Type listType = new TypeToken<List<FragmentSearchResult>>(){}.getType();
            return gson.fromJson(response.body().string(), listType);
        } catch (IOException e) {
            throw new RuntimeException("Search failed: " + e.getMessage(), e);
        }
    }

    /**
     * Get fragment by ID.
     */
    public JsonObject getFragment(String fragmentId) {
        Request request = createRequestBuilder("/api/v1/fragment/" + fragmentId).get().build();

        try (Response response = httpClient.newCall(request).execute()) {
            if (!response.isSuccessful()) {
                throw new IOException("Unexpected response: " + response);
            }
            return gson.fromJson(response.body().string(), JsonObject.class);
        } catch (IOException e) {
            throw new RuntimeException("Get fragment failed: " + e.getMessage(), e);
        }
    }

    /**
     * Submit feedback on a fragment.
     */
    public JsonObject submitFeedback(String feedbackType, float score) {
        return submitFeedback(feedbackType, score, null, null);
    }

    public JsonObject submitFeedback(String feedbackType, float score, String fragmentId, String comment) {
        JsonObject body = new JsonObject();
        body.addProperty("feedback_type", feedbackType);
        body.addProperty("score", score);
        if (fragmentId != null) body.addProperty("fragment_id", fragmentId);
        if (comment != null) body.addProperty("comment", comment);

        RequestBody requestBody = RequestBody.create(JSON, gson.toJson(body));
        Request request = createRequestBuilder("/api/v1/feedback")
                .post(requestBody)
                .build();

        try (Response response = httpClient.newCall(request).execute()) {
            if (!response.isSuccessful()) {
                throw new IOException("Unexpected response: " + response);
            }
            return gson.fromJson(response.body().string(), JsonObject.class);
        } catch (IOException e) {
            throw new RuntimeException("Submit feedback failed: " + e.getMessage(), e);
        }
    }

    /**
     * Get system metrics.
     */
    public JsonObject getMetrics() {
        Request request = createRequestBuilder("/api/v1/metrics").get().build();

        try (Response response = httpClient.newCall(request).execute()) {
            if (!response.isSuccessful()) {
                throw new IOException("Unexpected response: " + response);
            }
            return gson.fromJson(response.body().string(), JsonObject.class);
        } catch (IOException e) {
            throw new RuntimeException("Get metrics failed: " + e.getMessage(), e);
        }
    }

    /**
     * Get health status.
     */
    public JsonObject getHealth() {
        Request request = createRequestBuilder("/api/v1/health").get().build();

        try (Response response = httpClient.newCall(request).execute()) {
            if (!response.isSuccessful()) {
                throw new IOException("Unexpected response: " + response);
            }
            return gson.fromJson(response.body().string(), JsonObject.class);
        } catch (IOException e) {
            throw new RuntimeException("Get health failed: " + e.getMessage(), e);
        }
    }

    /**
     * List loaded plugins.
     */
    public List<PluginInfo> listPlugins() {
        Request request = createRequestBuilder("/api/v1/plugins").get().build();

        try (Response response = httpClient.newCall(request).execute()) {
            if (!response.isSuccessful()) {
                throw new IOException("Unexpected response: " + response);
            }
            Type listType = new TypeToken<List<PluginInfo>>(){}.getType();
            return gson.fromJson(response.body().string(), listType);
        } catch (IOException e) {
            throw new RuntimeException("List plugins failed: " + e.getMessage(), e);
        }
    }

    /**
     * Load a plugin.
     */
    public JsonObject loadPlugin(String name) {
        return loadPlugin(name, new HashMap<>());
    }

    public JsonObject loadPlugin(String name, Map<String, Object> config) {
        RequestBody requestBody = RequestBody.create(JSON, gson.toJson(config));
        Request request = createRequestBuilder("/api/v1/plugins/" + name + "/load")
                .post(requestBody)
                .build();

        try (Response response = httpClient.newCall(request).execute()) {
            if (!response.isSuccessful()) {
                throw new IOException("Unexpected response: " + response);
            }
            return gson.fromJson(response.body().string(), JsonObject.class);
        } catch (IOException e) {
            throw new RuntimeException("Load plugin failed: " + e.getMessage(), e);
        }
    }

    /**
     * Run clustering on fragments.
     */
    public JsonObject runClustering() {
        return runClustering("auto", null);
    }

    public JsonObject runClustering(String method, String taskType) {
        String url = "/api/v1/clustering/run?method=" + method;
        if (taskType != null) url += "&task_type=" + taskType;
        
        Request request = createRequestBuilder(url).post(RequestBody.create(JSON, "{}")).build();

        try (Response response = httpClient.newCall(request).execute()) {
            if (!response.isSuccessful()) {
                throw new IOException("Unexpected response: " + response);
            }
            return gson.fromJson(response.body().string(), JsonObject.class);
        } catch (IOException e) {
            throw new RuntimeException("Run clustering failed: " + e.getMessage(), e);
        }
    }

    /**
     * Get API specification.
     */
    public JsonObject getApiSpec() {
        Request request = createRequestBuilder("/api/v1/api-spec").get().build();

        try (Response response = httpClient.newCall(request).execute()) {
            if (!response.isSuccessful()) {
                throw new IOException("Unexpected response: " + response);
            }
            return gson.fromJson(response.body().string(), JsonObject.class);
        } catch (IOException e) {
            throw new RuntimeException("Get API spec failed: " + e.getMessage(), e);
        }
    }

    /**
     * Close the client.
     */
    public void close() {
        httpClient.dispatcher().executorService().shutdown();
        httpClient.connectionPool().evictAll();
    }
}

// Response classes
class ExecuteResponse {
    private final String decision;
    private final String result;
    private final JsonObject metadata;

    ExecuteResponse(JsonObject json) {
        this.decision = json.get("decision").getAsString();
        this.result = json.get("result").getAsString();
        this.metadata = json.getAsJsonObject("metadata");
    }

    public String getDecision() { return decision; }
    public String getResult() { return result; }
    public JsonObject getMetadata() { return metadata; }
}

class FragmentSearchResult {
    private final String fragment_id;
    private final float score;
    private final String task_type;

    public String getFragmentId() { return fragment_id; }
    public float getScore() { return score; }
    public String getTaskType() { return task_type; }
}

class PluginInfo {
    private final String name;
    private final String state;
    private final String type;
    private final String version;

    public String getName() { return name; }
    public String getState() { return state; }
    public String getType() { return type; }
    public String getVersion() { return version; }
}
