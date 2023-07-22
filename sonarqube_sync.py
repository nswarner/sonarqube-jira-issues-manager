#!/usr/bin/env python3

import os
import sys
import json
import requests


class SonarQubeSync(object):

    sonarqube_url = ""
    sonarqube_token = ""
    jira_url = ""
    jira_token = ""
    project_key = ""
    disclosure = False

    def __init__(self):
        self.sonarqube_url = os.getenv("SONARQUBE_URL")
        self.sonarqube_token = os.getenv("ENCODED_SONAR_TOKEN")
        self.jira_url = os.getenv("JIRA_URL")
        self.jira_token = os.getenv("JIRA_ENCODED_TOKEN")
        self.project_key = os.getenv("JIRA_PROJECT_KEY")
        if self.sonarqube_url is None:
            raise Exception("SONARQUBE_URL environment variable is not set.")
            sys.exit(10)
        if self.sonarqube_token is None:
            raise Exception("SONARQUBE_TOKEN environment variable is not set.")
            sys.exit(11)
        if self.jira_url is None:
            raise Exception("JIRA_URL environment variable is not set.")
            sys.exit(12)
        if self.jira_token is None:
            raise Exception("JIRA_TOKEN environment variable is not set.")
            sys.exit(13)
        print("SonarQube URL: {}".format(self.sonarqube_url))
        if self.disclosure:
            print("SonarQube Token: {}".format(self.sonarqube_token))

    def __del__(self):
        pass

    def get_project_vulnerabilities(self):
        url = f"{self.sonarqube_url}/api/issues/search?types=VULNERABILITY"
        headers = {"Authorization": f"Basic {self.sonarqube_token}", 
                   "Accept": "application/json"}

        response = requests.get(url, headers=headers)
        data_json = response.json()

        return data_json

    def create_and_update_jira_tickets(self):
        data_json = self.get_project_vulnerabilities()
        for item in data_json["issues"]:
            if item["status"] == "OPEN":
                # unique key
                key = item["key"]
                rule = item["rule"]
                author = item["author"]
                project = item["project"] + ": " + rule + " - " + key
                severity = item["severity"]
                # filename
                component = item["component"]
                # start line
                start_line = item["textRange"]["startLine"]
                # end line
                end_line = item["textRange"]["endLine"]
                # unique hash
                hash = item["hash"]
                # issue description
                message = item["message"]

                description = f"Rule: {rule}\nAuthor: {author}\nSeverity: {severity}\nComponent: {component}\nStart Line: {start_line}\nEnd Line: {end_line}\nMessage: {message}\nUniqueRef: {key}:{hash}"

                # check if already exists in Jira
                if self.ticket_already_exists(key, hash):
                    print(f"Ticket already exists, {key}:{hash}")
                else:
                    print("Creating ticket, {}:{}.".format(key, hash))
                    self.create_jira_ticket("BS", project, description, "Task")

        return data_json

    def create_jira_ticket(self, project_key, summary, description, issue_type):
        url = self.jira_url + "/rest/api/2/issue"

        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Basic {self.jira_token}',
        }

        data = {
            "fields": {
                "project": {
                    "key": project_key
                },
                "summary": summary,
                "description": description,
                "issuetype": {
                    "name": issue_type
                }
            }
        }

        response = requests.post(url, json=data, headers=headers)

        if response.status_code == 201:
            return response.json()["key"]
        else:
            print(f"Failed to create Jira ticket. Status code: {response.status_code}")
            return None

    def ticket_already_exists(self, key, hash):

        url = self.jira_url + "/rest/api/3/search"
        description = f"{key}:{hash}"

        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Basic {self.jira_token}',
        }

        # The JQL query
        jql = f'project = {self.project_key} AND description ~ "{description}"'

        payload = {
            'jql': jql,
            'fields': ['key', 'summary', 'description']  # only fetch these fields for each issue
        }

        response = requests.post(
            url,
            headers=headers,
            data=json.dumps(payload),
        )

        if len(response.json()["issues"]) == 0:
            return False
        else:
            # Parse the response JSON
            data = response.json()
            # Print out each issue key and summary
            # for issue in data['issues']:
            #     print(f"Issue Key: {issue['key']}, Summary: {issue['fields']['summary']}")
            return True

    def update_jira_issues(self):
        data_json = self.get_project_vulnerabilities()
        for item in data_json["issues"]:
            if item["status"] == "CLOSED":
                if "done" not in item["tags"]:
                    self.cleanup_jira_ticket(item["key"], item["hash"])
                    self.cleanup_sonarqube_issue(item["key"])

    def cleanup_jira_ticket(self, key, hash):

        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Basic {self.jira_token}',
        }

        jql = f'project = {self.project_key} AND description ~ "{key}:{hash}"'
        payload = {'jql': jql}
        response = requests.post(f'{self.jira_url}/rest/api/3/search', headers=headers, data=json.dumps(payload))

        issues = response.json()['issues']
        if (len(issues) > 0):
            for issue in issues:
                issue_key = issue['key']

                # 2. Transition the issue to closed
                # Note: The id for the 'Close' transition can vary, check it in your Jira instance
                transition_payload = {'transition': {'id': '31'}}
                response = requests.post(f'{self.jira_url}/rest/api/3/issue/{issue_key}/transitions', headers=headers, data=json.dumps(transition_payload))
                response.raise_for_status()

                # 3. Add a comment to the issue
                comment_payload = {'body': 'Closing this issue as per the latest update.'}
                response = requests.post(f'{self.jira_url}/rest/api/3/issue/{issue_key}/comment', headers=headers, data=json.dumps(comment_payload))
                response.raise_for_status()
        else:
            print("Unable to find Jira ticket for {}:{}.".format(key, hash))

    def cleanup_sonarqube_issue(self, key):
        url = f"{self.sonarqube_url}/api/issues/set_tags"
        headers = {"Authorization": f"Basic {self.sonarqube_token}", 
                   "Accept": "application/json"}

        data = {
            "issue": key,
            "tags": "done",
        }

        response = requests.post(url, headers=headers, data=data)
        return response.status_code


if __name__ == "__main__":
    sonarqube_sync = SonarQubeSync()
    vulnerabilities = sonarqube_sync.get_project_vulnerabilities()
    print(vulnerabilities)