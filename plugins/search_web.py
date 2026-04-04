import webbrowser
from urllib.parse import quote_plus

from plugins.base_plugin import BasePlugin


class SearchWebPlugin(BasePlugin):

    action = "search"
    required_parameters = {
        "query": "Please specify what you want to search for",
    }

    def execute(self, parameters):
        query = (parameters.get("query") or "").strip()

        url = f"https://www.google.com/search?q={quote_plus(query)}"

        try:
            webbrowser.open(url)
        except Exception:
            return f"Search ready for {query}, but the browser could not be opened automatically."

        return f"Searching for {query}"
