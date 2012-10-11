# encoding: utf-8
import json
import urllib2
import smtplib
import datetime

from cStringIO import StringIO
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email import Charset
from email.header import Header
from email.generator import Generator

def sendMail(smtpServer, sender, recipient, subject, htmlMessage, textMessage, priority):
    """Send the e-mail report

    Keywords:
    smtpServer  -- The SMTP server to use for sending the e-mail
    sender      -- Sender of the e-mail
    recipient   -- Recipient of the e-mail
    subject     -- Subject of the e-mail
    htmlMessage -- The HTML MIME part of the e-mail
    textMessage -- The plain text MIME part of the e-mail
    priority    -- The priority of the e-mail

    """

    # Override python's weird assumption that utf-8 text should be encoded with
    # base64, and instead use quoted-printable (for both subject and body).  I
    # can't figure out a way to specify QP (quoted-printable) instead of base64 in
    # a way that doesn't modify global state. :-(
    Charset.add_charset('utf-8', Charset.QP, Charset.QP, 'utf-8')

    # Create message container - the correct MIME type is multipart/alternative.
    msg = MIMEMultipart('alternative')

    # We need to use Header objects here instead of just assigning the strings in
    # order to get our headers properly encoded (with QP).
    # You may want to avoid this if your headers are already ASCII, just so people
    # can read the raw message without getting a headache.
    msg['Subject'] = Header(subject.encode('utf-8'), 'UTF-8').encode()

    # Set X-Priority to high if there are any problemes with the ingest.
    msg['X-Priority'] = priority

    # assume From and To are not UTF-8
    msg['From'] = Header(sender.encode('utf-8'), 'UTF-8').encode()
    msg['To'] = Header(recipient.encode('utf-8'), 'UTF-8').encode()

    # Record the MIME types of both parts - text/plain and text/html.
    # Add support for empty text part
    if not textMessage == '':
        part1 = MIMEText(textMessage.encode('utf-8'), 'plain', 'UTF-8')
    part2 = MIMEText(htmlMessage.encode('utf-8'), 'html', 'UTF-8')

    # Attach parts into message container.
    # According to RFC 2046, the last part of a multipart message, in this case
    # the HTML message, is best and preferred.
    # Add support for empty text part
    if not textMessage == '':
        msg.attach(part1)

    msg.attach(part2)

    # And here we have to instantiate a Generator object to convert the multipart
    # object to a string (can't use multipart.as_string, because that escapes
    # "From" lines).
    io = StringIO()
    g = Generator(io, False)
    g.flatten(msg)

    # Send the message via local SMTP server.
    s = smtplib.SMTP(smtpServer)
    # sendmail function takes 3 arguments: sender's address, recipient's address
    # and message to send - here it is sent as one string.
    s.sendmail(sender, recipient, io.getvalue())
    s.quit()

def getDetailUrl(appurl, filename):
    """Function to construct a URL for requesting detailed information on a file detail URL example:
       http://canopus:9511/ingestmonitorwebpage/#file=tv3_yousee.2217776400-2040-04-11-19.00.00_2217780000-2040-04-11-20.00.00_ftp.ts&mode=details&period=day

       Keywords:
       appurl   -- URL of the Ingest Monitor web application
       filename -- filename to look up in the Ingest Monitor

    """
    url = appurl
    url += '/#file='
    url += filename
    url += '&mode=details&period=all'
    return url


def getData(url):
    """Function for requesting JSON formatted data from the workflow state monitor

    Keywords:
    url -- The url from which to read JSON data.

    returns a list representation of the JSON data.

    """
    data = ''
    request = urllib2.Request(url, headers={"Accept": "application/json"})
    try:
        data = json.loads(urllib2.urlopen(request).read())
    except urllib2.HTTPError, e:
        raise Exception("HTTP error: %d" % e.code)
    except urllib2.URLError, e:
        raise Exception("Network error: %s" % e.reason.args[1])

    return data

def compare_stateName(a, b):
    """Function to compare two objects based on their stateName

    """

    return cmp(a['stateName'], b['stateName'])

def compare_name(a, b):
    """Function to compare two objects based on their name

    """
    return cmp(a['entity']['name'], b['entity']['name'])


def gatherOnComponent(l):
    """Gather/group the list of files in respect to the relevant components

    Keywords:
    l -- a list of objects stemming from the JSON data

    returns a new list of [component, object], where each object has the same structure as elements in l

    """
    newList = []
    for c in list(set([e['component'] for e in l])):
        newList.append([c, [e for e in l if e['component'] == c]])
    return newList

