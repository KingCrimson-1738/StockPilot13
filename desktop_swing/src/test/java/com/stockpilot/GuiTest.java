package com.stockpilot;

import javax.swing.*;
import java.awt.*;
import java.util.function.BooleanSupplier;
import java.util.function.Supplier;

/** Drives the REAL windows (finds components by name, types, clicks). Run it under a virtual display (xvfb). */
public class GuiTest {
    static int failures = 0;

    static void check(boolean ok, String what) {
        System.out.println((ok ? "PASS  " : "FAIL  ") + what);
        if (!ok) { failures++; System.exit(1); }
    }

    // ----- helpers -----
    static Component find(Container root, String name) {
        for (Component c : root.getComponents()) {
            if (name.equals(c.getName())) return c;
            if (c instanceof Container inner) {
                Component found = find(inner, name);
                if (found != null) return found;
            }
        }
        return null;
    }

    static <T extends Component> T get(Window window, String name, Class<T> type) {
        Component c = find(window, name);
        if (c == null) throw new IllegalStateException("no component named " + name);
        return type.cast(c);
    }

    static <T> T edt(Supplier<T> work) throws Exception {
        if (SwingUtilities.isEventDispatchThread()) return work.get();   // already on the Swing thread (nested helper call)
        Object[] box = new Object[1];
        SwingUtilities.invokeAndWait(() -> box[0] = work.get());
        @SuppressWarnings("unchecked") T result = (T) box[0];
        return result;
    }

    static void waitFor(BooleanSupplier condition, String what) throws Exception {
        long end = System.currentTimeMillis() + 15000;
        while (System.currentTimeMillis() < end) {
            try {
                if (edt(condition::getAsBoolean)) return;
            } catch (RuntimeException ignored) { }
            Thread.sleep(50);
        }
        throw new AssertionError("timed out waiting for: " + what);
    }

    static <T extends Window> T window(Class<T> type) throws Exception {
        waitFor(() -> java.util.Arrays.stream(Window.getWindows()).anyMatch(w -> type.isInstance(w) && w.isShowing()), type.getSimpleName() + " visible");
        return type.cast(edt(() -> java.util.Arrays.stream(Window.getWindows()).filter(w -> type.isInstance(w) && w.isShowing()).findFirst().get()));
    }

    static void click(Window w, String name) throws Exception {
        SwingUtilities.invokeLater(() -> ((AbstractButton) find(w, name)).doClick());   // not invokeAndWait: a click may open a modal dialog
    }

    static void type(Window w, String name, String text) throws Exception {
        edt(() -> { ((javax.swing.text.JTextComponent) find(w, name)).setText(text); return null; });
    }

    static String banner(Window w, String name) throws Exception {
        return edt(() -> ((Banner) find(w, name)).isVisible() ? ((Banner) find(w, name)).text() : "");
    }

    static int rows(Window w, String table) throws Exception {
        return edt(() -> ((JTable) find(w, table)).getRowCount());
    }

    static String cell(Window w, String table, int row, int col) throws Exception {
        return edt(() -> String.valueOf(((JTable) find(w, table)).getValueAt(row, col)));
    }

    static void shot(String name) throws Exception {
        Thread.sleep(700);
        new ProcessBuilder("import", "-window", "root", "/tmp/shots/" + name + ".png").inheritIO().start().waitFor();
    }

    static LoginFrame login(String email, String password) throws Exception {
        LoginFrame frame = window(LoginFrame.class);
        type(frame, "email", email);
        type(frame, "password", password);
        click(frame, "login");
        return frame;
    }

    public static void main(String[] args) {
        try {
            run();
        } catch (Throwable problem) {
            problem.printStackTrace();
            System.exit(1);   // never leave the windows hanging
        }
    }

