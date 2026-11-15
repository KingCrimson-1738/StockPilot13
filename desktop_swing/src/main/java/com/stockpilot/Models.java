package com.stockpilot;

/**
 * The shapes of the JSON the backend sends. Gson fills these records automatically:
 * a JSON field "default_min_stock" goes into the component defaultMinStock
 * (see the naming policy in ApiClient). Fields the screen does not need are simply left out.
 */
public final class Models {
    private Models() {}

    public record User(int id, String email, String fullName) {}

    public record LoginResult(String accessToken, User user) {}

    public record Business(int id, String name, String currency, int defaultMinStock, String myRole) {
        public boolean isOwner() { return "owner".equals(myRole); }

        @Override public String toString() { return name; }   // what a combo box shows
    }

    public record Product(int id, String name, String sku, Integer categoryId, String categoryName, Integer supplierId, String supplierName,
                          double purchasePrice, double sellingPrice, int quantity, int alertLevel, String stockStatus) {}

    public record Transaction(int id, String productName, String type, int quantityChange, int quantityAfter,
                              String reason, String userName, String createdAt) {}

    public record Dashboard(String currency, int totalProducts, int totalStock, double inventoryValue,
                            int lowStockCount, int outOfStockCount, Transaction[] recentTransactions) {}

    public record StockResult(int quantityAfter, int quantityChange, String type) {}

    public record Category(int id, String name, int productCount) {
        @Override public String toString() { return name; }   // what a combo box shows
    }

    public record Supplier(int id, String name, String contactPerson, String email, String phone, String address, int productCount) {
        @Override public String toString() { return name; }
    }

    public record RestockItem(int productId, String name, String sku, String supplierName, int quantity, int alertLevel,
                              int suggestedOrder, double estimatedCost) {}

    public record CategoryValue(String category, int productCount, int units, double value) {}
}