# construct the HTML part of the report email
def writeHTMLbody(appurl, numberOfCompletedFiles, stoppedState, componentList, dayStart, dayEnd):
    """Construct the HTML part of the report e-mail.

    Keywords:
    appurl                 -- The URL to the Ingest Monitor web application
    numberOfCompletedFiles -- List of files in the Done state
    stoppedState           -- List of files in the stopped pseudo state
    failedState            -- List of files in the pseudo failed state
    componentList          -- List of all objects still in progress but with a historic failed state. The list is grouped
                              by the relevant component.
    dayStart               -- String represenation of the time of day the report begins
    dayEnd                 -- String represenation of the time of day the report ends

    Returns HTML formatted text for inclusion in the e-mail

    """
    html = u'''\
<html>
  <head></head>
  <body>
    <p>Kære Operatør</p>
       <p>
       Her en rapport over hvordan det er gået med opsamling af YouSee
       TV i det seneste døgn. Informationerne i denne mail er alle trukket fra
       <a href="%(url)s">Ingest Monitor websiden</a> som du også selv kan klikke rundt på.
       </p><p>
       Døgnet startede i går klokken %(start)s og varede indtil i dag klokken %(end)s.
       </p>
       <p>
''' % {'url': appurl, 'start': dayStart, 'end': dayEnd}

    html += '<hr>'
    html += u'<p>I det seneste døgn blev der med succes blevet behandlet ' + str(numberOfCompletedFiles) + ' filer.</p>'

    if len(componentList) > 0:
        # add a list of files still in progress BUT previously were in a FAILED state
        # grouped by the component
        html += u'<h3>Filer som tidligere fejlede men som stadig er under behandling eller er belvet genstartet.</h3>'
        html += u'<p>'
        for component in componentList:
            html += u'<h4>Følgende filer fejlede i ' + component[0] + ' komponenten:</h4>'
            for e in component[1]:
                html += u'<a href="'\
                        + getDetailUrl(appurl, e['entity']['name'])\
                        + '">'\
                        + e['entity']['name']\
                        + '</a><br>\n'
            html += u'</p>'
    else:
        html += u'<p>Ingen filer under behandling har en fejlstatus.</p>'

    html += '<hr>'
    if len(stoppedState) > 0:
        # add a list of failed files to the report.
        html += u'<h3>Filer der er markeret som værende stoppet og som kun bliver genstartet ved manuel indgriben:</h3>'
        html += u'<p>'
        for e in stoppedState:
            html += u'<a href="' + getDetailUrl(appurl, e['entity']['name']) + '">'\
                    + e['entity']['name']\
                    + u'</a><br>\n'
        html += u'</p>'
    else:
        html += u'<p>Ingen filer er markeret som stoppet.</p>'

    # end the html part of the report
    html += u'''\
        </ul>
    </p>
  </body>
</html>
'''
    return html

# function for constructing the TEXT part of the report email.
def writeTextbody(appurl, doneState, stoppedState, failedState, progressState, dayStart, dayEnd):
    """Construct the plain text part of the report e-mail.

    Keywords:
    appurl              -- The URL to the Ingest Monitor web application
    doneState           -- List of files in the Done state
    stoppedState        -- List of files in the stopped pseudo state
    failedState         -- List of files in the pseudo failed state
    progressState       -- List of files in the pseudo progress state
    dayStart            -- String represenation of the time of day the report begins
    dayEnd              -- String represenation of the time of day the report ends

    Returns the text to include in the e-mail

    """
    text = u'''\
    Kære Operatør

       Jeg har her en rapport over hvordan det er gået med opsamling af YouSee
       TV i det seneste døgn.

       Døgnet startede i går klokken %(start)s og varede indtil  dag klokken %(end)s.

''' % {'start': dayStart, 'end': dayEnd}

    if len(doneState) > 0:
        # add list of done files to the report
        text += u'Filer importeret med success:\n\n'
        for e in doneState:
            text += getDetailUrl(appurl, e['entity']['name']) + '\n'
    else:
        text += u'** INGEN FILER ER BLEVET IMPORTERET MED SUCCES I DEN SENESTE RAPPORTERINGSPERIODE **\n\n'

    if len(failedState) > 0:
        # add a list of failed files to the report.
        text += u'\n\nFiler som fejlede under import:\n\n'
        for e in failedState:
            text += getDetailUrl(appurl, e['entity']['name']) + '\n'
    else:
        text += u'\n\nIngen filer er i en fejltilstand.\n\n'

    if len(stoppedState) > 0:
        # add a list of failed files to the report.
        text += u'\n\nFiler der er markeret som værende stoppet:\n\n'
        for e in stoppedState:
            text += getDetailUrl(appurl, e['entity']['name']) + '\n'
    else:
        text += u'\n\nIngen filer er markeret som stoppet.\n\n'

    if len(progressState) > 0:
        # add a list of files still in progress
        text += u'\n\nFiler som stadig er under behandling eller sat i kø:\n\n'
        for e in progressState:
            text += getDetailUrl(appurl, e['entity']['name']) + '\n'
    else:
        text += u'\n\nIngen filer bliver processeret eller er i kø.\n\n'

    # end the text part of the report
    text += u'''\


'''
    return text

