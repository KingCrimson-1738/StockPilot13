package com.stockpilot;

import javax.swing.*;
import javax.swing.table.DefaultTableModel;
import java.awt.*;

public class DashboardPanel extends JPanel implements Refreshable {
    private final MainFrame frame;
    private final JLabel[] values = new JLabel[4];
    private final DefaultTableModel recentModel = new DefaultTableModel(new String[]{"WHEN", "PRODUCT", "TYPE", "CHANGE", "AFTER", "BY"}, 0);
    private final Banner banner = new Banner();
    private int requestNumber;

    public DashboardPanel(MainFrame frame) {
        super(new BorderLayout(0, 16));
        this.frame = frame;
        banner.setName("dashboardBanner");
        setOpaque(false);

        JPanel top = new JPanel(new BorderLayout(0, 12));
        top.setOpaque(false);
        top.add(banner, BorderLayout.NORTH);
        JPanel cards = new JPanel(new GridLayout(1, 4, 14, 0));
        cards.setOpaque(false);
        String[] titles = {"Total products", "Units in stock", "Inventory value", "Needs attention"};
        for (int i = 0; i < 4; i++) {
            values[i] = Theme.label("…", 22, Font.BOLD, Theme.TEXT);
            values[i].setName("stat" + i);
            JPanel card = new JPanel(new GridLayout(2, 1, 0, 4));
            card.setBackground(Theme.CARD);
            card.setBorder(BorderFactory.createEmptyBorder(16, 18, 16, 18));
            card.add(Theme.label(titles[i], 12, Font.PLAIN, Theme.MUTED));
            card.add(values[i]);
            cards.add(card);
        }
        top.add(cards, BorderLayout.CENTER);
        add(top, BorderLayout.NORTH);

        JPanel recent = new JPanel(new BorderLayout(0, 8));
        recent.setOpaque(false);
        recent.add(Theme.label("Recent stock movements", 15, Font.BOLD, Theme.TEXT), BorderLayout.NORTH);
        JTable table = Theme.table(recentModel, 3, 4);
        table.setName("recentTable");
        recent.add(Theme.scroll(table), BorderLayout.CENTER);
        add(recent, BorderLayout.CENTER);
    }

    @Override public void refresh() {
        banner.clear();
        Models.Business business = frame.business();
        int number = ++requestNumber;
        Async.run(() -> frame.api().dashboard(business.id()), d -> {
            if (number != requestNumber || business.id() != frame.business().id()) return;   // an old answer: ignore it
            values[0].setText(Format.number(d.totalProducts()));
            values[1].setText(Format.number(d.totalStock()));
            values[2].setText(Format.money(d.inventoryValue(), d.currency()));
            int attention = d.lowStockCount() + d.outOfStockCount();
            values[3].setText(attention + " (" + d.lowStockCount() + " low, " + d.outOfStockCount() + " out)");
            values[3].setForeground(attention > 0 ? Theme.WARNING : Theme.SUCCESS);
            recentModel.setRowCount(0);
            for (Models.Transaction t : d.recentTransactions()) {
                recentModel.addRow(new Object[]{Format.when(t.createdAt()), t.productName(), Format.typeLabel(t.type()),
                        Format.signed(t.quantityChange()), t.quantityAfter(), t.userName() == null ? "—" : t.userName()});
            }
        }, error -> {
            if (number == requestNumber) frame.report(error, banner);
        });
    }
}
