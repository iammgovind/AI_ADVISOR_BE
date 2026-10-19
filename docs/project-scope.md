# FI Backend – Project Scope

## 1. Executive summary

FI is a personal finance management backend designed to help an individual track expenses, manage budgets, plan savings goals, monitor investments, and receive AI-informed financial guidance. The system acts as the foundation for a finance dashboard or mobile app experience and focuses on practical, everyday personal finance workflows.

This project is not a generic accounting system. It is built around a real user problem: helping a person understand where money is going, whether they are within budget, whether savings goals are realistic, and how their investments are performing over time.

## 2. Business problem being solved

Most personal-finance tools are either:
- too complex for everyday users,
- too focused on transactions without planning, or
- disconnected from financial decision support.

FI addresses this by combining the following in one system:
- transaction tracking (expenses),
- budget control,
- goal planning,
- investment tracking,
- dashboard analytics,
- AI-driven financial recommendations.

## 3. Target users

Primary users:
- individuals managing household or personal finances,
- users who want better visibility into monthly spending,
- people tracking savings goals and investments,
- users who want an automated financial health overview.

Secondary users:
- financial advisors or product teams using the backend as the foundation for a smarter personal finance product.

## 4. Scope in plain business language

The product scope includes:
- creating and managing user accounts,
- logging expenses by category,
- setting monthly budgets by category,
- tracking savings goals and progress,
- monitoring investments and portfolio performance,
- creating a dashboard for monthly financial health,
- generating risk and savings recommendations,
- uploading financial documents and asking questions through AI-powered document search.

## 5. In-scope features

### 5.1 User and authentication
- registration and login with JWT authentication,
- refresh token flow,
- user profile and admin/user roles,
- secure access to personal financial data.

### 5.2 Expense management
- add, update, list, and delete personal expenses,
- categorize expenses such as food, transport, housing, health, shopping, education, entertainment, and other,
- view monthly and category-based expense summaries.

### 5.3 Budget management
- create category budgets by month and year,
- compare actual spending versus budget limits,
- calculate utilization and alert states.

### 5.4 Goal planning
- create financial goals with target amount and timeline,
- adjust saved amount against target,
- calculate progress, remaining amount, and monthly saving requirement.

### 5.5 Investments
- track investments by type,
- store buy price, current price, quantity, and status,
- calculate portfolio profit/loss and holdings summary.

### 5.6 Dashboard and analytics
- monthly overview of spending,
- budget alerts,
- spending trends,
- category-level breakdown,
- budget and expense comparison dashboard data.

### 5.7 Financial advisory logic
- risk scoring based on budget discipline, investment behavior, goal progress, and portfolio diversity,
- savings capacity analysis,
- monthly allocation recommendations,
- investment recommendations and financial health score.

### 5.8 AI and document support
- PDF document upload for financial or planning documents,
- retrieval-based Q&A over uploaded content,
- AI-powered financial insights using Gemini model integration.

## 6. Out of scope for this version

The current release does not include:
- multi-user family accounts with shared household wallets,
- bank statement import or real banking API integration,
- real stock market live trading execution,
- payroll or tax filing workflows,
- subscriptions, invoicing, or accounting journal entries,
- advanced credit scoring or loan underwriting,
- multi-tenant SaaS platform features.

## 7. Functional architecture

The project is structured as a FastAPI backend with modular business domains:
- API layer for user interaction,
- service layer for business intelligence and recommendation logic,
- model layer for financial entities,
- schema layer for request and response validation,
- database layer with SQLAlchemy and PostgreSQL/MySQL-compatible support.

## 8. Core business value

This backend delivers value in four areas:
1. Visibility – users can see where money is going.
2. Control – budgets and monthly limits keep spending in check.
3. Planning – goals and savings strategies guide future actions.
4. Intelligence – AI and scoring help users make decisions.

## 9. Client demo narrative

A concise story for client presentation:

“FI is a personal finance intelligence platform backend that helps users understand their spending, control budgets, stay on track with goals, and make better investment decisions. It combines traditional financial tracking with AI-driven analysis so users can move from raw data to meaningful financial guidance.”

## 10. Success criteria

This project is successful when users can:
- record expenses quickly,
- monitor budget usage in real time,
- know if a savings goal is achievable,
- track portfolio performance,
- receive actionable financial advice,
- access a dashboard that turns data into decisions.

## 11. Summary

FI is a focused personal finance backend with practical financial planning capabilities. It is positioned as a financial wellness and decision-support platform rather than a generic CRUD app, and that is the main value proposition for the client demo.
