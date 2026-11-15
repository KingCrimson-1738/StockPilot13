package com.stockpilot;

import javax.swing.event.DocumentEvent;
import javax.swing.event.DocumentListener;

/** One callback for every kind of text change (typing, deleting, pasting). */
public class SimpleDocumentListener implements DocumentListener {
    private final Runnable onChange;

    public SimpleDocumentListener(Runnable onChange) { this.onChange = onChange; }

    @Override public void insertUpdate(DocumentEvent e) { onChange.run(); }
    @Override public void removeUpdate(DocumentEvent e) { onChange.run(); }
    @Override public void changedUpdate(DocumentEvent e) { onChange.run(); }
}
