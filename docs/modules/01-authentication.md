# 01 — Authentication

**Owner:** TBD
**Phase:** MVP
**Status:** Approved

---

## 1. Purpose

Verifies the identity of every user before they interact with the system. Establishes a secure session that downstream modules can trust. Foundational — every other module depends on it.

## 2. Scope

### In Scope

- Email + password login
- JWT access + refresh token lifecycle
- Password reset via email
- Forced password change (first login, admin-initiated)
- Account lockout after failed attempts
- Session revocation (logout, logout-all)
- MFA scaffolding (TOTP, MVP-optional, v2.1-mandatory for admins)

### Out of Scope

- Authorization / permission checks → owned by User Management (`02-user-management.md`)
- User profile CRUD → owned by User Management
- SSO / OAuth → future
- Biometric authentication → future (mobile app)

## 3. Personas & Permissions

| Role | Can do |
|---|---|
| Any authenticated user | Log out, refresh token, change own password, enable own MFA |
| Hospital Admin | Reset user password (triggers forced change), unlock account, revoke user sessions |
| Super Admin | Same as Hospital Admin, cross-hospital |

Anonymous:
- Log in
- Request password reset
- Complete password reset with a valid token

## 4. Business Rules

1. Passwords are hashed with Argon2id; never stored in plaintext.
2. Passwords must be at least 12 characters, contain uppercase + lowercase + digit + symbol.
3. Users cannot reuse any of their previous 5 passwords.
4. After 5 failed login attempts in 15 minutes, account is locked for 30 minutes.
5. Access tokens expire in 15 minutes.
6. Refresh tokens expire in 7 days and rotate on every use.
7. If a refresh token is reused (already-consumed value presented), all sessions for that user are invalidated.
8. Password reset tokens are single-use and expire in 30 minutes.
9. On password change (voluntary or forced), all existing refresh tokens are revoked except the current session.
10. On role change, all refresh tokens are revoked (forces re-login with new claims).
11. Login responses do not distinguish "unknown email" from "wrong password" — both return the same generic message.
12. MFA (when enabled) is required after password verification and before the access token is issued.

## 5. Workflow

### 5.1 Login (happy path)

1. User submits `POST /auth/login` with email + password.
2. Rate limiter checks the IP + email combination.
3. Service verifies credentials via user repository.
4. If MFA is enabled, service returns a partial token requiring TOTP verification.
5. Otherwise, service issues access + refresh tokens.
6. Audit log entry: `auth.login`.
7. Response includes access token, refresh token cookie/body, and user profile.

### 5.2 Login (failure)

- Invalid credentials → increment failed attempts, return 401 `AUTHENTICATION_REQUIRED`.
- Account locked → return 403 `ACCOUNT_LOCKED` with unlock time.
- Account suspended → 403 `ACCOUNT_SUSPENDED`.

### 5.3 Refresh

1. `POST /auth/refresh` with refresh token in body.
2. Service looks up token in Redis.
3. If found: issue new access + refresh, invalidate old refresh (rotation).
4. If not found (already used or expired): audit `auth.refresh_reuse_detected`, revoke all sessions for user, return 401.

### 5.4 Logout

1. `POST /auth/logout` with refresh token.
2. Service invalidates the refresh token.
3. Client discards access token.
4. Audit: `auth.logout`.

### 5.5 Logout All

1. `POST /auth/logout-all`.
2. Service invalidates all refresh tokens for the user.
3. Audit: `auth.logout_all`.

### 5.6 Password Reset — Request

1. `POST /auth/password/forgot` with email.
2. Regardless of whether email exists, respond with generic success message.
3. If email exists: generate single-use token, store hash + expiry in DB, email token link.
4. Audit: `auth.password_reset_requested`.

### 5.7 Password Reset — Complete

1. `POST /auth/password/reset` with token + new password.
2. Service validates token, hashes new password, updates user, invalidates token, revokes all refresh tokens.
3. Audit: `auth.password_reset_completed`.
4. Notification: email + in-app "Password changed".

### 5.8 Forced Password Change

- User has `password_changed_at IS NULL` or `password_change_required = true` on the user record.
- After login, access token includes a `force_password_change` claim.
- All non-auth endpoints return 403 until password is changed.

## 6. Functional Requirements

- FR-1: The system shall authenticate users via email + password.
- FR-2: The system shall issue short-lived access tokens and rotating refresh tokens.
- FR-3: The system shall support password reset via email.
- FR-4: The system shall lock accounts after 5 failed attempts.
- FR-5: The system shall detect refresh token reuse and invalidate sessions.
- FR-6: The system shall support forced password change on first login and admin trigger.
- FR-7: The system shall support optional TOTP-based MFA.

## 7. Non-Functional Requirements

- Login p95 < 300ms (excluding network).
- Refresh p95 < 100ms.
- Zero plaintext passwords in any log, database, or backup.
- 100% of auth events audited.
- Login endpoint capped at 10 requests per minute per IP.

## 8. Database Design

### 8.1 Tables

- `users` (already in `05-DATABASE_DESIGN.md`)
- `password_reset_tokens`

