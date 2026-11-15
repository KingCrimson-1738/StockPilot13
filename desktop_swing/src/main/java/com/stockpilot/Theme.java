package com.stockpilot;

import javax.swing.*;
import javax.swing.border.EmptyBorder;
import javax.swing.table.DefaultTableCellRenderer;
import javax.swing.table.JTableHeader;
import java.awt.*;

/** All colours and fonts in one place (the same palette as the Tkinter app), plus helpers that style components. */
public final class Theme {
    private Theme() {}

    public static final Color BG = new Color(0x0B1120);
    public static final Color SIDEBAR = new Color(0x111827);
    public static final Color CARD = new Color(0x1E293B);
    public static final Color INPUT = new Color(0x0F172A);
    public static final Color BORDER = new Color(0x334155);
    public static final Color PRIMARY = new Color(0x3B82F6);
    public static final Color PRIMARY_HOVER = new Color(0x2563EB);
    public static final Color TEXT = new Color(0xF8FAFC);
    public static final Color MUTED = new Color(0x94A3B8);
    public static final Color SUCCESS = new Color(0x22C55E);
    public static final Color WARNING = new Color(0xF59E0B);
    public static final Color DANGER = new Color(0xEF4444);

    public static Font font(float size, int style) {
        return new Font("SansSerif", style, 1).deriveFont(style, size);
    }

    /** Make menus, dialogs and tooltips match the dark theme. */
    public static void install() {
        UIManager.put("Panel.background", BG);
        UIManager.put("OptionPane.background", CARD);
        UIManager.put("OptionPane.messageForeground", TEXT);
        UIManager.put("ComboBox.background", CARD);
        UIManager.put("ComboBox.foreground", TEXT);
        UIManager.put("ComboBox.selectionBackground", PRIMARY);
        UIManager.put("ComboBox.selectionForeground", TEXT);
        UIManager.put("List.background", CARD);
        UIManager.put("List.foreground", TEXT);
        UIManager.put("List.selectionBackground", PRIMARY);
        UIManager.put("ScrollBar.background", CARD);
    }

    public static JLabel label(String text, float size, int style, Color color) {
        JLabel label = new JLabel(text);
        label.setFont(font(size, style));
        label.setForeground(color);
        return label;
    }

    public static JTextField textField(int columns) {
        JTextField field = new JTextField(columns);
        styleInput(field);
        return field;
    }

    /** A text box that shows a grey hint while it is empty (Swing has no built-in placeholder). */
    public static JTextField textField(int columns, String hint) {
        JTextField field = new JTextField(columns) {
            @Override protected void paintComponent(Graphics g) {
                super.paintComponent(g);
                if (getText().isEmpty()) {
                    Graphics2D g2 = (Graphics2D) g.create();
                    g2.setRenderingHint(RenderingHints.KEY_TEXT_ANTIALIASING, RenderingHints.VALUE_TEXT_ANTIALIAS_ON);
                    g2.setColor(MUTED);
                    g2.setFont(getFont());
                    Insets in = getInsets();
                    g2.drawString(hint, in.left, (getHeight() + g2.getFontMetrics().getAscent() - g2.getFontMetrics().getDescent()) / 2);
                    g2.dispose();
                }
            }
        };
        styleInput(field);
        return field;
    }

    public static JPasswordField passwordField(int columns) {
        JPasswordField field = new JPasswordField(columns);
        styleInput(field);
        return field;
    }

    private static void styleInput(JTextField field) {
        field.setFont(font(14, Font.PLAIN));
        field.setBackground(INPUT);
        field.setForeground(TEXT);
        field.setCaretColor(TEXT);
        field.setBorder(BorderFactory.createCompoundBorder(BorderFactory.createLineBorder(BORDER), new EmptyBorder(8, 10, 8, 10)));
    }

    public static JButton button(String text, boolean primary) {
        JButton button = new JButton(text);
        Color normal = primary ? PRIMARY : CARD;
        Color hover = primary ? PRIMARY_HOVER : BORDER;
        button.setFont(font(13, Font.BOLD));
        button.setForeground(TEXT);
        button.setBackground(normal);
        button.setOpaque(true);
        button.setContentAreaFilled(true);
        button.setFocusPainted(false);
        button.setBorder(BorderFactory.createCompoundBorder(BorderFactory.createLineBorder(primary ? PRIMARY : BORDER), new EmptyBorder(9, 18, 9, 18)));
        button.setCursor(Cursor.getPredefinedCursor(Cursor.HAND_CURSOR));
        button.addChangeListener(e -> button.setBackground(button.getModel().isRollover() ? hover : normal));
        return button;
    }

