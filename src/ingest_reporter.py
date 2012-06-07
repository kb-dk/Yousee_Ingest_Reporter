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

for parameter in ['workflowstatemonitorUrl', 'ingestmonitorwebpageUrl', 'doneStartTime', 'doneEndTime']:
    if not configParser.has_option('init', parameter):
        raise Exception("Error in settings file: No '" + parameter + "' parameter in init section.")

for parameter in ['recipient', 'sender', 'subject', 'smtpServer']:
    if not configParser.has_option('mail', parameter):
        raise Exception("Error in settings file: No '" + parameter + "' parameter in mail section.")

workflowstatemonitorUrl = configParser.get('init', 'workflowstatemonitorUrl')
ingestmonitorwebpageUrl = configParser.get('init', 'ingestmonitorwebpageUrl')
doneStartTime = configParser.get('init', 'doneStartTime')
doneEndTime = configParser.get('init', 'doneEndTime')

recipient = configParser.get('mail', 'recipient')
sender = configParser.get('mail', 'sender')
subject = configParser.get('mail', 'subject')
smtpServer = configParser.get('mail', 'smtpServer')

##
## end set-up
########


# Get a list of all files that have been ingested in the last 24 hours (or,
# actually, from 'startTime' o'clock yesterday to 'endTime' o'clock today.)
# Typically this could be from 07.00 yesterday morning to 07.00 this morning.
today = datetime.datetime.now()
todayString = today.strftime('%Y-%m-%d')
yesterdayString = (today - datetime.timedelta(days=1)).strftime('%Y-%m-%d')

doneStartDate = yesterdayString + 'T' + doneStartTime
doneEndDate = todayString + 'T' + doneEndTime

# get a list of files in "Done" state. For each file only the last state is
# requested.
inDoneState = getData(
    workflowstatemonitorUrl + '/states/?includes=Done&onlyLast=true&startDate=' + doneStartDate + '&endDate=' + doneEndDate)

# get all files not in Done state regardless of date and time. For each file
# only the last state is requested.
notInDoneState = getData(workflowstatemonitorUrl + '/states/?excludes=Done&onlyLast=true')

# States Stopped and Failed are special, the rest of the of files are
# considered to be in progress. Progress includes e.i. "Queued" files.
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

# Create the body of the message (only an HTML version).
htmlMessage = writeHTMLbody(ingestmonitorwebpageUrl, inDoneState, inStoppedState, inFailedState, inProgressState,
    doneStartTime, doneEndTime)
# Iin this first release we don not want to include a text version of the email
textMessage = ""

sendMail(smtpServer, sender, recipient, subject, htmlMessage, textMessage, emailPriority)
