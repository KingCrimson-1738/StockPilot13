package com.stockpilot;

import javax.swing.*;
import javax.swing.table.DefaultTableModel;
import java.awt.*;

/** Basic reports: what to restock, and how much stock value each category holds. Both come from the server. */
public class ReportsPanel extends JPanel implements Refreshable {
    private final MainFrame frame;
    private final DefaultTableModel restockModel = new DefaultTableModel(
            new String[]{"PRODUCT", "SKU", "SUPPLIER", "IN STOCK", "ALERT LEVEL", "SUGGESTED ORDER", "EST. COST"}, 0);
    private final DefaultTableModel categoryModel = new DefaultTableModel(
            new String[]{"CATEGORY", "PRODUCTS", "UNITS", "VALUE (AT COST)"}, 0);
    private final JLabel restockCount = Theme.label(" ", 13, Font.PLAIN, Theme.MUTED);
    private final JLabel categoryCount = Theme.label(" ", 13, Font.PLAIN, Theme.MUTED);
    private final Banner banner = new Banner();
    private int requestNumber;

    public ReportsPanel(MainFrame frame) {
        super(new BorderLayout(0, 12));
        this.frame = frame;
        setOpaque(false);
        banner.setName("reportsBanner");
        JTable restock = Theme.table(restockModel, 3, 4, 5, 6);
        restock.setName("restockTable");
        JTable categories = Theme.table(categoryModel, 1, 2, 3);
        categories.setName("categoryTable");

        JPanel grid = new JPanel(new GridLayout(2, 1, 0, 16));
        grid.setOpaque(false);
        grid.add(section("Restock list (at or below the alert level)", restockCount, restock));
        grid.add(section("Stock value by category", categoryCount, categories));
        add(banner, BorderLayout.NORTH);
        add(grid, BorderLayout.CENTER);
    }

    private static JPanel section(String title, JLabel count, JTable table) {
        JPanel panel = new JPanel(new BorderLayout(0, 8));
        panel.setOpaque(false);
        JPanel heading = new JPanel(new BorderLayout(12, 0));
        heading.setOpaque(false);
        heading.add(Theme.label(title, 15, Font.BOLD, Theme.TEXT), BorderLayout.WEST);
        heading.add(count, BorderLayout.CENTER);
        panel.add(heading, BorderLayout.NORTH);
        panel.add(Theme.scroll(table), BorderLayout.CENTER);
        return panel;
    }

    @Override public void refresh() {
        banner.clear();
        Models.Business business = frame.business();
        int number = ++requestNumber;
        Async.run(() -> new Object[]{frame.api().lowStockReport(business.id()), frame.api().categoryValueReport(business.id())}, result -> {
            if (number != requestNumber || business.id() != frame.business().id()) return;
            Models.RestockItem[] restock = (Models.RestockItem[]) result[0];
            Models.CategoryValue[] values = (Models.CategoryValue[]) result[1];
            restockModel.setRowCount(0);
            for (Models.RestockItem r : restock) {
                restockModel.addRow(new Object[]{r.name(), r.sku(), r.supplierName() == null ? "—" : r.supplierName(), r.quantity(),
                        r.alertLevel(), r.suggestedOrder(), Format.money(r.estimatedCost(), business.currency())});
            }
            restockCount.setText(restock.length == 0 ? "Nothing needs restocking." : restock.length + " to restock");
            categoryModel.setRowCount(0);
            for (Models.CategoryValue v : values) {
                categoryModel.addRow(new Object[]{v.category(), v.productCount(), v.units(), Format.money(v.value(), business.currency())});
            }
            categoryCount.setText(values.length == 0 ? "No products yet." : values.length + (values.length == 1 ? " category" : " categories"));
        }, error -> {
            if (number == requestNumber) frame.report(error, banner);
        });
    }
}
