package com.stockpilot;
public class UrlTest {
    static void ok(boolean c, String m) { System.out.println((c ? "PASS  " : "FAIL  ") + m); if (!c) System.exit(1); }
    public static void main(String[] a) {
        ok(Main.normalise(null).equals("http://127.0.0.1:8000"), "nothing set -> local server");
        ok(Main.normalise(" my-app.vercel.app/ ").equals("https://my-app.vercel.app"), "scheme added, slash removed");
        ok(Main.normalise("http://10.0.0.5:8000//").equals("http://10.0.0.5:8000"), "explicit http kept");
        ok(Main.isInsecure("http://192.168.1.5:8000") && !Main.isInsecure("http://localhost:8000") && !Main.isInsecure("https://x.vercel.app") && !Main.isInsecure("http://127.0.0.1:8000"), "insecure detection");
    }
}
