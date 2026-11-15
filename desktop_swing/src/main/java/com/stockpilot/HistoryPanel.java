package com.stockpilot;

import javax.swing.*;
import javax.swing.table.DefaultTableModel;
import java.awt.*;

public class HistoryPanel extends JPanel implements Refreshable {
    private static final String[] TYPE_LABELS = {"All movements", "Stock in", "Stock out", "Adjustments"};
    private static final String[] TYPE_VALUES = {"", "in", "out", "adjust"};
    private static final int LIMIT = 200;

    private final MainFrame frame;
    private final JComboBox<String> type = Theme.combo(TYPE_LABELS);
    private final DefaultTableModel model = new DefaultTableModel(
            new String[]{"WHEN", "PRODUCT", "TYPE", "CHANGE", "AFTER", "BY", "REASON"}, 0);
    private final JLabel count = Theme.label(" ", 13, Font.PLAIN, Theme.MUTED);
    private final Banner banner = new Banner();
    private int requestNumber;

    public HistoryPanel(MainFrame frame) {
        super(new BorderLayout(0, 12));
        this.frame = frame;
        setOpaque(false);
        type.setName("typeFilter");
        banner.setName("historyBanner");
        JTable table = Theme.table(model, 3, 4);
        table.setName("historyTable");

        JPanel top = new JPanel(new BorderLayout(0, 12));
        top.setOpaque(false);
        top.add(banner, BorderLayout.NORTH);
        JPanel bar = new JPanel(new BorderLayout(12, 0));
        bar.setOpaque(false);
        bar.add(type, BorderLayout.WEST);
        bar.add(count, BorderLayout.CENTER);
        top.add(bar, BorderLayout.CENTER);
        add(top, BorderLayout.NORTH);
        add(Theme.scroll(table), BorderLayout.CENTER);
        type.addActionListener(e -> refresh());
    }

    @Override public void refresh() {
        banner.clear();
        Models.Business business = frame.business();
        String kind = TYPE_VALUES[type.getSelectedIndex()];
        int number = ++requestNumber;
        Async.run(() -> frame.api().transactions(business.id(), kind, LIMIT), rows -> {
            if (number != requestNumber || business.id() != frame.business().id()) return;
            model.setRowCount(0);
            for (Models.Transaction t : rows) {
                model.addRow(new Object[]{Format.when(t.createdAt()), t.productName(), Format.typeLabel(t.type()),
                        Format.signed(t.quantityChange()), t.quantityAfter(),
                        t.userName() == null ? "—" : t.userName(), t.reason() == null ? "—" : t.reason()});
            }
            count.setText(rows.length + (rows.length == 1 ? " movement" : " movements") + (rows.length == LIMIT ? "  ·  showing the newest " + LIMIT : ""));
        }, error -> {
            if (number == requestNumber) frame.report(error, banner);
        });
    }
}
