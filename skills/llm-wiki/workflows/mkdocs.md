# Workflow: mkdocs — browse the wiki as a local website

**When to run this:** the user wants to view their wiki in a browser. The wiki is already markdown, but a static-site generator like mkdocs adds search, a nicer sidebar, dark mode, and the ability to publish as a public or private website. The trigger is usually one of:

- "Let me browse my wiki as a website"
- "Can I view my wiki in a browser?"
- "Set up mkdocs for my wiki"
- "Generate a static site from my wiki"
- "How do I publish my wiki?"
- "Can I search my wiki?"

**Prerequisite state:** a wiki exists at a known path with a `SCHEMA.md` at the root. Run [`init.md`](init.md) first if not.

**This workflow is opt-in.** The `init` workflow does **not** set up mkdocs by default — it only scaffolds the plain markdown wiki. mkdocs is an optional extra that requires `pip install` and adds a dependency on an external Python package.

---

## Step 0 — Read the wiki's schema

Read `<wiki>/SCHEMA.md` to know the directory layout. mkdocs setup doesn't depend much on it, but confirming the layout is how you verify this is actually a wiki.

---

## Step 1 — Check the state

Before doing anything, verify:

1. **`<wiki>/SCHEMA.md` exists** — otherwise this isn't a wiki. Tell the user to run `init` first.
2. **`<wiki>/mkdocs.yml` exists or not**. If it already exists, mkdocs was previously set up — tell the user and offer the choice of:
   - Leaving the existing config alone (show them `mkdocs serve` instructions)
   - Overwriting with the default template (dangerous — loses any customizations)

---

## Step 2 — Explain what mkdocs will do

Don't run `wiki_mkdocs_setup.py` without first telling the user what's about to happen. Say something like:

> "mkdocs is a Python-based static site generator. I'll:
>
> 1. Write a `mkdocs.yml` file at the root of your wiki with a sensible default config — it uses the Material theme, enables search, dark mode, and points at your existing wiki/ folder.
> 2. It'll read the existing markdown files (all of them, including your entity/concept/source/synthesis pages and the top-level `index.md`) and build them into a browsable website.
> 3. Your `raw/` sources, `SCHEMA.md`, `log.md` bindings and anything under `.trash/` will be excluded from the site — they won't show up in the public view.
>
> You'll still need to install two Python packages once (`mkdocs` and `mkdocs-material`) — the skill script doesn't do that for you, because I don't want to pip-install things without your permission.
>
> OK to proceed?"

Wait for the user to say yes. **Do not run the script without explicit confirmation.**

---

## Step 3 — Run the setup script

Once confirmed, run:

```bash
python /path/to/skills/llm-wiki/scripts/wiki_mkdocs_setup.py <wiki-path>
```

This script:

1. Copies the `mkdocs.yml` template from the skill folder to `<wiki>/mkdocs.yml`
2. Checks if `mkdocs` and `mkdocs-material` are already importable (using `_preflight.check`)
3. Appends a `## [YYYY-MM-DD] Mkdocs: setup completed` entry to `log.md`
4. Prints next steps (how to install packages, how to run `mkdocs serve`)

Script exits with `0` on success, `2` on error (e.g. no `SCHEMA.md`, template missing, or `mkdocs.yml` already exists without `--force`).

If `mkdocs.yml` already exists and the user wants to overwrite, pass `--force`.

---

## Step 4 — Summarize and give the user the commands

Report to the user what happened:

> "Done. Here's what I set up:
>
> - **Config file**: `<wiki>/mkdocs.yml` — you can edit this anytime, it's your file now
> - **Theme**: Material for MkDocs (with search, dark mode, and instant-loading pages)
> - **Content source**: your entire wiki folder (the `docs_dir: .` setting)
> - **Excluded from the site**: `raw/`, `SCHEMA.md`, `mkdocs.yml` itself, `.git/`, `.trash/`
>
> **To start using it**, run these commands in your terminal:
>
> ```bash
> # One-time install (skip if already installed)
> pip install mkdocs mkdocs-material
>
> # Preview in your browser (live-reloads as you edit)
> cd <wiki-path>
> mkdocs serve
>
> # Then open http://127.0.0.1:8000
> ```
>
> When you want to build a deployable static site:
>
> ```bash
> mkdocs build
> # Output goes to <wiki-path>/site/
> ```
>
> You can then deploy `site/` to any static host (GitHub Pages, Netlify, Cloudflare Pages, your own server — any static file server). mkdocs also has `mkdocs gh-deploy` if you want to publish to GitHub Pages in one command.
>
> Anything else about the setup I should explain?"

