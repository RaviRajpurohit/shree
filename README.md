# Shree

Shree is a Python-based offline AI agent that parses user commands, routes them to local plugins, remembers usage patterns, and offers lightweight context-aware suggestions.

## Features

- Offline-first intent routing with rule-based parsing and LLM fallback
- Offline basic knowledge handling for identity, greetings, time, date, and help without using the LLM
- Local plugin execution for actions like opening apps, web search, reminders, music, and browser control
- Memory-backed features such as command history, suggestions, and explainable suggestions
- Context-aware follow-up handling such as `open new tab` and `play next`
- Prompt suite and unit tests for regression coverage

## Project Structure

- `main.py`: interactive CLI entry point
- `core/`: agent loop, routing, memory, executor, and intent logic
- `plugins/`: action plugins
- `llm/`: offline LLM client integration
- `scripts/`: prompt-suite and utility scripts
- `tests/`: unit tests
- `reports/`: generated prompt test reports
- `logs/`: runtime logs

## Requirements

- Python 3.11+ recommended
- Windows environment recommended for current app-opening and media-control plugins

Install dependencies:

```powershell
pip install -r requirements.txt
```

## Run

```powershell
python main.py
```

Example commands:

- `open chrome`
- `open new tab`
- `open chrome with new tab`
- `play hanuman chalisa`
- `play next`
- `show my last commands`
- `why did you suggest chrome`

Exit with:

```text
exit
```

## Tests

Run unit tests:

```powershell
python -m unittest discover -s tests -p "test_*.py" -v
```

Run the prompt suite:

```powershell
python scripts\run_prompt_suite.py
```

The prompt suite runs in snapshot mode:
- it replaces app, browser, music, reminder, and system-action plugins with safe test doubles
- it keeps basic queries such as `who are you`, `what is time`, `what is date`, greetings, and help fully offline
- it writes a Markdown report to `reports/` and prints the generated report path

## License

This repository is private and distributed under a proprietary license. See [LICENSE](./LICENSE) for details.
