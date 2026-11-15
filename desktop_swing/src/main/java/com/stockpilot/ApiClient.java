package com.stockpilot;

import com.google.gson.FieldNamingPolicy;
import com.google.gson.Gson;
import com.google.gson.GsonBuilder;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import com.stockpilot.Models.*;

import java.io.IOException;
import java.net.ConnectException;
import java.net.URI;
import java.net.URLEncoder;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.net.http.HttpTimeoutException;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.LinkedHashMap;
import java.util.Map;

/**
 * Every call to the backend goes through this class (same idea as api_client.py in the Tkinter app).
 * It uses Java's built-in HttpClient, sends the JWT in the Authorization header and turns failures into ApiException.
 */
public class ApiClient {
    private final HttpClient http = HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(10)).build();
    // snake_case JSON  <->  camelCase Java
    private final Gson gson = new GsonBuilder().setFieldNamingPolicy(FieldNamingPolicy.LOWER_CASE_WITH_UNDERSCORES).create();
    private final String baseUrl;
    private String token;   // set after login, sent with every later request

    public ApiClient(String baseUrl) {
        this.baseUrl = baseUrl.endsWith("/") ? baseUrl.substring(0, baseUrl.length() - 1) : baseUrl;
    }

    // ---------- the one method that talks HTTP ----------
    private String send(String method, String path, Map<String, String> query, Object body) throws ApiException {
        StringBuilder url = new StringBuilder(baseUrl).append(path);
        if (query != null) {
            char separator = '?';
            for (Map.Entry<String, String> e : query.entrySet()) {
                if (e.getValue() == null || e.getValue().isBlank()) continue;   // empty filters are not sent
                url.append(separator).append(e.getKey()).append('=').append(URLEncoder.encode(e.getValue(), StandardCharsets.UTF_8));
                separator = '&';
            }
        }
        HttpRequest.Builder request = HttpRequest.newBuilder(URI.create(url.toString())).timeout(Duration.ofSeconds(30));
        if (token != null) request.header("Authorization", "Bearer " + token);
        if (body != null) {
            request.header("Content-Type", "application/json");
            request.method(method, HttpRequest.BodyPublishers.ofString(gson.toJson(body)));
        } else {
            request.method(method, HttpRequest.BodyPublishers.noBody());
        }
        try {
            HttpResponse<String> response = http.send(request.build(), HttpResponse.BodyHandlers.ofString());
            int status = response.statusCode();
            if (status >= 200 && status < 300) return response.body();
            throw new ApiException(errorMessage(status, response.body()), status);
        } catch (HttpTimeoutException e) {
            throw new ApiException("The server took too long to respond. Please try again.", 0);
        } catch (ConnectException e) {
            throw new ApiException("Cannot reach the server. Check your internet connection and the server address.", 0);
        } catch (IOException e) {
            throw new ApiException("Could not complete the request. Please try again.", 0);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new ApiException("The request was cancelled.", 0);
        } catch (IllegalArgumentException e) {
            throw new ApiException("The server address is not valid: " + baseUrl, 0);
        }
    }

    /** Reads the backend's {"detail": ...} error body into a friendly sentence. */
    static String errorMessage(int status, String body) {
        if (status >= 500) return "Something went wrong on the server. Please try again in a moment.";
        try {
            JsonElement detail = JsonParser.parseString(body).getAsJsonObject().get("detail");
            if (detail != null && detail.isJsonPrimitive()) return detail.getAsString();
            if (detail != null && detail.isJsonArray() && !detail.getAsJsonArray().isEmpty()) {   // 422 validation errors
                JsonObject first = detail.getAsJsonArray().get(0).getAsJsonObject();
                var loc = first.getAsJsonArray("loc");
                String field = loc.get(loc.size() - 1).getAsString().replace('_', ' ');
                return "Please check the " + field + ": " + first.get("msg").getAsString();
            }
        } catch (RuntimeException ignored) {
            // the body was not the JSON we expected; fall through to the generic message
        }
        return "The request failed (error " + status + ").";
    }

    private <T> T get(String path, Map<String, String> query, Class<T> type) throws ApiException {
        return gson.fromJson(send("GET", path, query, null), type);
    }

    private <T> T post(String path, Object body, Class<T> type) throws ApiException {
        return gson.fromJson(send("POST", path, null, body), type);
    }

    private <T> T put(String path, Object body, Class<T> type) throws ApiException {
        return gson.fromJson(send("PUT", path, null, body), type);
    }

    private static Map<String, String> params(String... pairs) {
        Map<String, String> map = new LinkedHashMap<>();
        for (int i = 0; i < pairs.length; i += 2) map.put(pairs[i], pairs[i + 1]);
        return map;
    }

    // ---------- the calls the screens use ----------
    public User login(String email, String password) throws ApiException {
        LoginResult result = post("/auth/login", Map.of("email", email, "password", password), LoginResult.class);
        token = result.accessToken();
        return result.user();
    }

    public Business[] businesses() throws ApiException {
        return get("/businesses", null, Business[].class);
    }

    public Dashboard dashboard(int businessId) throws ApiException {
        return get("/businesses/" + businessId + "/dashboard", null, Dashboard.class);
    }

    /** stock = all | ok | low | out ; the SERVER does the searching and filtering. */
    public Product[] products(int businessId, String search, String stock) throws ApiException {
        return get("/businesses/" + businessId + "/products", params("search", search, "stock", stock), Product[].class);
    }

    public StockResult stockIn(int businessId, int productId, int quantity, String reason) throws ApiException {
        return move(businessId, "in", productId, quantity, reason);
    }

    public StockResult stockOut(int businessId, int productId, int quantity, String reason) throws ApiException {
        return move(businessId, "out", productId, quantity, reason);
    }

    private StockResult move(int businessId, String kind, int productId, int quantity, String reason) throws ApiException {
        Map<String, Object> body = new LinkedHashMap<>();
        body.put("product_id", productId);
        body.put("quantity", quantity);
        if (reason != null && !reason.isBlank()) body.put("reason", reason.trim());
        return post("/businesses/" + businessId + "/stock/" + kind, body, StockResult.class);
    }

    public Transaction[] transactions(int businessId, String type, int limit) throws ApiException {
        return get("/businesses/" + businessId + "/transactions", params("type", type, "limit", String.valueOf(limit)), Transaction[].class);
    }

    public Models.Category[] categories(int businessId) throws ApiException {
        return get("/businesses/" + businessId + "/categories", null, Models.Category[].class);
    }

    public Models.Supplier[] suppliers(int businessId) throws ApiException {
        return get("/businesses/" + businessId + "/suppliers", null, Models.Supplier[].class);
    }

    /** Add a product (opening quantity becomes an 'Opening stock' movement on the server). */
    public Product createProduct(int businessId, Map<String, Object> values) throws ApiException {
        return post("/businesses/" + businessId + "/products", values, Product.class);
    }

    /** Edit a product's details. Quantity is not part of this: it only changes through stock movements. */
    public Product updateProduct(int businessId, int productId, Map<String, Object> values) throws ApiException {
        return put("/businesses/" + businessId + "/products/" + productId, values, Product.class);
    }

    public Models.RestockItem[] lowStockReport(int businessId) throws ApiException {
        return get("/businesses/" + businessId + "/reports/low-stock", null, Models.RestockItem[].class);
    }

    public Models.CategoryValue[] categoryValueReport(int businessId) throws ApiException {
        return get("/businesses/" + businessId + "/reports/inventory-by-category", null, Models.CategoryValue[].class);
    }
}
