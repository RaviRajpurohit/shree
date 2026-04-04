from plugins.base_plugin import BasePlugin


class CreateReminderPlugin(BasePlugin):

    action = "create_reminder"
    required_parameters = {
        "topic": "Please specify what the reminder is for",
        "time": "Please specify the reminder time",
        "day": "Please specify the reminder day",
    }

    def execute(self, parameters):
        topic = parameters.get("topic")
        day = parameters.get("day")
        time = parameters.get("time")

        return f"Reminder created for {topic} on {day} at {time}"
