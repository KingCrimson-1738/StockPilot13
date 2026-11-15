package com.stockpilot;

import javax.swing.*;
import java.awt.*;

public class LoginFrame extends JFrame {
    private final ApiClient api;
    private final JTextField email = Theme.textField(22);
    private final JPasswordField password = Theme.passwordField(22);
    private final JButton signIn = Theme.button("Log in", true);
    private final Banner banner = new Banner();

    public LoginFrame(ApiClient api, String serverUrl) {
        super("StockPilot");
        this.api = api;
        email.setName("email");
        password.setName("password");
        signIn.setName("login");
        banner.setName("banner");

        JPanel card = new JPanel(new GridBagLayout());
        card.setBackground(Theme.CARD);
        card.setBorder(BorderFactory.createEmptyBorder(32, 36, 32, 36));
        GridBagConstraints c = new GridBagConstraints();
        c.gridx = 0;
        c.fill = GridBagConstraints.HORIZONTAL;
        c.weightx = 1;
        c.anchor = GridBagConstraints.WEST;

        c.gridy = 0;
        card.add(Theme.label("Welcome back", 24, Font.BOLD, Theme.TEXT), c);
        c.gridy = 1;
        c.insets = new Insets(4, 0, 18, 0);
        card.add(Theme.label("Log in to manage your stock", 13, Font.PLAIN, Theme.MUTED), c);
        c.gridy = 2;
        c.insets = new Insets(0, 0, 10, 0);
        card.add(banner, c);
        c.gridy = 3;
        c.insets = new Insets(8, 0, 4, 0);
        card.add(Theme.label("Email", 12, Font.PLAIN, Theme.MUTED), c);
        c.gridy = 4;
        c.insets = new Insets(0, 0, 0, 0);
        card.add(email, c);
        c.gridy = 5;
        c.insets = new Insets(14, 0, 4, 0);
        card.add(Theme.label("Password", 12, Font.PLAIN, Theme.MUTED), c);
        c.gridy = 6;
        c.insets = new Insets(0, 0, 0, 0);
        card.add(password, c);
        c.gridy = 7;
        c.insets = new Insets(22, 0, 0, 0);
        card.add(signIn, c);
        c.gridy = 8;
        c.insets = new Insets(16, 0, 0, 0);
        card.add(Theme.label("Server: " + serverUrl, 11, Font.PLAIN, Theme.MUTED), c);
        if (Main.isInsecure(serverUrl)) {
            c.gridy = 10;
            c.insets = new Insets(6, 0, 0, 0);
            card.add(Theme.label("<html>Warning: this address is not HTTPS, so your password is not encrypted.</html>", 11, Font.PLAIN, Theme.WARNING), c);
        }
        c.gridy = 9;
        c.insets = new Insets(4, 0, 0, 0);
        card.add(Theme.label("New here? Create an account in the main StockPilot app.", 11, Font.PLAIN, Theme.MUTED), c);

        JPanel background = new JPanel(new GridBagLayout());
        background.setBackground(Theme.BG);
        background.add(card);
        setContentPane(background);

        signIn.addActionListener(e -> submit());
        password.addActionListener(e -> submit());
        email.addActionListener(e -> password.requestFocusInWindow());

        setDefaultCloseOperation(EXIT_ON_CLOSE);
        setSize(520, 560);
        setMinimumSize(new Dimension(460, 520));
        setLocationRelativeTo(null);
    }

    private void submit() {
        String emailText = email.getText().trim();
        String passwordText = new String(password.getPassword());
        if (emailText.isEmpty() || passwordText.isEmpty()) {
            banner.error("Please enter your email and password.");
            return;
        }
        banner.clear();
        signIn.setEnabled(false);
        signIn.setText("Logging in…");
        Async.run(() -> {
                    Models.User user = api.login(emailText, passwordText);
                    return new Object[]{user, api.businesses()};   // both requests run on the background thread
                },
                result -> {
                    Models.User user = (Models.User) result[0];
                    Models.Business[] businesses = (Models.Business[]) result[1];
                    if (businesses.length == 0) {
                        reset();
                        banner.show("You are not part of any business yet. Create one in the main StockPilot app, then log in again.", Banner.Kind.WARNING);
                        return;
                    }
                    new MainFrame(api, user, businesses).setVisible(true);
                    dispose();
                },
                error -> {
                    reset();
                    banner.error(error.getMessage());
                });
    }

    private void reset() {
        signIn.setEnabled(true);
        signIn.setText("Log in");
    }
}
