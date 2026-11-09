# Module Scope: Expense Tracking

## Purpose
This module allows users to record and manage their spending across different categories.

## Business value
Spending data is the foundation of all personal finance decision-making. If expenses are not tracked accurately, budgeting, savings, and investment guidance become unreliable.

## Included features
- Add a new expense with amount, title, date, and category
- Update or delete existing expenses
- Categorize expenses by type
- View spending totals by category
- Review monthly expense summaries
- Import expenses from bank statements with duplicate checking and explicit duplicate handling

## Statement import duplicates
The bulk-approve request accepts `duplicate_mode`:
- Omit it or use `"skip"` to retain the existing behavior: matching expenses are skipped.
- Use `"check"` to check for duplicates before saving. If any are found, the API returns `409` with `detail.code` set to `"duplicate_expenses"`, the duplicate count, and the matching transaction row indices. No expenses are saved in that response.
- After a `"check"` response, the frontend can ask the user whether to import duplicates. Retry with `"allow"` to save all approved transactions, marking duplicate imports in the expense note, or `"skip"` to use the existing skip behavior.

If `"check"` finds no duplicates, the approved transactions are saved normally.

## Categories supported
- food
- transport
- housing
- health
- entertainment
- shopping
- education
- other

## Why it matters for the client demo
This is the core transaction layer. It demonstrates that the application is designed to understand actual user behavior and financial patterns.
