# sonarqube-jira-issues-manager

Simple scripting to manage connectivity between Jira and SonarQube. As new issues are created in SonarQube, this script will identify the new issue(s), check Jira whether a ticket exists in Jira for the SonarQube issue, and if not, creates the ticket in Jira. This script can also scan SonarQube for closed issues which likely have an open Jira ticket, comment in the Jira ticket and then close the Jira ticket.

## Features

* When a vulnerability is identified in SonarQube, this script creates a complementary Jira ticket (issue)
  + The Jira ticket will contain a unique `{key}:{hash}` identifier in the description
* When a vulnerability is closed (`CLOSED`) in SonarQube, this script will:
  + Tag the SonarQube issue as closed (`done`)
  +  Close (`done`) the Jira ticket with a new comment indicating the issue is resolved

## Exception(al) workflows

* When a tagged (`done`) issue in SonarQube is in the `OPEN` status, this script will:
  + Tag the SonarQube issue as reopened (`reopened`)
  + Remove the SonarQube `done` tag from the SonarQube issue
  + Search for an associated Jira ticket,
    -  If a Jira ticket exists: (1) Reopen the ticket, (2) Add a new comment indicating it's reopened, (3) Add the label `sonarqube_regression` to the Jira ticket
    -  If a Jira ticket does not exist: (1) Create the ticket, (2) Label the ticket `sonarqube_review`, (3) Add a new comment indicating a ticket may be missing

# Simplicity

## SonarQube

All function definitions which access the SonarQube API start with `sq_`.

## Jira

All function definitions which access the Jira API start with `jira_`.

## Non-SQ-Jira logic

All other function definitions should have reasonable names.

# Testing workflows

When a new SQ scan happens,

1. Find any new SQ issues that don't have tags,
  + Create a Jira ticket uniquely identifying the issue by `{key}:{hash}`
2. For any SQ issues which are `closed` but untagged,
  + Comment and close the associated Jira ticket
  + Tag the SQ issue as `done`
3. For any SQ issues which are reopened,
  + Comment and reopen the Jira ticket
  + Remove the `done` tag from the SQ issue
  + Add a new tag to the SQ issue, `sq_regression`
  + Add a new label to the Jira issue, `sq_regression`
    - If the label already exists, add a second label, `repeat_regression`
4. For any SQ issue which are closed but tagged with `sq_regression`,
  + Remove the `sq_regression` tag from the SQ issue
  + Tag the SQ issue as `done`
  + Comment and close the associated Jira ticket

## Explanation

* This script only actions after a SonarQube scan completes
  + The script only actions against the scanned Project
* New issues create Jira tickets
* Jira tickets have comments indicating status
* Jira tickets are searchable based on `{key}:{hash}`
* Regressions are identified and documented
* Ongoing regressions are identified and documented
* SonarQube is the source of truth for the current state
* The current state is reflected in Jira

# Useful References

* Cookie-based authentication is deprecated
  + https://developer.atlassian.com/cloud/jira/platform/jira-rest-api-cookie-based-authentication/

* How to create the Jira Token for Basic Authentication
  + https://community.atlassian.com/t5/Jira-questions/How-to-authenticate-to-Jira-REST-API-with-curl/qaq-p/1312165
  + tldr: `echo -n EMAIL:API_TOKEN | base64`

* How to create the SonarQube Token for Basic Authentication
  + `echo -n API_TOKEN | base64`

# Current State

1. Identify new issues in SonarQube
2. Create Jira tickets in Jira
3. Identify resolved issues in SonarQube