    public static <T> JComboBox<T> combo(T[] items) {
        JComboBox<T> box = new JComboBox<>(items);
        box.setFont(font(13, Font.PLAIN));
        box.setBackground(CARD);
        box.setForeground(TEXT);
        box.setBorder(BorderFactory.createLineBorder(BORDER));
        box.setRenderer(new DefaultListCellRenderer() {
            @Override public Component getListCellRendererComponent(JList<?> list, Object value, int index, boolean selected, boolean focus) {
                super.getListCellRendererComponent(list, value, index, selected, focus);
                setBackground(selected ? PRIMARY : CARD);
                setForeground(TEXT);
                setBorder(new EmptyBorder(5, 8, 5, 8));
                return this;
            }
        });
        return box;
    }

    /** A dark table. Pass the column indexes that hold numbers so they are right-aligned. */
    public static JTable table(javax.swing.table.TableModel model, int... numberColumns) {
        JTable table = new JTable(model) {
            @Override public boolean isCellEditable(int row, int column) { return false; }
        };
        table.setBackground(CARD);
        table.setForeground(TEXT);
        table.setGridColor(CARD);
        table.setRowHeight(32);
        table.setFont(font(13, Font.PLAIN));
        table.setShowVerticalLines(false);
        table.setSelectionBackground(PRIMARY);
        table.setSelectionForeground(TEXT);
        table.setFillsViewportHeight(true);
        table.setIntercellSpacing(new Dimension(0, 1));
        JTableHeader header = table.getTableHeader();
        header.setBackground(SIDEBAR);
        header.setForeground(MUTED);
        header.setFont(font(11, Font.BOLD));
        header.setReorderingAllowed(false);
        header.setBorder(BorderFactory.createEmptyBorder());
        DefaultTableCellRenderer headerRenderer = new DefaultTableCellRenderer();
        headerRenderer.setBackground(SIDEBAR);
        headerRenderer.setForeground(MUTED);
        headerRenderer.setFont(font(11, Font.BOLD));
        headerRenderer.setBorder(new EmptyBorder(0, 10, 0, 10));
        header.setDefaultRenderer(new javax.swing.table.TableCellRenderer() {
            @Override public Component getTableCellRendererComponent(JTable t, Object v, boolean s, boolean f, int row, int col) {
                Component c = headerRenderer.getTableCellRendererComponent(t, v, s, f, row, col);
                headerRenderer.setBorder(new EmptyBorder(0, 10, 0, 10));   // the call above resets the border, so set it again
                boolean number = java.util.Arrays.stream(numberColumns).anyMatch(n -> n == col);
                headerRenderer.setHorizontalAlignment(number ? SwingConstants.RIGHT : SwingConstants.LEFT);
                return c;
            }
        });
        for (int index = 0; index < model.getColumnCount(); index++) {
            final int col = index;   // a lambda may only use variables that never change
            boolean number = java.util.Arrays.stream(numberColumns).anyMatch(n -> n == col);
            DefaultTableCellRenderer renderer = new DefaultTableCellRenderer() {
                @Override public Component getTableCellRendererComponent(JTable t, Object v, boolean sel, boolean foc, int row, int c) {
                    super.getTableCellRendererComponent(t, v, sel, foc, row, c);
                    setBorder(new EmptyBorder(0, 10, 0, 10));
                    setHorizontalAlignment(number ? SwingConstants.RIGHT : SwingConstants.LEFT);
                    if (!sel) {
                        setBackground(CARD);
                        Object marker = t.getClientProperty("rowColors");
                        Color color = marker instanceof Color[] colors && row < colors.length ? colors[row] : null;
                        setForeground(color != null ? color : TEXT);
                    }
                    return this;
                }
            };
            table.getColumnModel().getColumn(col).setCellRenderer(renderer);
        }
        return table;
    }

    public static JScrollPane scroll(JComponent inner) {
        JScrollPane pane = new JScrollPane(inner);
        pane.setBorder(BorderFactory.createLineBorder(CARD));
        pane.getViewport().setBackground(CARD);
        pane.setBackground(CARD);
        return pane;
    }
}
