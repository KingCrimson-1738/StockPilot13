package com.stockpilot;

import javax.swing.*;
import java.awt.*;
import java.util.LinkedHashMap;
import java.util.Map;

/** The main window: a header (business switcher, role, log out), a row of page buttons and the page itself. */
public class MainFrame extends JFrame {
    private final ApiClient api;
    private final Models.User user;
    private final Models.Business[] businesses;
    private Models.Business business;
    private final CardLayout cards = new CardLayout();
    private final JPanel pages = new JPanel(cards);
    private final Map<String, Refreshable> screens = new LinkedHashMap<>();
    private final Map<String, JButton> navButtons = new LinkedHashMap<>();
    private final JComboBox<Models.Business> businessMenu;
    private final JLabel roleBadge = new JLabel();
    private String currentPage = "Dashboard";

    public MainFrame(ApiClient api, Models.User user, Models.Business[] businesses) {
        super("StockPilot");
        this.api = api;
        this.user = user;
        this.businesses = businesses;
        this.business = businesses[0];

        businessMenu = Theme.combo(businesses);
        businessMenu.setName("businessMenu");
        businessMenu.addActionListener(e -> switchBusiness((Models.Business) businessMenu.getSelectedItem()));

        JPanel root = new JPanel(new BorderLayout());
        root.setBackground(Theme.BG);
        root.add(buildHeader(), BorderLayout.NORTH);

        pages.setOpaque(false);
        pages.setBorder(BorderFactory.createEmptyBorder(8, 28, 24, 28));
        addPage("Dashboard", new DashboardPanel(this));
        addPage("Products", new ProductsPanel(this));
        addPage("Suppliers", new SuppliersPanel(this));
        addPage("History", new HistoryPanel(this));
        addPage("Reports", new ReportsPanel(this));
        root.add(pages, BorderLayout.CENTER);
        setContentPane(root);

        setDefaultCloseOperation(EXIT_ON_CLOSE);
        setSize(1100, 720);
        setMinimumSize(new Dimension(900, 600));
        setLocationRelativeTo(null);
        updateRoleBadge();
        showPage("Dashboard");
    }

    private JComponent buildHeader() {
        JPanel header = new JPanel(new BorderLayout());
        header.setBackground(Theme.SIDEBAR);
        header.setBorder(BorderFactory.createEmptyBorder(14, 28, 14, 28));

        JPanel left = new JPanel(new FlowLayout(FlowLayout.LEFT, 6, 0));
        left.setOpaque(false);
        left.add(Theme.label("StockPilot", 20, Font.BOLD, Theme.TEXT));
        left.add(Box.createHorizontalStrut(24));
        for (String name : new String[]{"Dashboard", "Products", "Suppliers", "History", "Reports"}) {
            JButton button = Theme.button(name, false);
            button.setName("nav" + name);
            button.addActionListener(e -> showPage(name));
            navButtons.put(name, button);
            left.add(button);
        }
        header.add(left, BorderLayout.WEST);

        roleBadge.setFont(Theme.font(11, Font.BOLD));
        JPanel right = new JPanel(new FlowLayout(FlowLayout.RIGHT, 10, 0));
        right.setOpaque(false);
        right.add(roleBadge);
        right.add(businessMenu);
        right.add(Theme.label(user.fullName(), 13, Font.PLAIN, Theme.MUTED));
        JButton logout = Theme.button("Log out", false);
        logout.setName("logout");
        logout.addActionListener(e -> logOut());
        right.add(logout);
        header.add(right, BorderLayout.EAST);
        return header;
    }

    private void addPage(String name, JPanel panel) {
        pages.add(panel, name);
        screens.put(name, (Refreshable) panel);
    }

    private void updateRoleBadge() {
        roleBadge.setText(" " + (business.isOwner() ? "OWNER" : "STAFF") + " ");
        roleBadge.setForeground(business.isOwner() ? Theme.PRIMARY : Theme.WARNING);
    }

    public void showPage(String name) {
        currentPage = name;
        navButtons.forEach((key, button) -> {
            button.setBackground(key.equals(name) ? Theme.PRIMARY : Theme.CARD);
            button.setBorder(BorderFactory.createCompoundBorder(BorderFactory.createLineBorder(key.equals(name) ? Theme.PRIMARY : Theme.BORDER),
                    BorderFactory.createEmptyBorder(9, 18, 9, 18)));
        });
        cards.show(pages, name);
        screens.get(name).refresh();
    }

    private void switchBusiness(Models.Business chosen) {
        if (chosen == null || chosen.id() == business.id()) return;
        business = chosen;   // every later request uses this id; the server re-checks that we belong to it
        updateRoleBadge();
        screens.get(currentPage).refresh();
    }

    /** An error from any screen. If the login has expired we go back to the login window. */
    public void report(ApiException error, Banner banner) {
        if (error.status() == 401) {
            LoginFrame login = new LoginFrame(new ApiClient(Main.serverUrl()), Main.serverUrl());
            login.setVisible(true);
            dispose();
            JOptionPane.showMessageDialog(login, "Your session has expired. Please log in again.");
            return;
        }
        banner.error(error.getMessage());
    }

    private void logOut() {
        new LoginFrame(new ApiClient(Main.serverUrl()), Main.serverUrl()).setVisible(true);   // a new client: the old token is dropped
        dispose();
    }

    public ApiClient api() { return api; }

    public Models.Business business() { return business; }

    public Models.Business[] businesses() { return businesses; }
}
