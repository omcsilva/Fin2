import os
import django
import sys

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from django.test import Client
c = Client()
# We need to simulate the flow to get to step 3
# It's an XP statement, wizard step 3. 
# It might be too complex to mock the file upload. 
