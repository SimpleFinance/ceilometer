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
    AWS_REGION = "us-east-1",
    FORMAT     = "graphite",
    INTERVAL   = "30",
    LOGLEVEL   = "DEBUG",
    PREFIX     = "aws.",
)

def main():
    env = Environment(defaults=DEFAULTS, **os.environ)
    log.addHandler(logging.StreamHandler())
    log.level = getattr(logging, env["LOGLEVEL"])

    format = env["FORMAT"]
    formatter = formatters[format]
    interval = int(env["INTERVAL"])
    prefix = env["PREFIX"]

    while True:
        log.debug("beginning collection with format %r", format)
        for metric in collect(env):
            sys.stdout.write(formatter(*metric, prefix=prefix))

        log.debug("waiting %d seconds", interval)
        time.sleep(interval)

def collect(env):
    region = env["AWS_REGION"]
    
    log.debug("connecting to %s %s", region, ", ".join(APIS))
    metrics = fetch_metrics(*[API(region=region) for API in APIS.values()])

    for result in metrics:
        yield result

def fetch_metrics(*apis):
    for api in apis:
        for result in api.fetch_metrics():
            yield result

def fmt_text(value, key, typ, time, prefix="", suffix="\n"):
    return "%s%10s %20s %s%s" % (prefix, value, key, typ, suffix)

def fmt_graphite(value, key, typ, time, prefix="", suffix="\n"):
    return "%s%s.%s %s %s%s" % (prefix, key, typ, value, time, suffix)

def fmt_statsite(value, key, typ, time, prefix="", suffix="\n"):
    return "%s%s:%s|%s%s" % (prefix, key, value, typ, suffix)

formatters = dict(
    graphite = fmt_graphite,
    statsite = fmt_statsite,
    text     = fmt_text,
)

class metric(object):

    def __init__(self, now=time.time):
        self.now = now

    def __call__(self, fn):
        def wrapped(*args, **kwargs):
            now = self.now()
            for value, key, typ in fn(*args, **kwargs):
                yield value, key, typ, now
        return wrapped

class AWS(object):
    metrics = []
    connect_to_region = None

    def __init__(self, api=None, region=None):
        self.api = api
        if self.api is None and all((region, self.connect_to_region)):
            self.api = self.connect_to_region(region)

    def fetch_metrics(self):
        for metric in self.metrics:
            for result in getattr(self, metric)():
                yield result

class SES(AWS):
    connect_to_region = staticmethod(boto.ses.connect_to_region)
    metrics = [
        "verified_email_addresses",
        "quota",
        "send_statistics"
    ]

    @metric()
    def verified_email_addresses(self):
        verified = self.api.list_verified_email_addresses().get(
            "ListVerifiedEmailAddressesResponse", {}).get(
                "ListVerifiedEmailAddressesResult", {}).get(
                    "VerifiedEmailAddresses", [])

        yield len(verified), "ses.verified_email_addresses", "kv"

    @metric()
    def quota(self):
        quota = self.api.get_send_quota().get(
            "GetSendQuotaResponse", {}).get(
                "GetSendQuotaResult", {})
        yield float(quota["Max24HourSend"]), "ses.quota.max_24_hour_send", "kv"
        yield float(quota["SentLast24Hours"]), "ses.quota.sent_last_24_hours", "kv"
        yield float(quota["MaxSendRate"]), "ses.quota.max_send_rate", "kv"

    def get_send_statistics(self, since):
        now = time.time()
        send = self.api.get_send_statistics().get(
            "GetSendStatisticsResponse", {}).get(
                "GetSendStatisticsResult", {}).get(
                    "SendDataPoints", [])

        for data in send:
            data['Timestamp'] = boto.utils.parse_ts(data['Timestamp'])
            if data['Timestamp'] > since:
                yield data

    @metric()
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

APIS = dict(
    SES = SES,
)

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
