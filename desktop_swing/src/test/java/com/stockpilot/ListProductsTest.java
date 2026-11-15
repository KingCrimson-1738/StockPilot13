package com.stockpilot;

/** Prints the first business's products as Swing's own ApiClient sees them: sku|name|category|quantity. Used by tools/check_consistency.py. */
public class ListProductsTest {
    public static void main(String[] args) throws Exception {
        ApiClient api = new ApiClient(System.getenv().getOrDefault("STOCKPILOT_API_URL", "http://127.0.0.1:8000"));
        api.login(args[0], args[1]);
        Models.Business business = api.businesses()[0];
        System.out.println("BUSINESS " + business.name());
        for (Models.Product p : api.products(business.id(), "", "all")) {
            System.out.println(p.sku() + "|" + p.name() + "|" + (p.categoryName() == null ? "-" : p.categoryName()) + "|" + p.quantity());
        }
    }
}
