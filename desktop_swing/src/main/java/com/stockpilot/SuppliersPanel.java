package com.stockpilot;

import javax.swing.*;
import javax.swing.table.DefaultTableModel;
import java.awt.*;

/** Read-only list of the business's suppliers (adding and editing suppliers is done in the Tkinter app). */
public class SuppliersPanel extends JPanel implements Refreshable {
    private final MainFrame frame;
    private final DefaultTableModel model = new DefaultTableModel(
            new String[]{"SUPPLIER", "CONTACT", "EMAIL", "PHONE", "PRODUCTS"}, 0);
    private final JLabel count = Theme.label(" ", 13, Font.PLAIN, Theme.MUTED);
    private final Banner banner = new Banner();
    private int requestNumber;

    public SuppliersPanel(MainFrame frame) {
        super(new BorderLayout(0, 12));
        this.frame = frame;
        setOpaque(false);
        banner.setName("suppliersBanner");
        JTable table = Theme.table(model, 4);
        table.setName("supplierTable");
        JPanel top = new JPanel(new BorderLayout(0, 12));
        top.setOpaque(false);
        top.add(banner, BorderLayout.NORTH);
        top.add(count, BorderLayout.CENTER);
        add(top, BorderLayout.NORTH);
        add(Theme.scroll(table), BorderLayout.CENTER);
    }

    @Override public void refresh() {
        banner.clear();
        Models.Business business = frame.business();
        int number = ++requestNumber;
        Async.run(() -> frame.api().suppliers(business.id()), rows -> {
            if (number != requestNumber || business.id() != frame.business().id()) return;
            model.setRowCount(0);
            for (Models.Supplier s : rows) {
                model.addRow(new Object[]{s.name(), dash(s.contactPerson()), dash(s.email()), dash(s.phone()), s.productCount()});
            }
            count.setText(rows.length + (rows.length == 1 ? " supplier" : " suppliers")
                    + (rows.length == 0 ? "  ·  add suppliers in the Tkinter app" : ""));
        }, error -> {
            if (number == requestNumber) frame.report(error, banner);
        });
    }

    private static String dash(String text) {
        return text == null || text.isBlank() ? "—" : text;
    }
}
