# Optional Google and Polycam adapters

`integrations.py` uses documented official HTTP APIs. No account has been connected in this session and no external events/captures were modified.

## Google Calendar

Set server-only `GOOGLE_ACCESS_TOKEN`, or `GOOGLE_REFRESH_TOKEN`, `GOOGLE_CLIENT_ID`, and `GOOGLE_CLIENT_SECRET` with calendar.events authorization. `GOOGLE_CALENDAR_ID` defaults to primary. Tokens are never returned to the browser or included in logs. Obtaining authorization remains a user/account setup step.

The adapter creates reminders at 09:00 three, two and one day before expiry, and a daily overdue series until verified cancellation. Stable deterministic event IDs make retries update an existing event instead of generating duplicates. Verified cancellation removes the four generated event series. Transient 429/5xx errors retry with bounded backoff; 401 can refresh an existing refresh token. Failure remains an error, not a sync success.

Google Calendar has no native priority-number field matching the requested Priority #1; urgency is represented in the title, red color and private metadata. Google Tasks also does not expose a native priority field in its documented task schema. ICS export does carry PRIORITY:1, though a calendar client may ignore it. Do not claim top-tier priority behavior that the receiving service does not implement.

Official references: [Calendar event creation](https://developers.google.com/workspace/calendar/api/v3/reference/events/insert), [OAuth refresh flow](https://developers.google.com/identity/protocols/oauth2/web-server), [Tasks schema](https://developers.google.com/tasks/reference/rest/v1/tasks).

## Google Tasks

Use server-only Google credentials authorized for `https://www.googleapis.com/auth/tasks`. Set `GOOGLE_TASK_LIST_ID` to the intended list, or use the default `@default`. The credentials-configured flag does not prove that the token has the required scope. No account authorization or real task creation has been performed.

**Sync Google Tasks** creates date-only tasks on the three buffer dates and the renewal date. Urgency appears in the title; no priority-number or recurrence field is sent. Task due dates cannot carry scheduled times through this API. These tasks do not supply Haven's persistent notification loop.

A stable marker in each task's notes identifies the trial and reminder offset. Sync lists all pages, including completed/hidden tasks, then patches matching server IDs. Pending cancellation leaves tasks actionable. After entering a verified confirmation in Haven, sync again to mark existing generated tasks completed; it does not create completed tasks unnecessarily. Editing or removing the marker can cause the next sync to create a new task.

Creation requests do not automatically retry uncertain 429/5xx/network outcomes. Retry sync manually: it lists existing task markers first to reconcile a task that may have been created before the response was lost. Updates use bounded retry and 401 refresh handling. Calendar and Tasks remain separate sync actions; successful completion of one does not prove the other succeeded.

Official references: [Task schema and date-only due field](https://developers.google.com/workspace/tasks/reference/rest/v1/tasks), [Task insertion](https://developers.google.com/workspace/tasks/reference/rest/v1/tasks/insert).

## Polycam

Set server-only `POLYCAM_API_TOKEN` after Enterprise Content API access is enabled. The adapter lists captures and retrieves expiring artifact download links. It does not mint tokens, scrape browser credentials, purchase an upgrade, or fabricate capture geometry. Local GLB/GLTF/OBJ import works without this API.

Official references: [Polycam Content API](https://poly.cam/docs/api), [Exporting captures](https://learn.poly.cam/hc/en-us/articles/29647691255316-How-to-Export-Polycam-Captures).

## Delivery limits

Adapters and mocked behavior tests are not account-level integration verification. Account configuration, real sync and token-expiry tests remain outstanding. Remote intrusion/care push requires its own authenticated delivery service.

## Saved sync outcomes

Each explicit Calendar/Tasks request saves a pending attempt before external calls, then records confirmed results or an error. Outcomes are in a separate SQLite table so a stale browser settings save cannot erase them. The trial page displays the last attempt per provider and its timestamp. A change to trial dates or cancellation state flags the earlier attempt for another sync. Pending after interruption means confirmation is absent; it does not prove failure or successful creation. No background retry is claimed. Late responses cannot replace a newer attempt.
