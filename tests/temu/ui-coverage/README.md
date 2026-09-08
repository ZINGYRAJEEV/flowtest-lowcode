# Temu — UI Coverage

Homepage / cookie / nav / search / component-id coverage for [temu.com](https://www.temu.com/).

## Environment

- **Temu Prod** → `https://www.temu.com`
- `LANDING_URL` → Impact / adMarketplace campaign URL

## Notes

- Cookie banner must be accepted (`Accept all` / OneTrust).
- Temu may block or challenge headless automation; run locally headed if needed.
- Component inventory collects ids, data-testids, roles, and landmarks.

Regenerate: `python scripts/setup_temu_project.py`
