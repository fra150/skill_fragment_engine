package com.fb.sfe

import kotlinx.coroutines.*
import okhttp3.*
import com.google.gson.Gson
import com.google.gson.JsonObject
import java.lang.reflect.Type
import com.google.gson.reflect.TypeToken

/**
 * Kotlin Async SDK for Skill Fragment Engine.
 */
class AsyncSFEClient(
    private val baseUrl: String = "http://localhost:8000",
    private val apiKey: String? = null
) {
    private val httpClient = OkHttpClient()
    private val gson = Gson()
    private val scope = CoroutineScope(Dispatchers.IO)

    private val JSON = MediaType.get("application/json; charset=utf-8")

    private fun getHeaders(): Headers = Headers.Builder()
        .add("Content-Type", "application/json")
        .apply { apiKey?.let { add("Authorization", "Bearer $it") } }
        .build()

    private fun createRequestBuilder(path: String) = Request.Builder()
        .url("$baseUrl$path")
        .headers(getHeaders())

    suspend fun execute(taskType: String, prompt: String): JsonObject = withContext(Dispatchers.IO) {
        val body = JsonObject().apply {
            addProperty("task_type", taskType)
            addProperty("prompt", prompt)
            addProperty("context", gson.toJsonTree(mapOf<String, Any>()))
            addProperty("options", gson.toJsonTree(mapOf<String, Any>()))
        }

        val requestBody = RequestBody.create(JSON, gson.toJson(body))
        val request = createRequestBuilder("/api/v1/execute")
            .post(requestBody)
            .build()

        httpClient.newCall(request).execute().use { response ->
            if (!response.isSuccessful) throw IOException("Execute failed: ${response.code}")
            gson.fromJson(response.body?.string(), JsonObject::class.java)
        }
    }

    suspend fun searchFragments(query: String, topK: Int = 10, minScore: Float = 0.5f): List<JsonObject> = 
        withContext(Dispatchers.IO) {
            val url = "/api/v1/fragment/search?query=$query&top_k=$topK&min_score=$minScore"
            val request = createRequestBuilder(url).get().build()
            
            httpClient.newCall(request).execute().use { response ->
                if (!response.isSuccessful) throw IOException("Search failed: ${response.code}")
                val type: Type = object : TypeToken<List<JsonObject>>(){}.type
                gson.fromJson(response.body?.string(), type)
            }
        }

    suspend fun getMetrics(): JsonObject = withContext(Dispatchers.IO) {
        val request = createRequestBuilder("/api/v1/metrics").get().build()
        
        httpClient.newCall(request).execute().use { response ->
            if (!response.isSuccessful) throw IOException("Get metrics failed: ${response.code}")
            gson.fromJson(response.body?.string(), JsonObject::class.java)
        }
    }

    suspend fun getHealth(): JsonObject = withContext(Dispatchers.IO) {
        val request = createRequestBuilder("/api/v1/health").get().build()
        
        httpClient.newCall(request).execute().use { response ->
            if (!response.isSuccessful) throw IOException("Get health failed: ${response.code}")
            gson.fromJson(response.body?.string(), JsonObject::class.java)
        }
    }

    fun close() {
        scope.cancel()
        httpClient.dispatcher().executorService().shutdown()
        httpClient.connectionPool().evictAll()
    }
}
