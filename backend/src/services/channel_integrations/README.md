# Channel integration boundary

This package keeps the existing production Meta webhook adapters behind a small provider boundary.

Zernio has its own explicit code path:

- OAuth/account sync: `services/zernio_integrator.py`
- webhook parsing + CRM persistence + AI replies: `services/zernio_webhooks.py`
- public webhook router: `routers/zernio_webhook.py`

Keep new Zernio behavior in those files instead of adding generic placeholder providers that reject webhooks or hide unimplemented methods.
