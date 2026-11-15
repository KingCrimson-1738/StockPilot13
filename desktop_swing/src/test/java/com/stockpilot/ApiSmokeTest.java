package com.stockpilot;

import java.util.Arrays;

/**
 * Plain-Java test of ApiClient against a RUNNING backend (no test framework needed).
 * Needs two users already registered: asha@example.com (owner of the first business) and ravi@example.com.
 * Run:  java -cp out:gson.jar:test-out com.stockpilot.ApiSmokeTest
 */
public class ApiSmokeTest {
    static int failures = 0;

    static void check(boolean ok, String what) {
        System.out.println((ok ? "PASS  " : "FAIL  ") + what);
        if (!ok) failures++;
    }

    static ApiException expectError(ThrowingCall call) {
        try {
            call.run();
        } catch (ApiException e) {
            return e;
        }
        return null;
    }

    interface ThrowingCall { void run() throws ApiException; }

    public static void main(String[] args) throws Exception {
        ApiClient api = new ApiClient(Main.serverUrl());

        ApiException bad = expectError(() -> api.login("asha@example.com", "wrong-password"));
        check(bad != null && bad.status() == 401, "wrong password -> 401: " + (bad == null ? "none" : bad.getMessage()));
        ApiException unreachable = expectError(() -> new ApiClient("http://127.0.0.1:1").login("a@b.com", "x"));
        check(unreachable != null && unreachable.getMessage().startsWith("Cannot reach the server"), "server down -> friendly message");
        ApiException notLoggedIn = expectError(() -> new ApiClient(Main.serverUrl()).businesses());
        check(notLoggedIn != null && notLoggedIn.status() == 401, "no token -> 401");
        ApiException invalid = expectError(() -> api.login("not-an-email", "x"));
        check(invalid != null && invalid.status() == 422 && invalid.getMessage().startsWith("Please check the email"), "422 list-style error is turned into a sentence: " + (invalid == null ? "" : invalid.getMessage()));

        Models.User user = api.login("asha@example.com", "password123");
        check("Asha Kumar".equals(user.fullName()), "login returns the user (snake_case -> camelCase works): " + user.fullName());
        Models.Business[] businesses = api.businesses();
        Models.Business shop = Arrays.stream(businesses).filter(b -> b.name().equals("ABC Electronics")).findFirst().orElseThrow();
        check(shop.isOwner() && shop.defaultMinStock() == 5 && "INR".equals(shop.currency()), "business loaded with role, currency, default alert level");

        Models.Dashboard dash = api.dashboard(shop.id());
        check(dash.totalProducts() == 3 && dash.totalStock() == 53 && Math.abs(dash.inventoryValue() - 8000.0) < 0.001, "dashboard numbers: " + dash.totalProducts() + " products, " + dash.totalStock() + " units, " + dash.inventoryValue());
        check(dash.lowStockCount() == 1 && dash.outOfStockCount() == 1, "low=1, out=1");

        Models.Product[] all = api.products(shop.id(), "", "all");
        check(all.length == 3, "3 products listed");
        Models.Product[] searched = api.products(shop.id(), "cab", "all");
        check(searched.length == 1 && searched[0].sku().equals("CBL-1"), "server-side search 'cab' finds only the cable");
        check(api.products(shop.id(), "", "low").length == 1 && api.products(shop.id(), "", "out").length == 1, "stock filters low / out");
        check(api.products(shop.id(), "a b&c=d", "all").length == 0, "special characters in the search are URL-encoded safely");

        Models.Product cable = searched[0];
        Models.StockResult added = api.stockIn(shop.id(), cable.id(), 5, "Delivery");
        check(added.quantityAfter() == cable.quantity() + 5 && added.quantityChange() == 5 && added.type().equals("in"), "stock in: " + cable.quantity() + " -> " + added.quantityAfter());
        Models.StockResult removed = api.stockOut(shop.id(), cable.id(), 2, "");
        check(removed.quantityAfter() == added.quantityAfter() - 2, "stock out with a blank reason works");
        ApiException tooMany = expectError(() -> api.stockOut(shop.id(), cable.id(), 9999, null));
        check(tooMany != null && tooMany.status() == 409 && tooMany.getMessage().startsWith("Not enough stock"), "taking too much -> 409: " + (tooMany == null ? "" : tooMany.getMessage()));

        Models.Transaction[] history = api.transactions(shop.id(), "", 200);
        check(history.length == 4 && history[0].type().equals("out") && history[0].quantityChange() == -2, "history newest first: " + history[0].productName() + " " + history[0].quantityChange());
        check(Arrays.stream(api.transactions(shop.id(), "in", 200)).allMatch(t -> t.type().equals("in")), "history type filter");
        check(Format.when(history[0].createdAt()).matches("\\d\\d \\w{3} \\d\\d:\\d\\d"), "timestamp formats: " + Format.when(history[0].createdAt()));

        // isolation: a user who is not in a business must not see it
        ApiClient other = new ApiClient(Main.serverUrl());
        other.login("ravi@example.com", "password123");
        check(other.dashboard(shop.id()).totalProducts() == 3, "staff member can read the business they belong to");
        Models.Business furniture = Arrays.stream(businesses).filter(b -> b.name().equals("ABC Furniture")).findFirst().orElseThrow();
        ApiException hidden = expectError(() -> other.dashboard(furniture.id()));
        check(hidden != null && hidden.status() == 404, "a user who is NOT a member gets 404 for that business");

        System.out.println(failures == 0 ? "ALL PASSED" : failures + " FAILED");
        System.exit(failures == 0 ? 0 : 1);
    }
}
