# Code Freezing Checker

Python checker to block merge/deploy pipelines during configured freeze windows.

## Project layout

- `src/` contains the Python entrypoint and application code
- `config/` stores the freeze configuration file
- `.github/workflows/` contains the GitHub Actions workflow

## How it works

The script reads `config/config.yml` and:

- Allows users listed in `bypass_group`
- Blocks pipeline when current date is within a configured period in `freezing_dates`
- Uses `GITHUB_ACTOR` in CI (or `--user` locally) to evaluate bypass

## Configuration

Example `config/config.yml`:

```yaml
bypass_group:
  - root
  - release-manager

freezing_dates:
  End of the Year:
    from: 2025-12-24
    to: 2026-01-02
  Carnival:
    from: 2026-02-14
    to: 2026-02-18
```

## Local usage

Install dependencies:

```bash
pip install -r requirements.txt
```

Run with current date:

```bash
python src/code-freezing.py --config config/config.yml
```

Run simulating a specific date:

```bash
python src/code-freezing.py --config config/config.yml --date 2026-12-26
```

Run simulating a specific user:

```bash
python src/code-freezing.py --config config/config.yml --user mylena
```

## Tests

Run test suite locally:

```bash
pytest -q
```

## GitHub Actions integration

The workflow file `.github/workflows/code-freeze-check.yml` runs on push, pull request, and manual trigger.

If the current date is inside a freeze period and actor is not bypassed, the job fails with exit code `1`.
