# CertVerify Audit Fixes: Engineering Learning Guide

This guide explains the engineering problems found in the CertVerify backend, the fixes applied, and the ideas behind those fixes. It is written to help you reason about similar systems, not just to list changed files.

## 1. Password reset links are credentials

### The problem
When `FIREBASE_WEB_API_KEY` was missing, the password reset endpoint called Firebase Admin to generate a reset link and returned that link in its JSON response. Anyone could call this endpoint with another person's email. A password reset link is a bearer credential: whoever has it can use it to change the account password.

### The fix

The fallback that generated and returned reset links was removed. If the Firebase email delivery configuration is missing, the endpoint returns `503 Service Unavailable`. When Firebase is configured, the endpoint asks Firebase to send the email and returns a generic response. The request also has a timeout.

### Engineering principle

Never return secrets, reset links, one-time codes, or other bearer credentials from an unauthenticated endpoint. Deliver them through the intended private channel. Keep responses generic so callers cannot probe whether an email address is registered.

**Code:** `app/services/auth_service.py`

## 2. Admin allowlists must prove control of the email address

### The problem

Admin access could be granted because an ID token contained an email on the `ADMIN_EMAILS` allowlist. Firebase can issue tokens for accounts whose email has not yet been verified. Merely creating an account with an allowlisted address therefore was not a strong enough proof that the user controlled that address.

### The fix

Email-based admin access now requires Firebase's `email_verified` token claim. Email values are normalized for case and whitespace before comparison. Explicit Firebase custom admin claims remain a separate way to authorize admins.

### Engineering principle

Authorization should rely on claims whose meaning has been established by a trusted identity provider. A string matching an email allowlist is not proof of mailbox ownership until verification has happened.

**Code:** `app/core/security.py`

## 3. Payment success must match the order the customer created

### The problem

The original implementation trusted a successful provider status without checking whether the provider's amount and currency matched the local order. A success notification for the wrong amount could activate a subscription. Malformed JSON could also turn into an unhandled server error.

### The fix

The service checks the provider's transaction reference, amount in kobo, and NGN currency against the stored transaction before settling it. The webhook validates the same order details after validating its signature. Invalid JSON or an unexpected payload shape is rejected. Provider responses are also parsed defensively.

Payment initiation and verification requests have timeouts. A definitive rejection from Squad is recorded as an initiation failure. A network timeout is left pending because the provider may have accepted the request even though the application did not receive the response.

### Engineering principle

Treat a payment callback as a notification to verify, not as a financial ledger entry. The local order is the expected value; the payment provider is the evidence. Compare both before granting value. Use integer minor currency units for payment comparisons to avoid floating point errors.

**Code:** `app/services/payment_service.py`, `app/api/v1/payments.py`

## 4. Payment fulfillment must be atomic and idempotent

### The problem

The old flow committed `transaction.status = "success"` and activated subscription credits in a later database operation. If the process stopped between those operations, later callbacks saw a successful transaction and skipped activation. The customer had paid, but the purchased credits were not delivered.

### The fix

Settlement now locks the payment row, applies the subscription change, marks the transaction successful, and sets `payment_effects_applied_at` in one database transaction. If any database operation fails, the transaction rolls back as a unit. A repeated callback sees the marker and does not grant the subscription again.

An Alembic migration adds the fulfillment marker. The existing `mark_transaction_success` entry point delegates to the same settlement operation so callers do not accidentally use the old partial transition.

### Engineering principle

For a business operation that must change multiple database records together, use one database transaction. For retries, make the operation idempotent: the same request should not grant the same purchased value twice.

### Important boundary

The subscription records and payment row are atomic because they share Postgres. External actions such as sending an email cannot be made atomic with a database commit; a durable outbox is the usual next step if email delivery must be guaranteed.

**Code:** `app/services/payment_service.py`, `app/models/transaction.py`

**Migration:** `migrations/versions/b7c8d9e0f1a2_payment_effects_marker.py`

## 5. API keys should not be stored as plaintext

### The problem

The database stored full B2B API keys. Anyone who obtained a database dump could immediately call the B2B API as every organization in that dump.

### The fix

New keys are returned once to the customer, then only their SHA-256 digest is stored. Authentication hashes the presented key and looks up that digest. The database keeps a short prefix and suffix so the user interface can show a masked identifier without recovering the secret. Key rotation updates the digest and its masked parts. Pending B2B payment references are updated in the same rotation transaction so a key rotation does not orphan a checkout.

An Alembic migration converts existing key values and pending payment references to digests. Existing clients can continue using their original plaintext key because the service hashes the presented value before lookup.

### Engineering principle

Store a verifier for a secret, not the secret itself. A cryptographic hash is suitable here because generated keys have high entropy; this differs from human passwords, which need a slow password-hashing algorithm such as Argon2 or bcrypt.

**Code:** `app/core/api_key_security.py`, `app/services/b2b_service.py`, `app/services/credit_service.py`, `app/services/admin_service.py`

**Migration:** `migrations/versions/c8d9e0f1a2b3_hash_api_keys.py`

## 6. Async jobs need durable inputs, results, and an owner check

### The problem

The API hex-encoded each uploaded document into the Celery message. Hex encoding nearly doubles the byte count, so a 10 MB upload became a broker message of about 20 MB before JSON and transport overhead. B2B jobs also had no application endpoint for retrieving their result; clients were told to access the Celery result backend directly.

### The fix

The upload is saved as a binary payload on the `TaskResult` row in Postgres. Celery receives only the task ID and small metadata. On completion or terminal failure, workers clear the binary payload. B2B tasks persist status and result, record the owning API-key digest, and expose `GET /third_party/api/v1/tasks/{task_id}`. The polling endpoint checks that the presented API key owns the task.

