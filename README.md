# 🧠 Shree (श्री) – Offline Personal AI Agent

> A privacy-first, offline AI agent that learns from user behavior and executes real-world actions on your system.

---

## 🚀 Introduction

Shree (श्री) is an offline-first personal AI agent designed to run directly on your device.

Unlike traditional AI assistants that rely heavily on cloud-based LLMs, Shree focuses on:

* ⚡ Execution over conversation
* 🧠 Personalization over general intelligence
* 🔒 Privacy over connectivity

Shree acts as a system-level assistant that can:

* Open applications
* Execute system commands
* Manage reminders
* Play music
* Search locally/web
* Learn user behavior over time

---

## ⚙️ Key Features

* ✅ Offline-first architecture
* ✅ Plugin-based execution system
* ✅ Rule-based intent engine (fast & reliable)
* ✅ Multi-command chaining (early agent capability)
* ✅ Persistent memory (behavior tracking)
* ✅ Suggestion engine (based on usage patterns)
* ✅ Safe system command execution

---

## 🧠 Vision

Shree is not just an assistant — it is a learning system.

Inspired by how humans learn from their environment, Shree is designed to:

* Observe user behavior
* Learn patterns over time
* Adapt to individual usage
* Become unique for every user

### 🎯 Goal

> Build a fully offline, privacy-first AI agent that evolves with its user.

---

## 🏗️ Architecture

```
User Input
   ↓
Intent Router (Rule Engine → LLM Fallback)
   ↓
Action Schema
   ↓
Executor
   ↓
Plugin System
   ↓
Memory Update
   ↓
Suggestion Engine
```

---

## 🔌 Plugins

Shree uses a modular plugin system:

* `OpenAppPlugin` → Open applications
* `CreateReminderPlugin` → Manage reminders
* `PlayMusicPlugin` → Play music
* `SearchWebPlugin` → Search queries
* `RunCommandPlugin` → Execute terminal commands
* `SystemControlPlugin` → Shutdown / restart / lock

---

## 🧠 Memory System

Shree stores user interactions to learn behavior:

* Tracks frequently used commands
* Stores recent command history
* Generates smart suggestions

Example:

```
You usually open Chrome. Want me to?
```

---

## 🧪 Example Commands

```
open chrome
play hanuman chalisa
create reminder for tomorrow 6am
open chrome and search youtube
open terminal and execute dir
shutdown system
```

---

## ⚠️ Current Limitations

* Limited context awareness
* Suggestion engine is frequency-based
* LLM fallback is unstable (offline-first priority)
* No long-term behavioral learning yet

---

## 🔮 Roadmap

### Phase 1 (Completed ✅)

* Rule engine
* Plugin system
* Basic memory
* Command execution

### Phase 2 (In Progress 🚧)

* Context-aware execution
* Command normalization
* Improved suggestions

### Phase 3 (Next 🚀)

* Sequence-based learning
* Shree Brain (planner system)
* Intelligent task chaining

### Phase 4 (Future 🔥)

* Voice commands
* Multi-device sync
* Personalized AI behavior

---

## 💡 Philosophy

Shree is built on three core principles:

### 1. 🔒 Privacy First

No data leaves your device.

### 2. ⚡ Execution First

Actions matter more than conversation.

### 3. 🧠 Learning First

Every user gets a unique AI experience.

---

## 🧪 Testing

### Running Tests

Run the comprehensive test suite:

```bash
python tests/test_shree_features.py
```

### Test Logging

Test results are automatically logged to `reports/tests/test-log` when tests are executed. This file contains:

* Test name and status (PASS/FAIL/ERROR)
* Error messages for failed or errored tests
* Useful for CI/CD integration and test history tracking

Example log output:
```
[PASS] test_planner_engine_wraps_single_action_with_step_number
[PASS] test_planner_engine_keeps_action_list_and_adds_step_numbers
[FAIL] test_agent_loop_executes_open_file_intent
  Error: AssertionError: 'Opened file: report.pdf [test]' != 'Opened file: report.pdf'
```

---

## 🤝 Contributing

This is an evolving project. Contributions, ideas, and feedback are welcome.

---

## ⭐ Final Thought

Shree is not trying to compete with cloud AI.

It is building something different:

> A personal AI that lives with you, learns from you, and works for you — completely offline.
