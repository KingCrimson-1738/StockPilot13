package com.stockpilot;

import javax.swing.SwingWorker;
import java.util.concurrent.Callable;
import java.util.function.Consumer;

/**
 * Runs a request on a background thread so the window never freezes, then hands the result back to the
 * Swing (event) thread. Swing components may only be touched on that thread.
 */
public final class Async {
    private Async() {}

    public static <T> void run(Callable<T> work, Consumer<T> onDone, Consumer<ApiException> onError) {
        new SwingWorker<T, Void>() {
            @Override protected T doInBackground() throws Exception {
                return work.call();                       // background thread: the HTTP request
            }

            @Override protected void done() {             // Swing thread again
                try {
                    onDone.accept(get());
                } catch (java.util.concurrent.ExecutionException e) {
                    Throwable cause = e.getCause();
                    onError.accept(cause instanceof ApiException api ? api
                            : new ApiException("Something unexpected went wrong.", 0));
                } catch (InterruptedException e) {
                    Thread.currentThread().interrupt();
                }
            }
        }.execute();
    }
}
