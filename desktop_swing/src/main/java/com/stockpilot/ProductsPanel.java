package com.stockpilot;

import javax.swing.*;
import javax.swing.table.DefaultTableModel;
import java.awt.*;

public class ProductsPanel extends JPanel implements Refreshable {
    private static final String[] STOCK_LABELS = {"All stock levels", "Stock OK", "Low stock", "Out of stock"};
    private static final String[] STOCK_VALUES = {"all", "ok", "low", "out"};

    private final MainFrame frame;
    private final JTextField search = Theme.textField(20, "Search by name or SKU");
    private final JComboBox<String> stockFilter = Theme.combo(STOCK_LABELS);
    private final DefaultTableModel model = new DefaultTableModel(
            new String[]{"SKU", "NAME", "CATEGORY", "PRICE", "STOCK", "STATUS"}, 0);
    private final JTable table = Theme.table(model, 3, 4);
    private final JLabel count = Theme.label(" ", 13, Font.PLAIN, Theme.MUTED);
    private final Banner banner = new Banner();
    private final JButton add;
    private final JButton edit;
    private Models.Product[] products = new Models.Product[0];   // same order as the table rows
    private int requestNumber;
    private final Timer searchTimer;

    public ProductsPanel(MainFrame frame) {
        super(new BorderLayout(0, 12));
        this.frame = frame;
        setOpaque(false);
        search.setName("search");
        stockFilter.setName("stockFilter");
        table.setName("productTable");
        banner.setName("productsBanner");
        table.setSelectionMode(ListSelectionModel.SINGLE_SELECTION);

        JPanel top = new JPanel(new BorderLayout(0, 12));
        top.setOpaque(false);
        top.add(banner, BorderLayout.NORTH);
        JPanel filters = new JPanel(new BorderLayout(10, 0));
        filters.setOpaque(false);
        filters.add(search, BorderLayout.CENTER);
        filters.add(stockFilter, BorderLayout.EAST);
        JPanel actions = new JPanel(new BorderLayout(10, 0));
        actions.setOpaque(false);
        actions.add(count, BorderLayout.CENTER);
        JPanel buttons = new JPanel(new FlowLayout(FlowLayout.RIGHT, 10, 0));
        buttons.setOpaque(false);
        add = Theme.button("Add product", false);
        edit = Theme.button("Edit product", false);
        JButton in = Theme.button("Stock in", true);
        JButton out = Theme.button("Stock out", false);
        JButton reload = Theme.button("Refresh", false);
        add.setName("addProduct");
        edit.setName("editProduct");
        in.setName("stockIn");
        out.setName("stockOut");
        reload.setName("refresh");
        buttons.add(add);
        buttons.add(edit);
        buttons.add(in);
        buttons.add(out);
        buttons.add(reload);
        actions.add(buttons, BorderLayout.EAST);
        JPanel stack = new JPanel(new BorderLayout(0, 12));
        stack.setOpaque(false);
        stack.add(filters, BorderLayout.NORTH);
        stack.add(actions, BorderLayout.SOUTH);
        top.add(stack, BorderLayout.CENTER);
        add(top, BorderLayout.NORTH);
        add(Theme.scroll(table), BorderLayout.CENTER);

        add.addActionListener(e -> openProductDialog(false));
        edit.addActionListener(e -> openProductDialog(true));
        in.addActionListener(e -> openDialog(true));
        out.addActionListener(e -> openDialog(false));
        reload.addActionListener(e -> refresh());
        stockFilter.addActionListener(e -> refresh());
        // wait until the user pauses typing (300 ms) before asking the server
        searchTimer = new Timer(300, e -> refresh());
        searchTimer.setRepeats(false);
        search.getDocument().addDocumentListener(new SimpleDocumentListener(searchTimer::restart));
    }

    @Override public void refresh() {
        Models.Business business = frame.business();
        // only owners can change products; staff keep stock in / out (the server enforces this as well)
        add.setVisible(business.isOwner());
        edit.setVisible(business.isOwner());
        String text = search.getText().trim();
        String stock = STOCK_VALUES[stockFilter.getSelectedIndex()];
        int number = ++requestNumber;
        Async.run(() -> frame.api().products(business.id(), text, stock), result -> {
            if (number != requestNumber || business.id() != frame.business().id()) return;
            show(business, result);
        }, error -> {
            if (number == requestNumber) frame.report(error, banner);
        });
    }

    private void show(Models.Business business, Models.Product[] result) {
        int selectedId = table.getSelectedRow() >= 0 && table.getSelectedRow() < products.length ? products[table.getSelectedRow()].id() : -1;
        products = result;
        model.setRowCount(0);
        Color[] colors = new Color[result.length];
        for (int i = 0; i < result.length; i++) {
            Models.Product p = result[i];
            model.addRow(new Object[]{p.sku(), p.name(), p.categoryName() == null ? "—" : p.categoryName(),
                    String.format(java.util.Locale.ENGLISH, "%,.2f", p.sellingPrice()), p.quantity(), Format.statusLabel(p.stockStatus())});
            colors[i] = "out".equals(p.stockStatus()) ? Theme.DANGER : "low".equals(p.stockStatus()) ? Theme.WARNING : null;
        }
        table.putClientProperty("rowColors", colors);
        for (int i = 0; i < result.length; i++) {          // keep the same product selected after a reload
            if (result[i].id() == selectedId) table.setRowSelectionInterval(i, i);
        }
        table.repaint();
        count.setText(result.length + (result.length == 1 ? " product" : " products") + "  ·  prices in " + business.currency());
    }

    private void openDialog(boolean stockIn) {
        int row = table.getSelectedRow();
        if (row < 0) {
            banner.error("Select a product in the table first.");
            return;
        }
        banner.clear();
        Models.Product product = products[row];
        Models.Business business = frame.business();
        new StockDialog(frame, frame.api(), business, product, stockIn, result -> {
            String verb = result.type().equals("in") ? "added" : "removed";
            String text = product.name() + ": " + Math.abs(result.quantityChange()) + " " + verb + ". Stock is now " + result.quantityAfter() + ".";
            // low / out warnings use the alert level we already know for this product
            if (result.quantityAfter() == 0) banner.show(text + " This product is now OUT of stock.", Banner.Kind.WARNING);
            else if (result.quantityAfter() <= product.alertLevel()) banner.show(text + " That is at or below the alert level (" + product.alertLevel() + ").", Banner.Kind.WARNING);
            else banner.show(text, Banner.Kind.SUCCESS);
            refresh();
        }).setVisible(true);
    }

    /** Add (editExisting=false) or edit the selected product. The category and supplier lists come from the server first. */
    private void openProductDialog(boolean editExisting) {
        Models.Product product = null;
        if (editExisting) {
            int row = table.getSelectedRow();
            if (row < 0) {
                banner.error("Select a product in the table first.");
                return;
            }
            product = products[row];
        }
        banner.clear();
        Models.Business business = frame.business();
        Models.Product chosen = product;
        Async.run(() -> new Object[]{frame.api().categories(business.id()), frame.api().suppliers(business.id())}, lists -> {
            new ProductDialog(frame, frame.api(), business, chosen, (Models.Category[]) lists[0], (Models.Supplier[]) lists[1], () -> {
                banner.show(chosen == null ? "Product added." : "Product updated.", Banner.Kind.SUCCESS);
                refresh();
            }).setVisible(true);
        }, error -> frame.report(error, banner));
    }
}