---

## Step 5 — Check that the log entry was appended

The `wiki_mkdocs_setup.py` script appends a log entry automatically. Verify it by briefly mentioning it in the summary (Step 4 already does this implicitly).

If the script reports `log_entry_appended: false` in its JSON output, manually append the entry yourself:

```markdown
## [YYYY-MM-DD] Mkdocs: setup completed
- **Config file**: `mkdocs.yml` (from the llm-wiki skill template)
- **Theme**: Material for MkDocs
- **Next**: run `pip install mkdocs mkdocs-material` then `mkdocs serve`
```

---

## Common failures and recovery

### `mkdocs.yml` already exists

The script refuses to overwrite by default. Ask the user:

> "Your wiki already has a `mkdocs.yml` at `<path>/mkdocs.yml`. Options:
>
> 1. **Keep your existing config** — just run `mkdocs serve` from the wiki folder
> 2. **Overwrite with the skill's default template** — you'll lose any customizations you made. I can do this with `--force`. Confirm?
> 3. **Show me the diff** — I can read both files and show you what would change"

Default to option 1. Only overwrite with an explicit "yes, overwrite".

### The user doesn't have Python or pip

mkdocs is a Python package, so the user needs Python (which they must have anyway, since they're using this skill). If `pip install mkdocs` fails, point them at:

- [The mkdocs installation docs](https://www.mkdocs.org/user-guide/installation/)
- Their system's Python package manager (e.g. `brew install python` on macOS, `apt install python3-pip` on Debian/Ubuntu)

### The user is behind a corporate proxy

`pip install` may need `HTTPS_PROXY`. The skill's `_preflight` helper knows how to format the hint — but `wiki_mkdocs_setup.py` doesn't exit with the preflight guide because mkdocs is strictly optional (we use `_preflight.check`, not `_preflight.require`). If the user asks about this:

> "If `pip install` fails because of a corporate proxy, you'll need to set `HTTPS_PROXY` first. On Windows PowerShell: `$env:HTTPS_PROXY = 'http://proxy.example.com:8080'`. On bash/zsh: `export HTTPS_PROXY=http://proxy.example.com:8080`. Then retry the install."

### `mkdocs serve` fails with 'unknown configuration'

The mkdocs.yml template uses a few plugins (`pymdownx.*`) that ship with `mkdocs-material`. If the user installs `mkdocs` but not `mkdocs-material`, those plugins won't be found. Tell them:

> "Looks like you only installed `mkdocs`. The template needs `mkdocs-material` too (for the theme and the syntax extensions). Run `pip install mkdocs-material` and try again."

### The wiki has broken markdown links (mkdocs is strict)

mkdocs **will warn loudly** about unresolved relative links. This is actually useful — run `wiki_lint.py --mode broken-links` first to find them, fix them, then try `mkdocs serve` again.

If the user asks "why does mkdocs yell at me", tell them:

> "mkdocs strictly validates all relative `.md` links in your pages. It's the same thing `wiki_lint.py` does, but mkdocs catches them as *warnings* when building. Want me to run the lint pass to find and fix them?"

---

## Not what this workflow does

A few things this workflow **deliberately doesn't do**:

- **It doesn't run `mkdocs serve`.** That's a long-lived background process; starting one from a skill is out of scope. The user runs it themselves after the setup completes.
- **It doesn't `pip install` anything.** Package installation is a user-owned decision. We only check what's present and tell them what's missing.
- **It doesn't deploy to GitHub Pages or anywhere else.** Deployment is a judgment call (which branch? which domain? which CI?) that belongs to the user, not the skill.
- **It doesn't modify the wiki's existing markdown files** to be mkdocs-friendly. Our link style (relative markdown links) already is mkdocs-friendly — that's why we chose it. If the user has old `[[wikilink]]` syntax in their pages, tell them mkdocs won't render those and offer to run a lint pass or manual fix-up.
