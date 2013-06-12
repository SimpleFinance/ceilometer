#!/usr/bin/env python
# coding: utf-8

import collections
import datetime
import logging
import os
import sys
import time

import boto.utils
import boto.ses

__all__ = ["Environment"]

log = logging.getLogger("ceilometer")

DEFAULTS = dict(
    AWS_REGION = "us-east-1"
)

def main():
    env = Environment(defaults=DEFAULTS, **os.environ)
    log.addHandler(logging.StreamHandler())
    log.level = logging.DEBUG

    region = env["AWS_REGION"]
    ses = SES(api=boto.ses.connect_to_region(region))
    for value, key, typ in ses.fetch_metrics():
        print "%10s %20s %s" % (value, key, typ)

class AWS(object):
    metrics = []

    def __init__(self, api=None):
        self.api = api

    def fetch_metrics(self):
        for metric in self.metrics:
            for result in getattr(self, metric)():
                yield result

class SES(AWS):
    metrics = [
        "verified_email_addresses",
        "quota",
        "send_statistics"
    ]
            
    def verified_email_addresses(self):
        verified = self.api.list_verified_email_addresses().get(
            "ListVerifiedEmailAddressesResponse", {}).get(
                "ListVerifiedEmailAddressesResult", {}).get(
                    "VerifiedEmailAddresses", [])

        yield len(verified), "ses.verified_email_addresses", "kv"

    def quota(self):
        quota = self.api.get_send_quota().get(
            "GetSendQuotaResponse", {}).get(
                "GetSendQuotaResult", {})
        yield float(quota["Max24HourSend"]), "ses.quota.max_24_hour_send", "kv"
        yield float(quota["SentLast24Hours"]), "ses.quota.sent_last_24_hours", "kv"
        yield float(quota["MaxSendRate"]), "ses.quota.max_send_rate", "kv"

    def get_send_statistics(self, since):
        send = self.api.get_send_statistics().get(
            "GetSendStatisticsResponse", {}).get(
                "GetSendStatisticsResult", {}).get(
                    "SendDataPoints", [])

        for data in send:
            data['Timestamp'] = boto.utils.parse_ts(data['Timestamp'])
            if data['Timestamp'] > since:
                yield data

    def send_statistics(self, since=None):
        if since is None:
            since = datetime.datetime.utcnow() - datetime.timedelta(hours=24)

        totals = collections.defaultdict(int)
        for data in self.get_send_statistics(since):
            data.pop("Timestamp")
            for key, value in data.items():
                totals[key] += int(value)

        for key in sorted(totals):
            yield totals[key], "ses.stats.%s_last_24_hours" % key.lower(), "kv"
            
class Environment(dict):

    def __init__(self, defaults=None, **kwargs):
        super(Environment, self).__init__(**kwargs)
        self.defaults = defaults

    def __getitem__(self, key):
        return super(Environment, self).get(
            key,
            self.defaults[key])

if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit()