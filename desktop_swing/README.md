# StockPilot: Java Swing companion client

A smaller second front end for the SAME backend (it does not touch the database; it only calls the REST API).
It does: log in / log out, switch business, dashboard, search/filter products, **add and edit products** (owners),
**Stock in / Stock out**, supplier list, stock history, and basic reports (restock list, stock value by category).
Not included (use the main Tkinter app): registering, creating businesses, editing suppliers/categories, stock
adjustments, charts and CSV export.

## Requirements
Java 17 or newer (built and tested with Java 21) and Maven. The only library is **Gson** (JSON <-> Java objects);
HTTP uses Java's built-in `java.net.http.HttpClient`.

## Run it
```
cd desktop_swing
mvn package
java -jar target/stockpilot-swing-1.0-all.jar
```
The backend address comes from the `STOCKPILOT_API_URL` environment variable (default `http://127.0.0.1:8000`):
```
set STOCKPILOT_API_URL=https://your-app.vercel.app        (Windows)
export STOCKPILOT_API_URL=https://your-app.vercel.app     (Mac/Linux)
```
Without Maven you can compile by hand: download `gson-2.13.1.jar`, then
`javac -d out -cp gson-2.13.1.jar src/main/java/com/stockpilot/*.java` and
`java -cp out:gson-2.13.1.jar com.stockpilot.Main` (use `;` instead of `:` on Windows).

## How it is organised (src/main/java/com/stockpilot)
| File | Job |
|---|---|
| `Main` | start-up, reads the server address |
| `ApiClient` | the ONLY class that talks HTTP; sends the JWT; turns errors into `ApiException` |
| `Models` | Java records that Gson fills from the JSON (snake_case -> camelCase) |
| `Async` | runs a request on a background thread (SwingWorker) and returns to the Swing thread |
| `LoginFrame`, `MainFrame` | login window; main window (header, business switcher, page buttons) |
| `DashboardPanel`, `ProductsPanel`, `SuppliersPanel`, `HistoryPanel`, `ReportsPanel` | the five pages (each implements `Refreshable`) |
| `StockDialog`, `ProductDialog` | the Stock in / Stock out pop-up; the Add / Edit product pop-up |
| `Theme`, `Banner`, `Format` | colours/fonts and styled components; message strip; text formatting |

## Viva points
- **Why a thread?** A network call can take seconds. On the Swing (event) thread it would freeze the window, so
  `Async.run` does the request in `SwingWorker.doInBackground` and updates the screen in `done()` (Swing is not thread-safe).
- **Same rules as Tkinter:** the client never decides who may see what. It sends the token; the server checks membership
  (non-members get 404) and refuses negative stock (409). The client only pre-checks to give faster messages.
- **Stale answers:** each page numbers its requests, so a slow old answer cannot overwrite a newer one or another business's data.
- **No secrets:** the app holds only the user's own JWT, in memory. Nothing is stored on disk.

## Tests (in src/test/java)
Plain Java programs, no framework. Start the backend, register `asha@example.com` / `ravi@example.com` (password
`password123`), create the businesses, then run `ApiSmokeTest` (API layer) and, under a display, `GuiTest` (clicks the real windows).
