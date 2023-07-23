#!/usr/bin/env python3

from datetime import datetime
import os
import sys
import json
import time
import requests


class SonarQubeSync(object):

    sonarqube_url = ""
    sonarqube_token = ""
    jira_url = ""
    jira_token = ""
    project_key = ""
    disclosure = False
    # Analyze every 1 minute
    analysis_frequency = 700

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

    # Gets all vulnerabilities for a project
    def sq_get_project_vulnerabilities(self, project_key=""):
        if project_key == "":
            url = f"{self.sonarqube_url}/api/issues/search?types=VULNERABILITY"
        else:
            url = f"{self.sonarqube_url}/api/issues/search?types=VULNERABILITY&projectKeys={project_key}"
        headers = {"Authorization": f"Basic {self.sonarqube_token}", 
                   "Accept": "application/json"}

        response = requests.get(url, headers=headers)
        data_json = response.json()

        return data_json

    # Determines whether to create or update Jira tickets
    def create_and_update_jira_tickets(self, project_key=""):
        data_json = self.sq_get_project_vulnerabilities(project_key)
        for item in data_json["issues"]:
            print(item['tags'])
            if item["status"] == "CLOSED" and "done" not in item["tags"]:
                print("Found a fixed issue in SonarQube, {}:{}.".format(item["key"], item["hash"]))
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
                if self.jira_ticket_already_exists(key, hash):
                    print(f"Ticket already exists, {key}:{hash}")
                else:
                    print("Creating ticket, {}:{}.".format(key, hash))
                    self.jira_create_ticket("BS", project, description, "Task")

        self.update_issues(project_key)

        return data_json

    # Creates a Jira ticket
    def jira_create_ticket(self, project_key, summary, description, issue_type):
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

    # Boolean to check whether a ticket already exists
    def jira_ticket_already_exists(self, key, hash):

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
            return True

    # Updates Jira tickets when SonarQube issues are closed
    def update_issues(self, project_key=""):
        data_json = self.sq_get_project_vulnerabilities(project_key)
        for item in data_json["issues"]:
            if item["status"] == "CLOSED":
                if "done" not in item["tags"]:
                    self.jira_cleanup_ticket(item["key"], item["hash"])
                    self.sq_cleanup_issue(item["key"])

    # Closes Jira tickets
    def jira_cleanup_ticket(self, key, hash):

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

    # Adds a `done` tag to SonarQube issues
    def sq_cleanup_issue(self, key):
        url = f"{self.sonarqube_url}/api/issues/set_tags"
        headers = {"Authorization": f"Basic {self.sonarqube_token}", 
                   "Accept": "application/json"}

        data = {
            "issue": key,
            "tags": "done",
        }

        response = requests.post(url, headers=headers, data=data)
        return response.status_code

    # Removes the `done` tag from a SonarQube issue
    def sq_reset_issue(self, key):
        url = f"{self.sonarqube_url}/api/issues/tags"
        headers = {"Authorization": f"Basic {self.sonarqube_token}", 
                   "Accept": "application/json"}

        # Send GET request to get the current tags of the issue
        response = requests.get(f"{url}?ps=500", headers=headers)

        # Parse the current tags
        current_tags = response.json()

        # If the tag to remove is in the current tags, remove it
        if "done" in current_tags:
            current_tags.remove("done")

        # Prepare data for the POST request
        data = {
            "issue": key,
            "tags": ','.join(current_tags),
        }

        # Send POST request to the SonarQube server to update the tags
        response = requests.post(f"{self.sonarqube_url}/api/issues/set_tags", headers=headers, data=data)

    # Get a list of SonarQube projects and their data
    def sq_get_projects_data(self):
        url = f"{self.sonarqube_url}/api/projects/search"
        headers = {"Authorization": f"Basic {self.sonarqube_token}", 
                   "Accept": "application/json"}

        response = requests.get(url, headers=headers)
        projects_json = response.json()['components']

        return projects_json

    def sq_get_last_analysis_time(self, project_key):

        url_analysis = f"{self.sonarqube_url}/api/project_analyses/search?project={project_key}"
        headers = {"Authorization": f"Basic {self.sonarqube_token}", 
                   "Accept": "application/json"}
        response_analysis = requests.get(url_analysis, headers=headers)
        response_analysis.raise_for_status()

        # Get the analyses for the project
        analyses = response_analysis.json()['analyses']

        # Check if there are analyses for the project
        if analyses:
            # Get the date of the most recent analysis
            last_analysis_date = analyses[0]['date']

            # Convert to timestamp
            last_analysis_timestamp = datetime.strptime(last_analysis_date, "%Y-%m-%dT%H:%M:%S%z").timestamp()
            
            return last_analysis_timestamp

    def sq_analyze_sonarqube_last_analysis_time(self):
        projects = self.sq_get_projects_data()
        for project in projects:
            project_key = project['key']
            last_analysis_timestamp = self.sq_get_last_analysis_time(project_key)
            seconds_ago = time.time() - last_analysis_timestamp
            if self.analysis_frequency > seconds_ago:
                print(f"Project {project_key} was last analyzed {seconds_ago} seconds ago. Reviewing now.")
                self.sq_analyze_project(project_key)

    def sq_analyze_project(self, project_key):
        self.create_and_update_jira_tickets(project_key)


if __name__ == "__main__":
    sonarqube_sync = SonarQubeSync()
    # vulnerabilities = sonarqube_sync.sq_get_project_vulnerabilities()
    # print(vulnerabilities)
    # print("-------------------")
    # vulnerabilities = sonarqube_sync.sq_get_project_vulnerabilities("sast-3-sonarqube")
    # print(vulnerabilities)
    # print("-------------------")
    sonarqube_sync.sq_analyze_sonarqube_last_analysis_time()