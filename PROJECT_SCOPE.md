# Codev product scope

## Product

Codev is a private, single-operator course-platform CRM. It is derived from the Zernio integrator codebase but is maintained as an independent application.

## Locked decisions

- Product name: **Codev**.
- UI language: **Azerbaijani only**.
- Public landing page: **removed**; anonymous visitors see one login screen.
- Account model: **one operator**; administration and daily operations belong in one workspace.
- Business domain: **course platform**, not a shop/catalog storefront.
- Messaging channels retained: **Instagram, WhatsApp, TikTok**.
- Posting channels: **Instagram, WhatsApp, TikTok, LinkedIn** where supported by provider contracts.
- AI post creation/generation: **removed**. Posting accepts operator-provided content/media only.
- Visual system: pending the design prompt supplied by the product owner.

## Isolation

The source project must not be modified:

`/home/server/projects/instagram_assistant_integrator/ai-crm-bot`

Codev lives in:

`/home/server/projects/codev`

Codev has its own Compose project, Postgres volume, upload volume and loopback ports. It must never attach to the integrator Docker network or database volume.

## Delivery sequence

1. Isolate runtime, credentials, repository and branding.
2. Replace landing/admin/company route split with one login and one workspace.
3. Apply the supplied visual-design prompt.
4. Replace shop semantics with courses, students, enrolments and course knowledge.
5. Remove AI-generated social-post flows while retaining manual upload/scheduling.
6. Add LinkedIn connection and manual posting behind a provider boundary.
7. Remove dead multi-tenant registration/package-management behavior.
8. Run backend tests, frontend build, isolated Docker smoke tests and browser QA.
