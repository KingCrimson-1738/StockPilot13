package com.stockpilot;

import javax.swing.*;

/** Start-up. The backend address comes from the STOCKPILOT_API_URL environment variable (default: a local server). */
public class Main {
    public static String serverUrl() {
        return normalise(System.getenv("STOCKPILOT_API_URL"));
    }

    /** '  my-app.vercel.app/ ' -> 'https://my-app.vercel.app' (adds https:// when no scheme was typed). */
    static String normalise(String text) {
        String url = text == null ? "" : text.trim();
        while (url.endsWith("/")) url = url.substring(0, url.length() - 1);
        if (url.isEmpty()) return "http://127.0.0.1:8000";
        return url.contains("://") ? url : "https://" + url;
    }

    /** True for plain http to another computer: the password would travel unencrypted. */
    static boolean isInsecure(String url) {
        try {
            java.net.URI uri = java.net.URI.create(url);
            String host = uri.getHost();
            return "http".equals(uri.getScheme()) && host != null && !host.equals("127.0.0.1") && !host.equals("localhost") && !host.equals("[::1]");
        } catch (IllegalArgumentException e) {
            return false;
        }
    }

    public static void main(String[] args) {
        SwingUtilities.invokeLater(() -> {
            try {
                UIManager.setLookAndFeel(UIManager.getCrossPlatformLookAndFeelClassName());   // Metal: the same on every OS
            } catch (Exception ignored) {
                // fall back to the default look
            }
            Theme.install();
            new LoginFrame(new ApiClient(serverUrl()), serverUrl()).setVisible(true);
        });
    }
}
