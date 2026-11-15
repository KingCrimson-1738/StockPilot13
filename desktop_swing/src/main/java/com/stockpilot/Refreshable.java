package com.stockpilot;

/** A screen that reloads its data from the server when it is shown or the business changes. */
public interface Refreshable {
    void refresh();
}
