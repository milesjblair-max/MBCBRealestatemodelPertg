# Which instance am I changing? (an easy guide)

Two chains live in this one repo. When you want an update, just tell me **which
instance** and I work on the right branch and files. If you are not sure, tell me
what you see - the dev app has a yellow **DEV PREVIEW** badge top-left; production
does not.

## Production (live - do not break)
- **Branch:** `claude/repo-connection-mhn1nl`
- **Files:** root `index.html`, `web/`, `model/`, `data/`
- **Hosted:** GitHub Pages -> https://milesjblair-max.github.io/MBCBRealestatemodelPertg/
- **Say:** "production", "the live tool", "the one I'm sharing with my fiancee"

## Dev / platform (productisation - safe to iterate)
- **Branch:** `develop`
- **Files:** `platform/**` only
- **Hosted:** Cloudflare Pages preview for the `develop` branch (DEV badge top-left)
- **Say:** "the platform", "the dev version", "the productised version", "develop"

## How they stay separate
- The two branches never share commits unless you ask me to merge `develop -> production`.
- Cloudflare builds the `develop` preview; GitHub Pages keeps serving production.
- `platform/**` does not exist on the production branch, so nothing here can reach
  the live site by accident.
- `platform-ci.yml` validates the dev build on every `develop` push; it never
  deploys production.

## Giving feedback
- For the **dev** instance: "on the platform / dev, change X" (I edit `platform/`).
- For **production**: "on the live tool, change X" (I edit the root files).
- To promote dev work into production when you are happy: "merge develop into
  production" (I do it as a reviewed step, never automatically).
