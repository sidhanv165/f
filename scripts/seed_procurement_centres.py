import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "procurement_platform.settings")

import django

django.setup()

from django.core.management import call_command


call_command("load_mock_procurement_centres", per_state=1)
