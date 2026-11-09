"""Built-in scheduler: starts one background thread per web process so ROI is paid and
Quick Trades are settled automatically - no cron job needed. Safe with several workers
(each job locks its rows). An external ping to /cron/tick/ also keeps a sleeping free host awake."""
import os
import sys
import threading
import time

INTERVAL = int(os.environ.get('JOBS_INTERVAL', '60'))
_started = False


def _loop():
    time.sleep(8)
    while True:
        try:
            from .accrual import run_all_jobs
            run_all_jobs()
        except Exception as e:  # keep the thread alive
            print('[jobs] error:', e)
        time.sleep(INTERVAL)


def start():
    global _started
    if _started or os.environ.get('RUN_SCHEDULER', '1') == '0':
        return
    argv = ' '.join(sys.argv)
    is_server = 'gunicorn' in argv or ('runserver' in argv and os.environ.get('RUN_MAIN') != 'false' and '--noreload' in argv) \
        or ('runserver' in argv and os.environ.get('RUN_MAIN') == 'true')
    if not is_server:
        return
    _started = True
    threading.Thread(target=_loop, name='elvarion-jobs', daemon=True).start()