def executeReport(workflowstatemonitorUrl, ingestmonitorwebpageUrl, doneStartTime, recipient, sender, subject, smtpServer):
    """Get a list of all files that have been ingested in the last 24 hours (or,
    actually, from 'doneStartTime' o'clock yesterday to 24 hours later. Just
    enough time for a whole season of a really great TV series)

    Keyword arguments:
    workflowstatemonitorUrl -- The URL of the Work Flow State Monitor
    ingestmonitorwebpageUrl -- The URL of the Ingest Monitor
    doneStartTime           -- The time of yesterday for when the report should start. doneStartTime is formatted as a
                               list of two strings representing the hour and minute.
    recipient               -- The e-mail recipient of the report
    sender                  -- The e-mail sender of the report
    subject                 -- The e-mail subject
    smtpServer              -- The SMTP server to use for sending the e-mail report

    """

    yesterday = datetime.datetime.now() - datetime.timedelta(days=1)
    startdatetime = datetime.datetime.combine(
        # yesterday's date
        datetime.date(
            yesterday.year,
            yesterday.month,
            yesterday.day),
        # the configured time of day to start. doneStartTime is a list of [hour,minute]
        datetime.time(
            int(doneStartTime[0]),
            int(doneStartTime[1])))

    enddatetime = startdatetime + datetime.timedelta(days=1)

    doneStartDate = startdatetime.isoformat()
    doneEndDate = enddatetime.isoformat()

    numberOfCompletedFiles = len(
        getData(workflowstatemonitorUrl
                + '/states/?includes=Done&onlyLast=true&startDate='
                + doneStartDate
                + '&endDate='
                + doneEndDate))

    inStoppedState = getData(workflowstatemonitorUrl + '/states/?includes=Stopped&onlyLast=true')

    # if any files are in the failed state, set the priority of the email to 1 (high)
    # If no files have failed, set the priority to 5 (low)
    if len(getData(workflowstatemonitorUrl + '/states/?includes=Failed&onlyLast=true')) > 0:
        emailPriority = '1'
    else:
        emailPriority = '5'

    ## Implementation of the functionality that ensures no failed object will be
    ## overlooked because of automatic restart.
    ## To implement this we compare a set of all objects with a historic "failed" state
    ## with the set of objects currently being processed. The intersection of
    ## these two sets will be included in the report.
    ## To ensure we capture all potential problems, this functionality includes all
    ## historic objects.
    historicFailedState = getData(workflowstatemonitorUrl + '/states/?includes=Failed')

    # Extract a set of file names of files in progress. I.e. all files that don't have Done as the last state
    inProgressNames = set(
        [e['entity']['name'] for e in getData(workflowstatemonitorUrl + '/states/?excludes=Done&onlyLast=true')])

    # Calculate a new list consisting of all files inhistoricFailedState that are also in inProgressNames
    failedAndInProgress = [e for e in historicFailedState if e['entity']['name'] in inProgressNames]
    componentList = gatherOnComponent(failedAndInProgress)

    # Create the body of the message (only an HTML version).
    htmlMessage = writeHTMLbody(
        ingestmonitorwebpageUrl,
        numberOfCompletedFiles,
        inStoppedState,
        componentList,
        startdatetime.strftime("%H.%M"),
        enddatetime.strftime("%H.%M"))

    # In this first release we don not want to include a text version of the email
    textMessage = ""

    sendMail(smtpServer, sender, recipient, subject, htmlMessage, textMessage, emailPriority)
