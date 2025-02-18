"""Cancel all pending and in-progress jobs"""
from dotenv import load_dotenv

from openweights import OpenWeights


load_dotenv()
client = OpenWeights()




for job in client.jobs.list(limit=1000):
    if job['status'] in ['pending', 'in_progress']:
        from datetime import datetime, timedelta, timezone
        from dateutil import parser
        if datetime.now(timezone.utc) - parser.parse(job['created_at']).astimezone(timezone.utc) > timedelta(days=2):
            print(job)
            client.jobs.cancel(job['id'])

