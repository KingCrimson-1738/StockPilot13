package com.stockpilot;

import javax.swing.*;
import java.awt.*;
import java.util.function.Consumer;

/** The 'Stock in' / 'Stock out' pop-up. The server makes the final decision (e.g. it refuses to go below zero). */
public class StockDialog extends JDialog {
    private final JTextField quantity = Theme.textField(10);
    private final JTextField reason = Theme.textField(10);
    private final JLabel preview = Theme.label(" ", 13, Font.BOLD, Theme.MUTED);
    private final JButton save;
    private final Banner banner = new Banner();
    private final ApiClient api;
    private final Models.Business business;
    private final Models.Product product;
    private final boolean stockIn;
    private final Consumer<Models.StockResult> onSaved;

    public StockDialog(Frame owner, ApiClient api, Models.Business business, Models.Product product, boolean stockIn,
                       Consumer<Models.StockResult> onSaved) {
        super(owner, stockIn ? "Stock in" : "Stock out", true);
        this.api = api;
        this.business = business;
        this.product = product;
        this.stockIn = stockIn;
        this.onSaved = onSaved;
        quantity.setName("quantity");
        reason.setName("reason");
        banner.setName("dialogBanner");
        save = Theme.button(stockIn ? "Record stock in" : "Record stock out", true);
        save.setName("save");

        JPanel body = new JPanel(new GridBagLayout());
        body.setBackground(Theme.CARD);
        body.setBorder(BorderFactory.createEmptyBorder(24, 28, 24, 28));
        GridBagConstraints c = new GridBagConstraints();
        c.gridx = 0;
        c.fill = GridBagConstraints.HORIZONTAL;
        c.weightx = 1;
        c.anchor = GridBagConstraints.WEST;
        int row = 0;
        c.gridy = row++;
        body.add(Theme.label(product.name(), 18, Font.BOLD, Theme.TEXT), c);
        c.gridy = row++;
        c.insets = new Insets(2, 0, 14, 0);
        body.add(Theme.label("SKU " + product.sku() + "   ·   In stock: " + product.quantity() + "   ·   Alert level: " + product.alertLevel(),
                12, Font.PLAIN, Theme.MUTED), c);
        c.gridy = row++;
        c.insets = new Insets(0, 0, 8, 0);
        body.add(banner, c);
        c.gridy = row++;
        c.insets = new Insets(4, 0, 4, 0);
        body.add(Theme.label(stockIn ? "Quantity to add" : "Quantity to remove", 12, Font.PLAIN, Theme.MUTED), c);
        c.gridy = row++;
        c.insets = new Insets(0, 0, 0, 0);
        body.add(quantity, c);
        c.gridy = row++;
        c.insets = new Insets(12, 0, 4, 0);
        body.add(Theme.label("Reason (optional)", 12, Font.PLAIN, Theme.MUTED), c);
        c.gridy = row++;
        c.insets = new Insets(0, 0, 0, 0);
        body.add(reason, c);
        c.gridy = row++;
        c.insets = new Insets(12, 0, 0, 0);
        body.add(preview, c);
        JPanel buttons = new JPanel(new FlowLayout(FlowLayout.RIGHT, 10, 0));
        buttons.setOpaque(false);
        JButton cancel = Theme.button("Cancel", false);
        cancel.setName("cancel");
        cancel.addActionListener(e -> dispose());
        buttons.add(cancel);
        buttons.add(save);
        c.gridy = row;
        c.insets = new Insets(20, 0, 0, 0);
        body.add(buttons, c);

        setContentPane(body);
        save.addActionListener(e -> submit());
        quantity.addActionListener(e -> submit());
        reason.addActionListener(e -> submit());
        quantity.getDocument().addDocumentListener(new SimpleDocumentListener(this::updatePreview));
        getRootPane().registerKeyboardAction(e -> dispose(), KeyStroke.getKeyStroke("ESCAPE"), JComponent.WHEN_IN_FOCUSED_WINDOW);
        setResizable(false);
        setSize(460, 420);
        setLocationRelativeTo(owner);
    }

    /** Shows what the stock will be after the movement, before anything is saved. */
    private void updatePreview() {
        banner.clear();   // the user is correcting the number, so the old error message is out of date
        String text = quantity.getText().trim();
        if (!text.matches("\\d{1,9}")) {
            preview.setText(" ");
            return;
        }
        int amount = Integer.parseInt(text);
        int after = stockIn ? product.quantity() + amount : product.quantity() - amount;
        if (after < 0) {
            preview.setForeground(Theme.DANGER);
            preview.setText("Not enough stock: only " + product.quantity() + " available.");
        } else {
            preview.setForeground(after <= product.alertLevel() ? Theme.WARNING : Theme.SUCCESS);
            preview.setText("Stock after: " + after);
        }
    }

    /** Returns the quantity, or null (after showing a message) if the text is not a valid quantity. */
    private Integer readQuantity() {
        String text = quantity.getText().trim();
        if (text.isEmpty()) {
            banner.error("Please enter a quantity.");
            return null;
        }
        if (!text.matches("\\d+")) {
            banner.error("The quantity must be a whole number.");
            return null;
        }
        long amount = text.length() > 9 ? Long.MAX_VALUE : Long.parseLong(text);   // long, so a huge number cannot overflow
        if (amount < 1 || amount > 1_000_000) {
            banner.error("The quantity must be between 1 and 1,000,000.");
            return null;
        }
        if (!stockIn && amount > product.quantity()) {
            banner.error("Not enough stock. Available: " + product.quantity() + ", requested: " + amount + ".");
            return null;
        }
        return (int) amount;
    }

    private void submit() {
        Integer amount = readQuantity();
        if (amount == null) return;
        banner.clear();
        save.setEnabled(false);
        String why = reason.getText();
        Async.run(() -> stockIn ? api.stockIn(business.id(), product.id(), amount, why)
                        : api.stockOut(business.id(), product.id(), amount, why),
                result -> {
                    dispose();
                    onSaved.accept(result);
                },
                error -> {
                    save.setEnabled(true);
                    banner.error(error.getMessage());   // e.g. the server says someone else just sold the stock
                });
    }
}
