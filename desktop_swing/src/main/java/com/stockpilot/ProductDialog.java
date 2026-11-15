package com.stockpilot;

import javax.swing.*;
import java.awt.*;
import java.math.BigDecimal;
import java.util.LinkedHashMap;
import java.util.Map;


/** The 'Add product' / 'Edit product' pop-up (owners only; the server checks that too). */
public class ProductDialog extends JDialog {
    private static final String NONE = "None";

    private final JTextField name = Theme.textField(20);
    private final JTextField sku = Theme.textField(20);
    private final JTextField purchase = Theme.textField(8);
    private final JTextField selling = Theme.textField(8);
    private final JTextField alertLevel = Theme.textField(8, "Business default");
    private final JTextField opening = Theme.textField(8);
    private final JComboBox<Object> category;
    private final JComboBox<Object> supplier;
    private final JButton save;
    private final Banner banner = new Banner();
    private final ApiClient api;
    private final Models.Business business;
    private final Models.Product editing;     // null = adding a new product
    private final Runnable onSaved;

    public ProductDialog(Frame owner, ApiClient api, Models.Business business, Models.Product editing,
                         Models.Category[] categories, Models.Supplier[] suppliers, Runnable onSaved) {
        super(owner, editing == null ? "Add product" : "Edit product", true);
        this.api = api;
        this.business = business;
        this.editing = editing;
        this.onSaved = onSaved;
        category = Theme.combo(withNone(categories));
        supplier = Theme.combo(withNone(suppliers));
        name.setName("productName");
        sku.setName("productSku");
        purchase.setName("purchasePrice");
        selling.setName("sellingPrice");
        alertLevel.setName("alertLevel");
        opening.setName("openingQuantity");
        category.setName("productCategory");
        supplier.setName("productSupplier");
        banner.setName("dialogBanner");
        save = Theme.button(editing == null ? "Add product" : "Save changes", true);
        save.setName("save");

        JPanel body = new JPanel(new GridBagLayout());
        body.setBackground(Theme.CARD);
        body.setBorder(BorderFactory.createEmptyBorder(22, 28, 22, 28));
        GridBagConstraints c = new GridBagConstraints();
        c.fill = GridBagConstraints.HORIZONTAL;
        c.weightx = 1;
        c.gridx = 0;
        c.gridwidth = 2;
        c.gridy = 0;
        c.insets = new Insets(0, 0, 10, 0);
        body.add(banner, c);
        c.gridwidth = 1;
        int row = 1;
        row = addRow(body, c, row, "Name *", name, "SKU *", sku);
        row = addRow(body, c, row, "Category", category, "Supplier", supplier);
        row = addRow(body, c, row, "Purchase price (" + business.currency() + ")", purchase, "Selling price (" + business.currency() + ")", selling);
        row = addRow(body, c, row, "Low-stock alert level", alertLevel, editing == null ? "Opening quantity" : null, editing == null ? opening : null);

        JPanel buttons = new JPanel(new FlowLayout(FlowLayout.RIGHT, 10, 0));
        buttons.setOpaque(false);
        JButton cancel = Theme.button("Cancel", false);
        cancel.setName("cancel");
        cancel.addActionListener(e -> dispose());
        buttons.add(cancel);
        buttons.add(save);
        c.gridx = 0;
        c.gridy = row;
        c.gridwidth = 2;
        c.insets = new Insets(18, 0, 0, 0);
        body.add(buttons, c);

        if (editing != null) fillFromProduct(categories, suppliers);
        setContentPane(body);
        save.addActionListener(e -> submit());
        getRootPane().registerKeyboardAction(e -> dispose(), KeyStroke.getKeyStroke("ESCAPE"), JComponent.WHEN_IN_FOCUSED_WINDOW);
        setResizable(false);
        setSize(620, 440);
        setLocationRelativeTo(owner);
    }

    private static Object[] withNone(Object[] items) {
        Object[] all = new Object[items.length + 1];
        all[0] = NONE;
        System.arraycopy(items, 0, all, 1, items.length);
        return all;
    }