```
password_reset_tokens
  id              UUID PK
  user_id         UUID FK users(id) NOT NULL
  token_hash      VARCHAR(255) NOT NULL          -- SHA-256 of the token
  expires_at      TIMESTAMPTZ NOT NULL
  used_at         TIMESTAMPTZ NULL
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
  Index: (user_id, used_at)
```

Refresh tokens live in **Redis**, not PostgreSQL:

- Key: `refresh:{token_uuid}` → `{user_id, hospital_id, family_id, expires_at}`
- Family id: identifies a session lineage; on reuse detection, all keys with the family id are purged.

### 8.2 User fields relevant to auth

Already in the `users` table: `password_hash`, `failed_login_attempts`, `locked_until`, `mfa_enabled`, `mfa_secret`, `password_changed_at`.

## 9. API Design

```
POST   /api/v1/auth/login
POST   /api/v1/auth/mfa/verify
POST   /api/v1/auth/refresh
POST   /api/v1/auth/logout
POST   /api/v1/auth/logout-all
POST   /api/v1/auth/password/forgot
POST   /api/v1/auth/password/reset
POST   /api/v1/auth/password/change     # authenticated
POST   /api/v1/auth/mfa/enroll          # authenticated
POST   /api/v1/auth/mfa/confirm         # authenticated
POST   /api/v1/auth/mfa/disable         # authenticated
```

Sample:

**POST /auth/login**

Request:
```json
{ "email": "doctor@hospital.com", "password": "..." }
```

Success 200 (no MFA):
```json
{
  "success": true,
  "message": "Logged in.",
  "data": {
    "access_token": "eyJ...",
    "refresh_token": "opaque-uuid",
    "expires_in": 900,
    "user": { "id": "...", "email": "...", "roles": ["doctor"] }
  }
}
```

Success 200 (MFA required):
```json
{
  "success": true,
  "message": "MFA required.",
  "data": {
    "mfa_ticket": "opaque-uuid",
    "expires_in": 300
  }
}
```

Failure 401:
```json
{
  "success": false,
  "message": "Invalid credentials.",
  "errors": [],
  "error_code": "AUTHENTICATION_REQUIRED"
}
```

## 10. Permissions

None — anonymous endpoints. Admin actions on other users' auth belong to User Management.

## 11. Validation Rules

- Email: valid RFC 5322 address, lowercased before storage / comparison.
- Password: ≥ 12 chars, uppercase + lowercase + digit + symbol.
- MFA code: 6 digits, integer.
- Password reset token: opaque, base64url, 32 bytes of entropy.

## 12. UI Requirements

- Login page (email, password, "forgot password?" link).
- MFA prompt page (6-digit TOTP entry).
- Forgot password page (email entry).
- Reset password page (token from URL, new + confirm password, strength indicator).
- Force-change-password page (interstitial after login when required).
- Session expired banner (auto-refresh attempted; on failure, redirect to login preserving return URL).

Shadcn components: `Card`, `Form`, `Input`, `Button`, `Alert`.

## 13. AI Integration Points

None. Authentication does not use AI. AI never bypasses authentication.

## 14. Edge Cases

- User rotates password while another device holds an active access token → access token remains valid until expiry (accepted for MVP); refresh will fail; document behavior.
- Clock skew across servers → JWT `exp` includes a 60-second leeway.
- Race condition on refresh: two simultaneous refresh calls with the same token → one wins, the other is treated as reuse; families are still fresh so only that one session dies (not the whole user).
- Password reset requested for suspended account → generic success but never actually emailed.
- User email changes → not permitted in MVP; requires Hospital Admin flow with re-verification.
- Time zones: token `exp` is UTC epoch.

## 15. Cross-Module Dependencies

- Depends on: User Management for user existence, role, status.
- Depends on: Notification service for reset emails and MFA setup confirmation.
- Provides to: every other module — the authenticated user context.

## 16. Testing Requirements

- Unit: password hashing, token generation, MFA verification, refresh reuse detection.
- Repository: password reset token lifecycle.
- API: happy path + all listed failure modes for every endpoint.
- Integration: full login → refresh → logout cycle; refresh reuse detection invalidates family.

## 17. Acceptance Criteria

- AC-1: A user can log in with correct credentials and receive access + refresh tokens.
- AC-2: A user cannot log in with wrong credentials; the error does not reveal whether the email exists.
- AC-3: After 5 failed attempts, the account locks for 30 minutes.
- AC-4: A refresh token used twice invalidates all sessions in its family.
- AC-5: A password reset token works once and expires within 30 minutes.
- AC-6: Enabling MFA requires a successful TOTP verification before saving.
- AC-7: Every auth event appears in the audit log with actor + IP + user agent.

## 18. Rollout Plan

- No feature flag — auth is foundational; ships with the first release.
- No migration from v1 — v1 didn't have persistent users at MVP quality; all pilot hospitals start fresh.

## 19. Future Scope

- SSO via SAML / OIDC (Enterprise phase)
- WebAuthn / passkeys
- Risk-based authentication (unusual location / device)
- Session inspection dashboard for the user themselves

## 20. Open Questions

- None currently open. Any deviation from this spec requires a PR against this file.
