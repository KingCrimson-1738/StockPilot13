# Testing: the 20 scenarios from the project brief

Run everything with: backend `python -m pytest -q` (125 tests); UI scripts in `tools/ui_tests/`; Java tests in
`desktop_swing/src/test/java`; cross-client check `tools/check_consistency.py`.

| # | Scenario | Where it is tested |
|---|---|---|
| 1 | Register a new user | `test_auth.py::test_register_returns_token_and_no_password_data`; UI: `drive_ui.py` |
| 2 | Log in | `test_auth.py::test_login_success`; UI: `drive_ui.py`; Swing: `GuiTest` |
| 3 | Create a business | `test_businesses.py::test_create_business_makes_creator_the_owner`; UI: `drive_ui.py` |
| 4 | Second business, same account | `test_businesses.py::test_one_account_can_have_multiple_businesses` |
| 5 | Switch between businesses | `drive_ui.py` (Tkinter) and `GuiTest` (Swing: the other business shows its own empty list) |
| 6 | Add products | `test_products.py` (create, opening stock, duplicate SKU); UI: `drive_products.py`; Swing: `GuiTest` |
| 7 | Edit products | `test_products.py::test_update_changes_fields_but_never_the_quantity`; UI and Swing as above |
| 8 | Delete or archive products | `test_products.py::test_product_with_history_is_archived_not_deleted`, `..._without_history_is_really_deleted`, `test_restore_...` |
| 9 | Add suppliers | `test_suppliers.py`; UI: `drive_stock.py` |
| 10 | Custom categories | `test_categories.py`; UI: `drive_products.py` |
| 11 | Stock in | `test_stock.py::test_stock_in_increases_quantity_and_records_a_transaction`; Swing: `GuiTest` |
| 12 | Stock out | `test_stock.py::test_stock_out_decreases_quantity`; Swing: `GuiTest` |
| 13 | Remove more than available | `test_stock.py::test_cannot_remove_more_than_available_and_nothing_is_recorded`; `test_simultaneous_stock_outs_never_oversell`; shown on screen in `drive_stock.py` and `GuiTest` |
| 14 | Invalid transactions rejected | `test_stock.py::test_quantity_must_be_a_positive_whole_number`, `..._unknown_product_and_archived_product_are_rejected`, `test_a_failure_in_the_middle_saves_nothing`; `test_constraints.py` (database CHECK) |
| 15 | Low-stock alerts | `test_reports.py::test_low_stock_lists_low_and_out_with_suggested_order`; `test_dashboard.py`; UI: `drive_reports.py` |
| 16 | Dashboard calculations | `test_dashboard.py::test_numbers_are_calculated_from_real_rows`; UI: `drive_ui.py` (numbers on screen) |
| 17 | CSV exports | `test_reports.py::test_products_csv`, `test_csv_cells_cannot_run_as_formulas`, `test_transactions_csv_...`, `test_low_stock_csv`; UI: `drive_reports.py` |
| 18 | One user cannot access another's business | `test_businesses.py::test_user_cannot_read_or_edit_another_users_business`; `..._isolated...` tests in every file; `test_hardening.py` (every route checks membership) |
| 19 | Tkinter and Swing show consistent data | `tools/check_consistency.py`: products created through the Tkinter screens (`drive_products.py`) are listed by Swing's own API client and match the server |
| 20 | Data persists after restart | `tools/check_consistency.py --restart ...`: backend restarted, all data identical; `test_deployment.py::test_running_migrations_again_keeps_existing_data` |

## Cross-client check (scenarios 19 and 20)
```
python tools/ui_tests/drive_products.py        # (backend running, empty dev database) creates products through the Tkinter UI
cd desktop_swing && javac -d out -cp gson-2.13.1.jar src/main/java/com/stockpilot/*.java src/test/java/com/stockpilot/*.java
python tools/check_consistency.py asha@example.com password123 gson-2.13.1.jar out --restart "bash restart_backend.sh"
```
`restart_backend.sh` is whatever command stops and starts your backend. Without `--restart` only scenario 19 is checked.

## Not tested
Real Vercel/Neon deployment and `mvn package` (no network access from the development sandbox): use
`tools/check_deployment.py` and `docs/DEPLOYMENT.md`.
