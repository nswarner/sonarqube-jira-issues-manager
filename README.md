# plugins-jira-sonarqube

Simple scripting to manage connectivity between Jira and SonarQube. As new issues are created in SonarQube, this script will identify the new issue(s), check Jira whether a ticket exists in Jira for the SonarQube issue, and if not, creates the ticket in Jira. This script can also scan SonarQube for closed issues which likely have an open Jira ticket, comment in the Jira ticket and then close the Jira ticket.

## Features

* When a vulnerability is identified in SonarQube, this script creates a complementary Jira ticket (issue)
** The Jira ticket will contain a unique `{key}:{hash}` identifier in the description
* When a vulnerability is closed (`CLOSED`) in SonarQube, this script will:
** Tag the SonarQube issue as closed (`done`)
** Close (`done`) the Jira ticket with a new comment indicating the issue is resolved

## Exception(al) workflows

* When a tagged (`done`) issue in SonarQube is in the `OPEN` status, this script will:
** Tag the SonarQube issue as reopened (`reopened`)
** Remove the SonarQube `done` tag from the SonarQube issue
** Search for an associated Jira ticket,
*** If a Jira ticket exists: (1) Reopen the ticket, (2) Add a new comment indicating it's reopened, (3) Add the label `sonarqube_regression` to the Jira ticket
*** If a Jira ticket does not exist: (1) Create the ticket, (2) Label the ticket `sonarqube_review`, (3) Add a new comment indicating a ticket may be missing