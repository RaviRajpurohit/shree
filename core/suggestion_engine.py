class SuggestionEngine:

    def __init__(self, memory):
        self.memory = memory

    def get_suggestion(self):
        return self.memory.get_suggestion()