    static void run() throws Exception {
        SwingUtilities.invokeAndWait(() -> {
            try { UIManager.setLookAndFeel(UIManager.getCrossPlatformLookAndFeelClassName()); } catch (Exception ignored) { }
            Theme.install();
            new LoginFrame(new ApiClient(Main.serverUrl()), Main.serverUrl()).setVisible(true);
        });

        // ---------- login ----------
        LoginFrame loginFrame = window(LoginFrame.class);
        shot("40_swing_login");
        click(loginFrame, "login");
        waitFor(() -> !((Banner) find(loginFrame, "banner")).text().isEmpty() && ((Banner) find(loginFrame, "banner")).isVisible(), "empty-form message");
        check(banner(loginFrame, "banner").contains("enter your email and password"), "empty form -> message");
        login("asha@example.com", "wrong");
        waitFor(() -> ((Banner) find(loginFrame, "banner")).text().contains("Incorrect"), "wrong password message");
        check(true, "wrong password -> server message shown: " + banner(loginFrame, "banner"));
        check(edt(() -> ((AbstractButton) find(loginFrame, "login")).isEnabled()), "login button is usable again after a failure");
        login("asha@example.com", "password123");
        MainFrame main = window(MainFrame.class);
        check(!loginFrame.isShowing(), "after login the login window closes and the main window opens");

        // ---------- dashboard ----------
        waitFor(() -> !((JLabel) find(main, "stat0")).getText().equals("…"), "dashboard loaded");
        check(((JLabel) find(main, "stat0")).getText().equals("3"), "stat: 3 products");
        check(((JLabel) find(main, "stat1")).getText().equals("53"), "stat: 53 units");
        check(((JLabel) find(main, "stat2")).getText().equals("INR 8,000.00"), "stat: value INR 8,000.00");
        check(((JLabel) find(main, "stat3")).getText().equals("2 (1 low, 1 out)"), "stat: needs attention '2 (1 low, 1 out)'");
        check(rows(main, "recentTable") == 2, "recent movements table has the 2 opening-stock rows");
        check(edt(() -> ((JComboBox<?>) find(main, "businessMenu")).getItemCount()) == 2, "business switcher lists both businesses");
        shot("41_swing_dashboard");

        // ---------- products ----------
        click(main, "navProducts");
        waitFor(() -> { try { return rows(main, "productTable") == 3; } catch (Exception e) { return false; } }, "3 products");
        check(true, "products listed (3)");
        type(main, "search", "cab");
        waitFor(() -> { try { return rows(main, "productTable") == 1; } catch (Exception e) { return false; } }, "search narrows to 1");
        check(cell(main, "productTable", 0, 0).equals("CBL-1"), "typing 'cab' asks the server and shows only the cable (debounced)");
        type(main, "search", "");
        waitFor(() -> { try { return rows(main, "productTable") == 3; } catch (Exception e) { return false; } }, "cleared");
        edt(() -> { ((JComboBox<?>) find(main, "stockFilter")).setSelectedItem("Low stock"); return null; });
        waitFor(() -> { try { return rows(main, "productTable") == 1; } catch (Exception e) { return false; } }, "low filter");
        check(cell(main, "productTable", 0, 1).equals("Phone X"), "stock filter 'Low stock' shows Phone X");
        edt(() -> { ((JComboBox<?>) find(main, "stockFilter")).setSelectedItem("All stock levels"); return null; });
        waitFor(() -> { try { return rows(main, "productTable") == 3; } catch (Exception e) { return false; } }, "all again");
        shot("42_swing_products");

        click(main, "stockOut");
        waitFor(() -> { try { return banner(main, "productsBanner").contains("Select a product"); } catch (Exception e) { return false; } }, "no-selection message");
        check(true, "Stock out with nothing selected -> message");

        // ---------- stock out dialog ----------
        int phoneRow = -1;
        for (int i = 0; i < 3; i++) if (cell(main, "productTable", i, 1).equals("Phone X")) phoneRow = i;
        int row = phoneRow;
        edt(() -> { ((JTable) find(main, "productTable")).setRowSelectionInterval(row, row); return null; });
        click(main, "stockOut");
        StockDialog dialog = window(StockDialog.class);
        type(dialog, "quantity", "9");
        waitFor(() -> ((JLabel) findPreview(dialog)).getText().contains("Not enough stock"), "preview warns");
        check(true, "dialog preview warns when removing more than available");
        click(dialog, "save");
        waitFor(() -> { try { return banner(dialog, "dialogBanner").contains("Not enough stock"); } catch (Exception e) { return false; } }, "validation message");
        check(true, "removing 9 of 3 is refused on screen: " + banner(dialog, "dialogBanner"));
        type(dialog, "quantity", "abc");
        click(dialog, "save");
        waitFor(() -> { try { return banner(dialog, "dialogBanner").contains("whole number"); } catch (Exception e) { return false; } }, "letters");
        check(true, "letters rejected");
        type(dialog, "quantity", "99999999999999");
        click(dialog, "save");
        waitFor(() -> { try { return banner(dialog, "dialogBanner").contains("between 1 and 1,000,000"); } catch (Exception e) { return false; } }, "huge number");
        check(true, "a number too big for an int is rejected without crashing");
        type(dialog, "quantity", "3");
        type(dialog, "reason", "Sale");
        shot("43_swing_stock_dialog");
        click(dialog, "save");
        waitFor(() -> !dialog.isShowing(), "dialog closes");
        waitFor(() -> { try { return banner(main, "productsBanner").contains("OUT of stock"); } catch (Exception e) { return false; } }, "out-of-stock warning");
        check(true, "stock out recorded; warning shown: " + banner(main, "productsBanner"));
        waitFor(() -> { try { return cell(main, "productTable", row, 4).equals("0") && cell(main, "productTable", row, 5).equals("Out"); } catch (Exception e) { return false; } }, "table updated");
        check(true, "table now shows Phone X: stock 0, status Out");
        shot("44_swing_out_warning");

        // stock in
        click(main, "stockIn");
        StockDialog dialog2 = window(StockDialog.class);
        type(dialog2, "quantity", "10");
        click(dialog2, "save");
        waitFor(() -> !dialog2.isShowing(), "dialog 2 closes");
        waitFor(() -> { try { return cell(main, "productTable", row, 4).equals("10"); } catch (Exception e) { return false; } }, "stock in applied");
        check(true, "stock in of 10 recorded (stock 10)");

        // ---------- history ----------
        click(main, "navHistory");
        waitFor(() -> { try { return rows(main, "historyTable") >= 4; } catch (Exception e) { return false; } }, "history rows");
        check(cell(main, "historyTable", 0, 2).equals("Stock in") && cell(main, "historyTable", 0, 3).equals("+10"), "history newest first: " + cell(main, "historyTable", 0, 2) + " " + cell(main, "historyTable", 0, 3));
        check(cell(main, "historyTable", 0, 5).equals("Asha Kumar"), "history shows who did it");
        edt(() -> { ((JComboBox<?>) find(main, "typeFilter")).setSelectedItem("Stock out"); return null; });
        waitFor(() -> { try { return rows(main, "historyTable") == 1; } catch (Exception e) { return false; } }, "filtered");
        check(cell(main, "historyTable", 0, 6).equals("Sale") && cell(main, "historyTable", 0, 3).equals("-3"), "type filter 'Stock out' -> only the sale (-3, reason Sale)");
        shot("45_swing_history");

        // ---------- switch business ----------
        click(main, "navProducts");
        edt(() -> { ((JComboBox<?>) find(main, "businessMenu")).setSelectedIndex(1); return null; });
        waitFor(() -> { try { return rows(main, "productTable") == 0; } catch (Exception e) { return false; } }, "other business is empty");
        check(true, "switching to ABC Furniture shows its own (empty) product list, not the electronics");
        edt(() -> { ((JComboBox<?>) find(main, "businessMenu")).setSelectedIndex(0); return null; });
        waitFor(() -> { try { return rows(main, "productTable") == 3; } catch (Exception e) { return false; } }, "back");
        check(true, "switching back shows the electronics again");


        // ---------- add / edit product (owner) ----------
        click(main, "addProduct");
        ProductDialog add = window(ProductDialog.class);
        click(add, "save");
        waitFor(() -> { try { return banner(add, "dialogBanner").contains("required"); } catch (Exception e) { return false; } }, "required message");
        check(true, "adding a product without name and SKU is refused on screen");
        type(add, "productName", "Adapter");
        type(add, "productSku", "AD-1");
        type(add, "purchasePrice", "abc");
        click(add, "save");
        waitFor(() -> { try { return banner(add, "dialogBanner").contains("purchase price"); } catch (Exception e) { return false; } }, "price message");
        check(true, "a price that is not a number is refused on screen");
        edt(() -> { JComboBox<?> box = (JComboBox<?>) find(add, "productCategory"); for (int i = 0; i < box.getItemCount(); i++) if (box.getItemAt(i).toString().equals("Cables")) box.setSelectedIndex(i); return null; });
        edt(() -> { JComboBox<?> box = (JComboBox<?>) find(add, "productSupplier"); for (int i = 0; i < box.getItemCount(); i++) if (box.getItemAt(i).toString().equals("Volt Traders")) box.setSelectedIndex(i); return null; });
        type(add, "purchasePrice", "20");
        type(add, "sellingPrice", "35");
        type(add, "openingQuantity", "7");
        shot("47_swing_add_product");
        click(add, "save");
        waitFor(() -> !add.isShowing(), "add dialog closes");
        waitFor(() -> { try { return rows(main, "productTable") == 4; } catch (Exception e) { return false; } }, "4 products");
        int adapterRow = -1;
        for (int i = 0; i < 4; i++) if (cell(main, "productTable", i, 1).equals("Adapter")) adapterRow = i;
        int ar = adapterRow;
        check(ar >= 0 && cell(main, "productTable", ar, 2).equals("Cables") && cell(main, "productTable", ar, 4).equals("7"),
                "new product appears with its category and opening stock 7");
        edt(() -> { ((JTable) find(main, "productTable")).setRowSelectionInterval(ar, ar); return null; });
        click(main, "editProduct");
        ProductDialog editDialog = window(ProductDialog.class);
        check(edt(() -> ((JTextField) find(editDialog, "productName")).getText()).equals("Adapter"), "edit dialog is pre-filled");
        type(editDialog, "sellingPrice", "40");
        click(editDialog, "save");
        waitFor(() -> !editDialog.isShowing(), "edit dialog closes");
        waitFor(() -> { try { return cell(main, "productTable", ar, 3).equals("40.00"); } catch (Exception e) { return false; } }, "price updated");
        check(cell(main, "productTable", ar, 4).equals("7"), "edit changed the price (40.00) and left the stock (7) alone");

        // ---------- suppliers and reports ----------
        click(main, "navSuppliers");
        waitFor(() -> { try { return rows(main, "supplierTable") == 1; } catch (Exception e) { return false; } }, "supplier row");
        check(cell(main, "supplierTable", 0, 0).equals("Volt Traders") && cell(main, "supplierTable", 0, 4).equals("1"),
                "suppliers page lists Volt Traders with 1 product (the Adapter)");
        shot("48_swing_suppliers");
        click(main, "navReports");
        waitFor(() -> { try { return rows(main, "restockTable") >= 1 && rows(main, "categoryTable") >= 2; } catch (Exception e) { return false; } }, "reports load");
        boolean chargerListed = false;
        for (int i = 0; i < rows(main, "restockTable"); i++) if (cell(main, "restockTable", i, 0).equals("Charger")) chargerListed = true;
        check(chargerListed, "restock report lists Charger (0 in stock, below its alert level)");
        boolean cablesListed = false;
        for (int i = 0; i < rows(main, "categoryTable"); i++) if (cell(main, "categoryTable", i, 0).equals("Cables")) cablesListed = true;
        check(cablesListed, "category report lists Cables");
        shot("49_swing_reports");
        click(main, "navProducts");

        // ---------- log out, then log in as staff ----------
        click(main, "logout");
        LoginFrame again = window(LoginFrame.class);
        check(!main.isShowing(), "log out closes the main window and shows login");
        login("ravi@example.com", "password123");
        MainFrame staff = window(MainFrame.class);
        waitFor(() -> !((JLabel) find(staff, "stat0")).getText().equals("…"), "staff dashboard");
        check(edt(() -> ((JComboBox<?>) find(staff, "businessMenu")).getItemCount()) == 1, "staff sees only the one business they belong to");
        check(edt(() -> java.util.Arrays.stream(((Container) staff.getContentPane()).getComponents()).count()) > 0 && containsText(staff, "STAFF"), "role badge says STAFF");
        click(staff, "navProducts");
        waitFor(() -> { try { return rows(staff, "productTable") == 4; } catch (Exception e) { return false; } }, "staff products");
        check(!edt(() -> find(staff, "addProduct").isVisible()) && !edt(() -> find(staff, "editProduct").isVisible()), "staff does not see Add / Edit product");
        edt(() -> { ((JTable) find(staff, "productTable")).setRowSelectionInterval(0, 0); return null; });
        click(staff, "stockIn");
        StockDialog staffDialog = window(StockDialog.class);
        type(staffDialog, "quantity", "1");
        click(staffDialog, "save");
        waitFor(() -> !staffDialog.isShowing(), "staff dialog closes");
        waitFor(() -> { try { return banner(staff, "productsBanner").contains("added"); } catch (Exception e) { return false; } }, "staff stock in");
        check(true, "staff can record stock in");
        shot("46_swing_staff");
        System.out.println("ALL PASSED");
        System.exit(0);
    }

    static Component findPreview(Container root) {
        for (Component c : root.getComponents()) {
            if (c instanceof JLabel l && (l.getText().startsWith("Not enough") || l.getText().startsWith("Stock after") || l.getText().isBlank())
                    && l.getFont().isBold() && l.getFont().getSize() == 13) return c;
            if (c instanceof Container inner) {
                Component f = findPreview(inner);
                if (f != null) return f;
            }
        }
        return null;
    }

    static boolean containsText(Container root, String text) throws Exception {
        return edt(() -> containsTextNow(root, text));
    }

    static boolean containsTextNow(Container root, String text) {
        for (Component c : root.getComponents()) {
            if (c instanceof JLabel l && l.getText() != null && l.getText().contains(text)) return true;
            if (c instanceof Container inner && containsTextNow(inner, text)) return true;
        }
        return false;
    }
}
