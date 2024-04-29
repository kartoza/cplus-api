"""
This script initializes
"""

#########################################################
# Setting up the  context
#########################################################

#########################################################
# Imports
#########################################################
from django.db import connection
from django.db.utils import OperationalError
from django.contrib.auth import get_user_model
from django.core.management import call_command
import os
import time
import ast

import django

django.setup()

# Getting the secrets
admin_username = os.getenv('ADMIN_USERNAME')
admin_password = os.getenv('ADMIN_PASSWORD')
admin_email = os.getenv('ADMIN_EMAIL')

#########################################################
# 1. Waiting for PostgreSQL
#########################################################

print("-----------------------------------------------------")
print("1. Waiting for PostgreSQL")
for _ in range(60):
    try:
        connection.ensure_connection()
        break
    except OperationalError:
        time.sleep(1)
else:
    connection.ensure_connection()
connection.close()

#########################################################
# 2. Running the migrations
#########################################################

print("-----------------------------------------------------")
print("2. Running the migrations")
call_command('makemigrations')
call_command('migrate', '--noinput')

#########################################################
# 3. Creating superuser if it doesn't exist
#########################################################

print("-----------------------------------------------------")
print("3. Creating/updating superuser")
try:
    superuser = get_user_model().objects.get(username=admin_username)
    superuser.set_password(admin_password)
    superuser.is_active = True
    superuser.email = admin_email
    superuser.save()
    print('superuser successfully updated')
except get_user_model().DoesNotExist:
    superuser = get_user_model().objects.create_superuser(
        admin_username,
        admin_email,
        admin_password
    )
    print('superuser successfully created')

#########################################################
# 4. Loading fixtures
#########################################################
print("-----------------------------------------------------")
print("4. Loading fixtures")
# Disable fixtures loading in prod by including environment variable:
#  INITIAL_FIXTURES=False
_load_initial_fixtures = ast.literal_eval(
    os.getenv('INITIAL_FIXTURES', 'True'))
if _load_initial_fixtures:
    call_command('load_fixtures')

#########################################################
# 4. Collecting static files
#########################################################

print("-----------------------------------------------------")
print("4. Collecting static files")
call_command('collectstatic', '--noinput', verbosity=0)


#########################################################
# 5. Adding Periodic Task
#########################################################
def init_periodic_task():
    from django_celery_beat.models import PeriodicTask, IntervalSchedule
    from django.core.exceptions import ValidationError

    schedule, created = IntervalSchedule.objects.get_or_create(
        every=12,
        period=IntervalSchedule.HOURS,
    )
    # Should we remove existing remove_layer task first?
    # try:
    #     task = PeriodicTask.objects.get(
    #         name='Remove layers',  # simply describes this periodic task.
    #         task='remove_layers',  # name of task.
    #     )
    #     task.delete()
    # except PeriodicTask.DoesNotExist:
    #     pass

    try:
        PeriodicTask.objects.get_or_create(
            interval=schedule,
            name='Remove layers',
            task='remove_layers',
        )
    except ValidationError:
        pass


init_periodic_task()
