package com.stockpilot;

import javax.swing.*;
import javax.swing.border.EmptyBorder;
import java.awt.*;

/** A message strip: error (red), success (green, disappears after 4 s) or warning (amber). Hidden until used. */
public class Banner extends JPanel {
    public enum Kind { ERROR, SUCCESS, WARNING }

    private final JLabel message = new JLabel();
    private Timer hideTimer;

    public Banner() {
        super(new BorderLayout());
        message.setFont(Theme.font(13, Font.PLAIN));
        add(message, BorderLayout.CENTER);
        setBorder(new EmptyBorder(10, 14, 10, 14));
        setVisible(false);
    }

    public void show(String text, Kind kind) {
        Color color = switch (kind) { case ERROR -> Theme.DANGER; case SUCCESS -> Theme.SUCCESS; case WARNING -> Theme.WARNING; };
        setBackground(mix(color, Theme.BG, 0.14f));
        setBorder(BorderFactory.createCompoundBorder(BorderFactory.createLineBorder(mix(color, Theme.BG, 0.5f)), new EmptyBorder(9, 13, 9, 13)));
        message.setForeground(color);
        message.setText("<html>" + escape(text) + "</html>");   // html so long messages wrap
        setVisible(true);
        if (hideTimer != null) hideTimer.stop();
        if (kind == Kind.SUCCESS) {
            hideTimer = new Timer(4000, e -> setVisible(false));
            hideTimer.setRepeats(false);
            hideTimer.start();
        }
        revalidate();
    }

    public void error(String text) { show(text, Kind.ERROR); }

    public void clear() {
        if (hideTimer != null) hideTimer.stop();
        setVisible(false);
    }

    public String text() { return message.getText().replaceAll("<[^>]*>", ""); }

    @Override protected void paintComponent(Graphics g) {
        g.setColor(getBackground());
        g.fillRect(0, 0, getWidth(), getHeight());
    }

    private static Color mix(Color c, Color base, float amount) {
        return new Color(Math.round(base.getRed() + (c.getRed() - base.getRed()) * amount),
                Math.round(base.getGreen() + (c.getGreen() - base.getGreen()) * amount),
                Math.round(base.getBlue() + (c.getBlue() - base.getBlue()) * amount));
    }

    private static String escape(String text) {   // the text comes from the server, so never let it act as HTML
        return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;");
    }
}
