package com.stockpilot;

import java.time.OffsetDateTime;
import java.time.ZoneId;
import java.time.format.DateTimeFormatter;
import java.util.Locale;

/** Turns raw API values into text for the screen. */
public final class Format {
    private Format() {}

    private static final DateTimeFormatter WHEN = DateTimeFormatter.ofPattern("dd MMM HH:mm", Locale.ENGLISH);

    public static String money(double amount, String currency) {
        return String.format(Locale.ENGLISH, "%s %,.2f", currency, amount);
    }

    public static String number(int value) {
        return String.format(Locale.ENGLISH, "%,d", value);
    }

    /** '2026-11-15T12:30:00+00:00' -> '15 Nov 18:00' in this computer's time zone. */
    public static String when(String isoText) {
        return OffsetDateTime.parse(isoText).atZoneSameInstant(ZoneId.systemDefault()).format(WHEN);
    }

    public static String typeLabel(String type) {
        return switch (type) { case "in" -> "Stock in"; case "out" -> "Stock out"; default -> "Adjustment"; };
    }

    public static String signed(int value) {
        return value > 0 ? "+" + value : String.valueOf(value);
    }

    public static String statusLabel(String status) {
        return switch (status) { case "low" -> "Low"; case "out" -> "Out"; default -> "OK"; };
    }
}
