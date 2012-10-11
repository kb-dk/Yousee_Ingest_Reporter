#!/usr/bin/python
# encoding: utf-8
import argparse
from ConfigParser import SafeConfigParser
import codecs

# Import the functions for the report generator
from ingest_reporter_lib import *

######
## parse command line argument and settings file
##
parser = argparse.ArgumentParser(description='YouSee døgnrapport')
parser.add_argument('--settings', '-s', nargs=1, action="store", dest="settingsFile",
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


executeReport(
    workflowstatemonitorUrl,
    ingestmonitorwebpageUrl,
    doneStartTime,
    recipient,
    sender,
    subject,
    smtpServer)