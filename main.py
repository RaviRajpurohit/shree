import logging
from pathlib import Path

from core.agent_loop import AgentLoop


def configure_logging():
    logs_dir = Path(__file__).resolve().parent / "logs"
    logs_dir.mkdir(exist_ok=True)
    log_file = logs_dir / "shree.log"

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.handlers.clear()

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")
    )

    root_logger.addHandler(file_handler)


def main():
    configure_logging()

    print("Shree is running...")

    agent = AgentLoop()

    while True:
        suggestion = agent.get_suggestion()

        if suggestion:
            print(f"Shree suggestion: {suggestion}")

        user_input = input("You: ")

        if user_input.lower() in ["exit", "quit"]:
            break

        if user_input.lower() == "memory summary":
            print(f"Shree: {agent.get_memory_summary()}")
            continue

        response = agent.process(user_input)

        print(f"Shree: {response}")


if __name__ == "__main__":
    main()