### Engineering principle

Message brokers are designed to carry work descriptions, not large sensitive documents. Persist the input in a controlled store and send a small reference. Result access needs an explicit authorization rule; an unguessable task ID is not a substitute for an owner check.

### Operational tradeoff

This implementation uses Postgres as the temporary document store. It keeps large documents out of Redis, but increases database storage and I/O while jobs are active. The cleanup task clears stale payloads, and completed task-level result copies are deleted after 30 days. If volume grows, move payloads to private object storage with retention and encryption controls.

**Code:** `app/models/task_result.py`, `app/api/v1/verification.py`, `app/api/v1/b2b.py`, `app/tasks/verification_tasks.py`

**Migration:** `migrations/versions/d9e0f1a2b3c4_task_payload_and_b2b_results.py`

## 7. Failed jobs should not charge customers for work they did not receive

### The problem

Credits were deducted before a job was queued. The API already restored credits when queue submission failed, but a job that exhausted its worker retries could still consume a credit even though no result was produced.

### The fix

When a job reaches terminal failure, the worker restores one credit and records `credit_refunded` in the task row. The refund and guard are committed together. Repeated task delivery will not refund twice. The daily cleanup task applies the same policy to jobs that remain pending or started for too long.

### Engineering principle

A paid or credit-based operation needs a complete lifecycle: reserve or deduct, execute, then either commit the charge on success or compensate on terminal failure. Make the compensation itself idempotent.

**Code:** `app/tasks/verification_tasks.py`, `app/tasks/admin_tasks.py`, `app/models/task_result.py`

## 8. Concurrent account creation must respect database uniqueness

### The problem

Two first-time requests for the same user could both query for a missing credit account and then both try to insert it. The database's unique `user_id` constraint correctly rejected one insert, but the application did not recover from that normal race.

### The fix

The account creation code catches the unique-constraint conflict, rolls back the losing insert, and reads the account created by the concurrent request.

### Engineering principle

A "check then insert" sequence is not atomic. Under concurrency, use an upsert where appropriate, or handle the unique-constraint race and re-read the winning row. The database constraint remains essential; application-level checks alone cannot enforce uniqueness under load.

**Code:** `app/services/credit_service.py`

## 9. Model scores need validation and careful product wording

### The problem

The Gemini response was used as a score without checking its type or range. A malformed response could fail later or produce an out-of-range result. Also, an AI score by itself is not direct evidence from WAEC or NECO that a certificate is genuine.

### The fix

The analyzer accepts only a numeric, finite score from 0 through 100. Invalid analysis is treated as a processing failure so it can be retried, rather than silently becoming a zero score. Reports now include the statement: "AI-assisted document screening only; this is not confirmation from the issuing authority."

### Engineering principle

Validate data at the boundary where it enters the system, especially when it comes from a probabilistic model. Keep the user-facing claim within the evidence the system actually has.

**Code:** `app/services/document_analyser.py`, `app/services/validator_service.py`, `app/tasks/verification_tasks.py`, `app/api/v1/verification.py`

## 10. Lists and background records need limits and retention

### The problem

Payment history, verification history, and API-key lists loaded every matching row into memory. Async task rows and their result copies could also grow without a defined cleanup policy.

### The fix

The history and key-list endpoints now accept `page` and bounded `page_size` parameters. Celery Beat schedules an hourly cleanup for stale pending payments and a daily cleanup that expires jobs older than 48 hours and deletes task-level results older than 30 days.

### Engineering principle

Every collection endpoint needs a bounded response size. Every persisted record needs a retention owner and a cleanup rule, particularly when it contains uploaded documents or extracted personal information.

**Code:** `app/api/v1/payments.py`, `app/api/v1/verification.py`, `app/api/v1/b2b.py`, `app/tasks/admin_tasks.py`, `app/core/celery_app.py`

## 11. Callback configuration should be explicit

### The problem

The callback default pointed to a developer's temporary ngrok URL. A deployment that forgot to configure the callback could send customers to that stale address. The local `.env` currently has no `SQUAD_CALLBACK_URL`.

### The fix

The stale default was removed. The app can still start without the setting, but payment initiation returns `503` before writing a pending order until a callback URL is configured. The example configuration and README now use the actual `/payment/paymentsuccess` route.

### Engineering principle

Fail close to the feature that requires a missing setting. A payment callback is a deployment-specific public URL; it should not silently inherit a development address.

**Code:** `app/core/config.py`, `app/services/payment_service.py`

## Database migration and deployment

The new code expects the added database columns and the hashed-key data format. Apply the migrations before starting the new API and workers:

```bash
alembic upgrade head
```

For an existing database whose tables already match the initial schema, stamp only the baseline revision `a1b2c3d4e5f6`, then run `alembic upgrade head`. Do **not** stamp `head`: that would skip the later schema and data migrations.

Because the key migration changes database values from plaintext to digests, stop old API and worker processes while the migration and code deployment happen. Old code expects plaintext keys and cannot authenticate against the migrated values.

Also set `SQUAD_CALLBACK_URL` in the deployment environment and run Celery Beat for the scheduled stale-payment and task cleanup jobs.

## Verification status and remaining work

The optional local browser console is served at `/test-console/` when
`ENABLE_TEST_CONSOLE=true`. See the README for launch instructions.

- A syntax-only parse of the Python files completed successfully.
- `git diff --check` completed without whitespace errors.
- The test suite was not run.
- The dependency manifest still contains minimum-version ranges and does not have a resolved lockfile. The environment had no installed packages to resolve against, so exact dependency pins were not invented. Generate and review a lockfile in the deployment environment with the project's supported Python and package resolver.
