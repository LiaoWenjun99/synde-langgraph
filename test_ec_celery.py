#!/usr/bin/env python
"""Quick test of CLEAN EC through Celery."""
import os, time
from celery import Celery, signature

celery_app = Celery("test",
    broker=os.environ.get('CELERY_BROKER_URL', 'redis://172.31.19.34:6379/0'),
    backend=os.environ.get('CELERY_RESULT_BACKEND', 'redis://172.31.19.34:6379/1'))

sequence = "MKTVRQERLKSIVRILERSKEPVSGAQLAEYLGDGTRIGGLSLWRDVTRQLLGPKNTSEYLADVITLAEQVERILGTDEVFVNAGRGRTHGGYVGALNYQDSQLTPQQNKLFAFDM"
print(f"Testing CLEAN EC via Celery (seq len: {len(sequence)})")

result = signature("home.tasks.run_clean_ec_job", queue="gpu", app=celery_app).delay(sequence, "celery_test")
print(f"Task ID: {result.id}")

start = time.time()
while not result.ready() and time.time() - start < 120:
    print(f"  waiting... ({time.time()-start:.0f}s)")
    time.sleep(5)

print(f"\nCompleted in {time.time()-start:.1f}s")
print(f"State: {result.state}")
print(f"Result: {result.result}")
