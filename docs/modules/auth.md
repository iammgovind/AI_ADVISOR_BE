# Module Scope: Authentication and User Access

## Purpose
This module handles how a user signs up, logs in, manages tokens, and accesses their personal finance data securely.

## Business value
Without secure access, financial data could not be trusted or managed privately. This module builds trust and ensures the user sees only their own data.

## Included features
- User registration
- Login with email and password
- JWT access token generation
- Refresh token support
- Logout flow
- Role-based user access (user/admin)
- Active/inactive user state checks

## Typical user journey
1. A new user creates an account.
2. The system stores a hashed password.
3. The user logs in and receives tokens.
4. The token is used to access private financial dashboard APIs.

## Why it matters for the client demo
This is the trust layer. It shows the project is a real product with secure personal data handling, not just a demo API.
