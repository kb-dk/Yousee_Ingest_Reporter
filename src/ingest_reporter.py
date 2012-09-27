#!/usr/bin/python
# encoding: utf-8
import argparse
from ConfigParser import SafeConfigParser
import codecs
import datetime

# Import the functions for the report generator
from ingest_reporter_lib import *

######
## parse command line argument and settings file
##
parser = argparse.ArgumentParser(description='YouSee døgnrapport')
parser.add_argument('-settings', '-s', nargs=1, action="store", dest="settingsFile",
    help='full path to settings file. Settings are in the INI file syntax.')
args = parser.parse_args()

configParser = SafeConfigParser()
with codecs.open(args.settingsFile[0], 'r', encoding='utf-8') as f:
    configParser.readfp(f)

if not configParser.has_section('init'):
    raise Exception("Error in settings file: No init section.")

if not configParser.has_section('mail'):
    raise Exception("Error in settings file: No mail section.")

for parameter in ['workflowstatemonitorUrl', 'ingestmonitorwebpageUrl', 'doneStartTime']:
    if not configParser.has_option('init', parameter):
        raise Exception("Error in settings file: No '" + parameter + "' parameter in init section.")

for parameter in ['recipient', 'sender', 'subject', 'smtpServer']:
    if not configParser.has_option('mail', parameter):
        raise Exception("Error in settings file: No '" + parameter + "' parameter in mail section.")

workflowstatemonitorUrl = configParser.get('init', 'workflowstatemonitorUrl')
ingestmonitorwebpageUrl = configParser.get('init', 'ingestmonitorwebpageUrl')
doneStartTime = configParser.get('init', 'doneStartTime').split(':')

recipient = configParser.get('mail', 'recipient')
sender = configParser.get('mail', 'sender')
subject = configParser.get('mail', 'subject')
smtpServer = configParser.get('mail', 'smtpServer')

##
## end set-up
########


# Get a list of all files that have been ingested in the last 24 hours (or,
# actually, from 'doneStartTime' o'clock yesterday to 24 hours later. Just
# enough time for a whole season of a really great TV series)
yesterday=datetime.datetime.now() - datetime.timedelta(days=1)
startdatetime=datetime.datetime.combine(
    # yesterday's date
    datetime.date(
        yesterday.year,
        yesterday.month,
        yesterday.day),
    # the configured time of day to start. doneStartTime is a list of [hour,minute]
    datetime.time(
        int(doneStartTime[0]),
        int(doneStartTime[1])))

enddatetime=startdatetime + datetime.timedelta(days=1)

doneStartDate = startdatetime.isoformat()
doneEndDate = enddatetime.isoformat()

# get a list of files in "Done" state. For each file only the last state is
# requested.
inDoneState = getData(
    workflowstatemonitorUrl + '/states/?includes=Done&onlyLast=true&startDate=' + doneStartDate + '&endDate=' + doneEndDate)

# get all files not in Done state regardless of date and time. For each file
# only the last state is requested.
notInDoneState = getData(workflowstatemonitorUrl + '/states/?excludes=Done&onlyLast=true')

# States Stopped and Failed are special, the rest of the of files are
# considered to be in progress. Progress also includes "Queued" files.
inStoppedState = [e for e in notInDoneState if e['stateName'] == 'Stopped']
inFailedState = [e for e in notInDoneState if e['stateName'] == 'Failed']

# if any files are in the failed state, set the priority of the email to 1 (high)
# If no files have failed, set the priority to 5 (low)
if len(inFailedState) > 0:
    emailPriority = '1'
else:
    emailPriority = '5'

# gather all files that are not either failed or done. The list is ordered by
# stateName using the compare_stateName function defined above.
inProgressState = sorted(
    [e for e in notInDoneState if e['stateName'] != 'Stopped' and e['stateName'] != 'Failed'],
    compare_stateName)

## Implementation of the functionality that ensures no failed object will be
## overlooked because of automatic restart. 
## To implement this we compare a set of all objects with a historic "failed" state
## with the set of objects currently being processed. The intersection of
## these two sets will be included in the report.
## To ensure we capture all potential problems, this functionality includes all
## historic objects.
historicFailedState = getData(workflowstatemonitorUrl + '/states/?includes=Failed')

# Extract a set of object names on objects in progress
inProgressNames = set(
    [e['entity']['name'] for e in getData(workflowstatemonitorUrl + '/states/?excludes=Done')])

# Calculate the intersection
failedAndInProgress = [e for e in failed if e['entity']['name'] in inProgressNames]


# Create the body of the message (only an HTML version).
htmlMessage = writeHTMLbody(ingestmonitorwebpageUrl, inDoneState, inStoppedState, inFailedState, inProgressState,
    startdatetime.strftime("%H.%M"), enddatetime.strftime("%H.%M"))
# Iin this first release we don not want to include a text version of the email
textMessage = ""

sendMail(smtpServer, sender, recipient, subject, htmlMessage, textMessage, emailPriority)
