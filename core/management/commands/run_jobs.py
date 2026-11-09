import time
from django.core.management.base import BaseCommand
from core.accrual import run_all_jobs


class Command(BaseCommand):
    help = 'Pay out investment ROI, mature plans and settle Quick Trades. Use --loop to keep running.'

    def add_arguments(self, parser):
        parser.add_argument('--loop', action='store_true', help='keep running')
        parser.add_argument('--every', type=int, default=60, help='seconds between runs with --loop')

    def handle(self, *args, **o):
        while True:
            r = run_all_jobs()
            self.stdout.write(f"ROI paid on {r['roi_paid']} investments, {r['options_settled']} quick trades settled")
            if not o['loop']:
                break
            time.sleep(o['every'])
