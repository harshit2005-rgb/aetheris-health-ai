# 11 — Notifications

**Owner:** TBD
**Phase:** MVP (in-app + email); SMS in v2.1
**Status:** Approved

---

## 1. Purpose

Get the right message to the right person through the right channel at the right time. Own the templates, delivery, preferences, and history.

## 2. Scope

### In Scope

- In-app notification center
- Email notifications
- User notification preferences
- Standard event → notification mapping
- Template management (v2.1)
- SMS (v2.1)
- Retry & delivery logging

### Out of Scope

- WhatsApp → future
- Push notifications (mobile app) → future
- Rich transactional in-app content (attachments, threads) → future

## 3. Personas & Permissions

| Role | Can do |
|---|---|
| Any authenticated | Read own notifications, update own preferences |
| Hospital Admin | Manage hospital-wide templates (v2.1), view delivery logs |

## 4. Business Rules

1. Every notification has: recipient, kind, title, body, optional link.
2. Delivery channels are per-recipient preferences × kind's default channels.
3. Email failures retry with exponential backoff up to 5 attempts.
4. In-app notifications never fail delivery; they're persisted directly.
5. No notification body includes PII beyond what the recipient is already authorized to see.
6. Bulk notifications (broadcasts) queue individually to allow per-recipient failure handling.

## 5. Workflow

- Service emits a domain event (via a dispatcher).
- `NotificationService` receives event → resolves recipient(s) → looks up template + preferences → enqueues per-channel deliveries to background worker.
- Worker sends via SMTP / SMS provider; records delivery status.
- In-app notification insertion is inline (fast).

## 6. Functional Requirements

- FR-1: In-app notification list + unread count.
- FR-2: Email delivery via SMTP.
- FR-3: User preferences per kind.
- FR-4: Templates with variable interpolation.
- FR-5: Delivery log with retry state.
- FR-6: Broadcast to a role or a hospital (admin action).

## 7. Non-Functional Requirements

- In-app notification insert p95 < 50ms.
- Email queue drain p95 < 5s from enqueue.
- Zero silent drops — every notification either delivered or explicitly failed with reason.

## 8. Database Design

Table `notifications` in `05-DATABASE_DESIGN.md`. Additional:

```
notification_preferences
  user_id UUID PK
  preferences JSONB NOT NULL DEFAULT '{}'
  updated_at TIMESTAMPTZ

notification_deliveries
  id UUID PK
  notification_id UUID FK notifications(id)
  channel ENUM(in_app/email/sms)
  status ENUM(queued/sent/failed/delivered)
  attempts INT NOT NULL DEFAULT 0
  last_error TEXT
  sent_at TIMESTAMPTZ
  delivered_at TIMESTAMPTZ
  + audit

notification_templates
  id UUID PK
  hospital_id UUID NULLABLE  -- NULL for platform default
  kind VARCHAR(50) NOT NULL
  channel ENUM
  subject VARCHAR(200)     -- email only
  body_template TEXT NOT NULL
  variables JSONB
  version INT NOT NULL DEFAULT 1
  is_active BOOLEAN
```

## 9. API Design

```
GET  /api/v1/notifications                 # my notifications
POST /api/v1/notifications/{id}/read
POST /api/v1/notifications/read-all
GET  /api/v1/notifications/preferences
PUT  /api/v1/notifications/preferences
POST /api/v1/notifications/broadcast       # admin
GET  /api/v1/notifications/templates       # admin (v2.1)
POST /api/v1/notifications/templates       # admin (v2.1)
PATCH /api/v1/notifications/templates/{id} # admin (v2.1)
GET  /api/v1/notifications/deliveries      # admin (v2.1)
```

## 10. Permissions

- `notification.read.own`
- `notification.preference.update.own`
- `notification.broadcast`
- `notification.template.read/create/update`
- `notification.delivery.read`

## 11. Validation Rules

- Template body ≤ 5000 chars.
- Variables schema declared per template; interpolation fails safely with a placeholder.

## 12. UI Requirements

- Bell icon with unread count.
- Notification center dropdown with filter and mark-all-read.
- Preferences page grouped by category.
- Admin: template editor with preview.

## 13. AI Integration Points

- **Prompt (v2.1):** `notification.reminder_text` — generate appointment reminder in patient's preferred language.
- Safety: PII in inputs limited to what the patient already knows about their appointment.

## 14. Edge Cases

- Recipient without email address → skip email channel silently, log.
- Broadcast during outage → queue persists, drains on recovery.
- Preferences set to "none" for a kind → still delivered in-app for critical types (auth, security) — critical kinds documented.

## 15. Cross-Module Dependencies

- Consumed by: every module that emits events.
- Depends on: User Management, Email provider (SMTP), SMS provider (v2.1).

## 16. Testing Requirements

- Unit: template interpolation, preference resolution.
- Repository: unread count.
- API: full endpoint set + permission gates.
- Integration: emit event → in-app + email delivered.

## 17. Acceptance Criteria

- AC-1: A user receives an in-app notification within 1 second of the source event.
- AC-2: Email is delivered within 30 seconds of enqueue under normal load.
- AC-3: Preferences honor across channels.
- AC-4: Critical notifications override preferences.

## 18. Rollout Plan

- MVP: in-app + email.
- v2.1: SMS via Twilio (or MSG91 for India pilots).

## 19. Future Scope

- WhatsApp Business API (v3)
- Push notifications (v3, mobile)
- Digest mode (v2.2)

## 20. Open Questions

- Which SMS provider for India first pilot? Twilio, MSG91, or Fast2SMS? Cost/reliability decision by v2.1 sprint.