    /** Two labelled fields side by side: label row, then field row. */
    private static int addRow(JPanel body, GridBagConstraints c, int row, String leftLabel, JComponent left, String rightLabel, JComponent right) {
        c.gridy = row++;
        c.insets = new Insets(8, 0, 3, 8);
        c.gridx = 0;
        body.add(Theme.label(leftLabel, 12, Font.PLAIN, Theme.MUTED), c);
        if (rightLabel != null) {
            c.gridx = 1;
            c.insets = new Insets(8, 8, 3, 0);
            body.add(Theme.label(rightLabel, 12, Font.PLAIN, Theme.MUTED), c);
        }
        c.gridy = row++;
        c.gridx = 0;
        c.insets = new Insets(0, 0, 0, 8);
        body.add(left, c);
        if (right != null) {
            c.gridx = 1;
            c.insets = new Insets(0, 8, 0, 0);
            body.add(right, c);
        }
        return row;
    }

    private void fillFromProduct(Models.Category[] categories, Models.Supplier[] suppliers) {
        name.setText(editing.name());
        sku.setText(editing.sku());
        purchase.setText(String.format(java.util.Locale.ENGLISH, "%.2f", editing.purchasePrice()));
        selling.setText(String.format(java.util.Locale.ENGLISH, "%.2f", editing.sellingPrice()));
        alertLevel.setText(String.valueOf(editing.alertLevel()));
        for (Models.Category item : categories) if (editing.categoryId() != null && item.id() == editing.categoryId()) category.setSelectedItem(item);
        for (Models.Supplier item : suppliers) if (editing.supplierId() != null && item.id() == editing.supplierId()) supplier.setSelectedItem(item);
    }

    /** Reads a price: empty means 0; returns null (after showing a message) when it is not a valid price. */
    private BigDecimal readPrice(JTextField field, String what) {
        String text = field.getText().trim();
        if (text.isEmpty()) return BigDecimal.ZERO;
        try {
            BigDecimal value = new BigDecimal(text);
            if (value.signum() >= 0 && value.scale() <= 2 && value.precision() <= 12) return value;
        } catch (NumberFormatException ignored) {
            // falls through to the message below
        }
        banner.error("The " + what + " must be a number of zero or more with at most 2 decimals.");
        return null;
    }

    private Integer readWholeNumber(JTextField field, String what) {
        String text = field.getText().trim();
        if (text.isEmpty()) return -1;     // -1 = "not given"
        if (!text.matches("\\d{1,7}")) {
            banner.error("The " + what + " must be a whole number.");
            return null;
        }
        return Integer.parseInt(text);
    }

    private void submit() {
        if (name.getText().isBlank() || sku.getText().isBlank()) {
            banner.error("Name and SKU are required.");
            return;
        }
        BigDecimal buy = readPrice(purchase, "purchase price");
        if (buy == null) return;
        BigDecimal sell = readPrice(selling, "selling price");
        if (sell == null) return;
        Integer level = readWholeNumber(alertLevel, "alert level");
        if (level == null) return;
        Integer start = editing == null ? readWholeNumber(opening, "opening quantity") : -1;
        if (start == null) return;

        Map<String, Object> values = new LinkedHashMap<>();
        values.put("name", name.getText().trim());
        values.put("sku", sku.getText().trim());
        values.put("category_id", category.getSelectedItem() instanceof Models.Category cat ? cat.id() : null);
        values.put("supplier_id", supplier.getSelectedItem() instanceof Models.Supplier sup ? sup.id() : null);
        values.put("purchase_price", buy);
        values.put("selling_price", sell);
        values.put("min_stock", level >= 0 ? level : null);       // null = the business default
        if (editing == null && start > 0) values.put("opening_quantity", start);

        banner.clear();
        save.setEnabled(false);
        Async.run(() -> editing == null ? api.createProduct(business.id(), values) : api.updateProduct(business.id(), editing.id(), values),
                saved -> {
                    dispose();
                    onSaved.run();
                },
                error -> {
                    save.setEnabled(true);
                    banner.error(error.getMessage());
                });
    }
}
