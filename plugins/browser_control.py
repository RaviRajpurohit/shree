import webbrowser

from plugins.base_plugin import BasePlugin


class BrowserControlPlugin(BasePlugin):
    action = "browser_control"

    def execute(self, parameters):
        browser = (parameters.get("browser") or "microsoft edge").strip().lower() or "microsoft edge"
        resource = (parameters.get("resource") or "new_tab").strip().lower() or "new_tab"

        if resource != "new_tab":
            return f"Unsupported browser control action: {resource}"

        url = self._resolve_browser_home(browser)

        try:
            webbrowser.open_new_tab(url)
        except Exception:
            return f"I could not open a new tab in {browser}."

        if browser == "default":
            return "Opened a new tab in the default browser."

        return f"Opened a new tab in {browser}."

    @staticmethod
    def _resolve_browser_home(browser):
        urls = {
            "chrome": "https://www.google.com",
            "edge": "https://www.bing.com",
            "firefox": "https://www.mozilla.org",
            "default": "https://www.bing.com",
        }
        return urls.get(browser, "about:blank")
