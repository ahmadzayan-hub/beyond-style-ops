# Operations authentication and authorization

The dashboard no longer treats a role selected by the visitor as authorization.
Every dashboard page requires Streamlit's verified OpenID Connect login and an
explicit server-owned role. Missing configuration, an unrecognized account,
an issuer mismatch, or an invalid role denies access before operational data loads.
The independent command-line verification scripts are unchanged.

## Before merging or deploying

This change intentionally closes an unconfigured dashboard. It does **not** create
an identity provider, credentials, user grants, or change a running deployment.
The owner must review the role policy and arrange approved authentication setup
before rollout. Back up existing deployment configuration and document a recovery
path. Do not restore the selectable-role implementation as a public fallback.

1. Install the updated requirements (`streamlit[auth]>=1.50.0`). Use an approved
   OIDC provider and Streamlit's supported `[auth]` configuration. Register the
   deployed HTTPS `/oauth2callback` redirect URI. Keep all credentials in
   deployment secrets; never paste them into GitHub, issues or logs.
2. In `[ops_auth]`, set `issuer` to the exact verified ID-token `iss` value.
   In `[ops_auth.user_roles]`, map each approved user's stable `sub` value to one
   role listed in `ops/config.py`. Obtain subjects through your identity provider's
   trusted administration flow. Email addresses, display names, query parameters,
   client-submitted roles, and the old session role are not accepted identities.
3. Confirm the owner account can sign in before granting individual staff access.
   Do not give every authenticated user a default role. Only the deployment owner
   may edit the allowlist. Removing a subject revokes access on subsequent page
   runs and writes; restart the app after changing deployment secrets if required
   by the hosting platform.
4. Test with synthetic data first: anonymous access to every direct page URL;
   an authenticated but unmapped account; each staff role; read-only writes;
   sign-out and browser back; a revoked account; and separate browser sessions.
   Confirm no operational data appears to an unauthorized visitor, including from
   cached pages, and no unauthorized Sheets update is made.
5. Verify actual OIDC cookies, HTTPS, hosting secrets, Sheets permissions and
   identity-provider access policies before real customer data is admitted.

See Streamlit's [authentication guide](https://docs.streamlit.io/develop/concepts/connections/authentication).
Use these synthetic placeholders as a template in deployment secrets, never as
working credentials. Existing integration examples are not changed by this patch.

```toml
[auth]
redirect_uri = "https://your-dashboard.example.test/oauth2callback"
cookie_secret = "replace-in-deployment-secrets-only"
client_id = "your-oidc-client-id"
client_secret = "your-oidc-client-secret"
server_metadata_url = "https://your-identity-provider.example.test/.well-known/openid-configuration"

[ops_auth]
issuer = "https://your-identity-provider.example.test"

[ops_auth.user_roles]
# Add approved OIDC sub values in deployment secrets only, not in this document.
# "approved-owner-subject" = "Owner / Admin"
# "approved-sales-subject" = "Sales / WhatsApp"
# "approved-packing-subject" = "Packing / Sharon"
# "approved-courier-subject" = "Courier / Delivery"
# "approved-viewer-subject" = "Read Only"
```

## Write policy

- Owner / Admin: existing owner operations.
- Sales / WhatsApp: initial processing/QC handoff, payments and reviews/closeout.
- Packing / Sharon: QC, packing, labels and courier booking.
- Courier / Delivery: courier tracking, delivery and delivery evidence.
- Read Only: no writes.

All approved roles retain the current shared operational read view. This patch
is **not** field-level privacy, row-level tenancy or a staff data-minimization
project. Review who needs customer/payment visibility before assigning a role.

The Sheets read/write boundary rechecks identity on each access. Master-order
writes enforce allowed fields and workflow states for the role. Buttons also show
only actions for the assigned role, but hiding a button is not the security check.
Role checks do not replace the existing business prerequisites (payment evidence,
QC, delivery proof) or provide transaction/audit guarantees for Sheets.

## Verification

Run all existing script suites and the new offline authorization suite:

```sh
python tests/test_module1.py
python tests/test_verification.py
python tests/test_escalation_summary.py
python tests/test_directives.py
python -m unittest discover -s tests -p 'test_auth*.py' -v
```

The authorization tests use synthetic claims and mocked worksheet access. They
cover anonymous/unmapped/invalid identities, session-role tampering, role-specific
write denials, cache-connection guards and gating all seven page entry points.
They do not establish real hosted identity-provider or Google Sheets acceptance.

### Known remaining acceptance work

Delivery/closeout evidence and label QC now have shared write-boundary validation;
see [order integrity](OPS_ORDER_INTEGRITY.md). Dashboard cells and the paired
payment records use one atomic workbook batch. This is not a complete lifecycle
policy, concurrent read/write transaction, or audit log. No production login,
provider revocation, live Sheets write, multi-user browser or hosted cache
acceptance has been established by these local tests.
