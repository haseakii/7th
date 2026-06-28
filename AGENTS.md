# Repository Guidelines

## Project Structure & Module Organization
The active application lives in `7th/`. Shared runtime code belongs in `7th/module/`, feature automation belongs in `7th/tasks/`, and assets live in `7th/assets/`. Tests are in `7th/tests/` and follow `test_*.py` naming. Common entry points include `7th/main.py`, `7th/gui.py`, `7th/launcher.py`, `7th/shop_bot.py`, and `7th/calibrate.py`. Keep scratch files in `7th/temp/` only.

## Build, Test, and Development Commands
Run commands from `7th/` unless noted otherwise.
- `pip install -r requirements.txt`: installs runtime and test dependencies.
- `python -m pytest tests`: runs the full test suite.
- `python main.py --webui`: starts the local Web UI.
- `python main.py --config-name default`: starts the ALAS-style scheduler with the default config.
- `build.bat`: builds the packaged app with PyInstaller.

## Coding Style & Naming Conventions
Use standard Python style: 4-space indentation, `snake_case` for functions, variables, and modules, and `PascalCase` for classes. Keep modules focused on one domain, such as `tasks/secret_shop/` or `module/webui/`. Prefer descriptive filenames and preserve existing public constants when tests or external callers import them.

## Testing Guidelines
Use `pytest` for unit and property tests. Name new tests `test_<feature>_unit.py` or `test_<feature>_property.py`. Mock device, OCR, and Web UI boundaries with `unittest.mock`. Add or update tests when changing scheduler behavior, OCR parsing, coordinate logic, or shop automation flow.

## Commit & Pull Request Guidelines
Recent commits use short prefixes such as `feat:`, `fix:`, `chore:`, and `revert:` with concise Chinese or English summaries. Keep commits focused. Pull requests should explain user-facing impact, list validation steps, and include screenshots or logs for UI or automation behavior changes. Link related issues when available.

## Security & Configuration Tips
Treat `7th/config.yaml`, `7th/config/*.json`, and generated logs as environment-specific unless the change is intentional. Avoid committing emulator credentials, device serials, temporary screenshots, or debug artifacts from `7th/log/`, `7th/logs/`, `7th/screenshots/`, or `7th/temp/`.
