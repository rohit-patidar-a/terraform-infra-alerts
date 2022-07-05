import os
import json
import base64
import re
import requests

from base64 import b64decode

DEFAULT_USERNAME = os.environ.get('DEFAULT_USERNAME', 'AWS Lambda')
DEFAULT_CHANNEL = os.environ.get('DEFAULT_CHANNEL', '#slack-mdm-dev')
DEFAULT_EMOJI = os.environ.get('DEFAULT_EMOJI', ':information_source:')
USERNAME_PREFIX = os.environ.get('USERNAME_PREFIX', '')


def get_slack_channel(region, event_src, topic_name, channel_map):
    '''Map region and event type to Slack channel name
    '''
    try:
        return channel_map[topic_name]
    except KeyError:
        return DEFAULT_CHANNEL


def get_slack_username(event_src):
    '''Map event source to the Slack username
    '''
    username_map = {
        'cloudwatch': 'AWS CloudWatch',
        'autoscaling': 'AWS AutoScaling',
        'elasticache': 'AWS ElastiCache',
        'codepipeline': 'AWS CodePipeline',
        's3': 'AWS S3'}

    try:
        return "{0}{1}".format(USERNAME_PREFIX, username_map[event_src])
    except KeyError:
        return DEFAULT_USERNAME


def lambda_handler(event, context):
    '''The Lambda function handler
    '''
    config = {
      'webhook_url': os.environ['WEBHOOK_URL'],
      'channel_map': json.loads(base64.b64decode(os.environ['CHANNEL_MAP']))
    }

    event_cond = 'default'
    sns = event['Records'][0]['Sns']
    print('DEBUG EVENT:', sns['Message'])
    try:
        json_msg = json.loads(sns['Message'])
    except ValueError as e:
        json_msg = {}

    if sns['Subject']:
        message = sns['Subject']
    else:
        message = sns['Message']

    attachments = []
    if json_msg.get('AlarmName'):
        event_src = 'cloudwatch'
        event_cond = json_msg['NewStateValue']
        color_map = {
            'OK': 'good',
            'INSUFFICIENT_DATA': 'warning',
            'ALARM': 'danger'
        }

        attachments = [{
            'fallback': json_msg,
            'message': json_msg,
            'color': color_map[event_cond],
            "fields": [{
                "title": "Alarm",
                "value": json_msg['AlarmName'],
                "short": True
            }, {
                "title": "Status",
                "value": json_msg['NewStateValue'],
                "short": True
            }, {
                "title": "Description",
                "value": json_msg['AlarmDescription'],
                "short": False
            }, {
                "title": "Reason",
                "value": json_msg['NewStateReason'],
                "short": False
            }]
        }]
    elif json_msg.get('Cause'):
        event_src = 'autoscaling'
        attachments = [{
            "text": "Details",
            "fallback": message,
            "color": "good",
            "fields": [{
                "title": "Capacity Change",
                "short": True
            }, {
                "title": "Event",
                "value": json_msg['Event'],
                "short": False
            }, {
                "title": "Cause",
                "value": json_msg['Cause'],
                "short": False
            }]
        }]
    elif re.match("S3", sns.get('Subject') or ''):
        event_src = 's3'
        attachments = [{
            "fields": [{
                "title": "Source",
                "value": "{0} '{1}'".format(json_msg['Event Source'], json_msg['Source ID'])
                },{
                "title": "Message",
                "value": json_msg['Event Message']
                }]}]
        if json_msg.get('Identifier Link'):
            title_arr = json_msg['Identifier Link'].split('\n')
            if len(title_arr) >= 2:
                title_str = title_arr[1]
                title_lnk_str = title_arr[0]
            else:
                title_str = title_lnk_str = title_arr[0]
            attachments[0]['fields'].append({
                "title": "Details",
                "value": "<{0}|{1}>".format(title_str, title_lnk_str)
            })
    else:
        event_src = 'other'

    # SNS Topic ARN: arn:aws:sns:<REGION>:<AWS_ACCOUNT_ID>:<TOPIC_NAME>
    #
    # SNS Topic Names => Slack Channels
    #  <env>-alerts => alerts-<region>
    #  <env>-notices => events-<region>
    #
    region = sns['TopicArn'].split(':')[3]
    topic_name = sns['TopicArn'].split(':')[-1]
    # event_env = topic_name.split('-')[0]
    # event_sev = topic_name.split('-')[1]

    # print('DEBUG:', topic_name, region, event_env, event_sev, event_src)

    channel_map = config['channel_map']

    payload = {
        'text': message,
        'channel': get_slack_channel(region, event_src, topic_name, channel_map),
        'username': get_slack_username(event_src)}
    if attachments:
        payload['attachments'] = attachments
    print('DEBUG PAYLOAD:', json.dumps(payload))

    webhook_url = config['webhook_url'] \
        if re.match('^https://', config['webhook_url']) \
        else f"https://{config['webhook_url']}"
    print('DEBUG URL:', webhook_url)
    r = requests.post(webhook_url, json=payload)
    print('DEBUG STATUS:', r)
    return r.status_code
