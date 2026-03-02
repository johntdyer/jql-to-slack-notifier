import logging
import requests
from requests.auth import HTTPBasicAuth

logger = logging.getLogger(__name__)


class JiraClient:
    def __init__(self, base_url: str, email: str, api_token: str):
        self.base_url = base_url.rstrip("/")
        self.auth = HTTPBasicAuth(email, api_token)
        self.session = requests.Session()
        self.session.headers.update({"Accept": "application/json"})

    def search(
        self,
        jql: str,
        fields: list[str],
        max_results: int = 50,
        field_map: dict | None = None,
    ) -> list[dict]:
        # field_map: {display_name: jira_field_id} for custom fields
        # Replace display names with their Jira field IDs in the API request
        fm = field_map or {}
        api_fields = [fm.get(f, f) for f in fields]

        url = f"{self.base_url}/rest/api/3/search/jql"
        params = {
            "jql": jql,
            "maxResults": max_results,
            "fields": ",".join(api_fields),
        }
        logger.debug("GET %s | jql=%r | fields=%s | maxResults=%s", url, jql, params["fields"], max_results)
        response = self.session.get(url, params=params, auth=self.auth)
        logger.debug("Response: HTTP %s", response.status_code)
        response.raise_for_status()
        data = response.json()
        issues = data.get("issues", [])
        logger.debug("Returned %d issue(s)", len(issues))
        results = [self._normalize(issue, fields, fm) for issue in issues]
        if results:
            missing = [f for f in fields if f != "key" and f not in results[0]]
            for f in missing:
                logger.warning("Field %r is not supported by the normalizer and will be omitted from results", f)
        for result in results:
            logger.debug("  %s: %s", result["key"], {k: v for k, v in result.items() if k != "key"})
        return results

    def _normalize(self, issue: dict, fields: list[str], field_map: dict | None = None) -> dict:
        f = issue.get("fields", {})
        fm = field_map or {}
        result = {"key": issue["key"]}

        if "summary" in fields:
            result["summary"] = f.get("summary", "")

        if "assignee" in fields:
            assignee = f.get("assignee")
            result["assignee"] = assignee["displayName"] if assignee else "Unassigned"

        if "status" in fields:
            status = f.get("status", {})
            result["status"] = status.get("name", "Unknown")

        if "priority" in fields:
            priority = f.get("priority", {})
            result["priority"] = priority.get("name", "Unknown")

        if "reporter" in fields:
            reporter = f.get("reporter")
            result["reporter"] = reporter["displayName"] if reporter else "Unknown"

        if "issuetype" in fields:
            issuetype = f.get("issuetype", {})
            result["issuetype"] = issuetype.get("name", "Unknown")

        if "duedate" in fields:
            result["duedate"] = f.get("duedate") or ""

        # Custom fields via field_map: extract by Jira field ID, store under display name
        for display_name, field_id in fm.items():
            if display_name in fields:
                result[display_name] = f.get(field_id) or ""

        return result
