package com.stockpilot;

/** A failed request, with a message that is safe to show to the user. */
public class ApiException extends Exception {
    private final int status;   // HTTP status, or 0 if the server was never reached

    public ApiException(String message, int status) {
        super(message);
        this.status = status;
    }

    public int status() { return status; }
}
