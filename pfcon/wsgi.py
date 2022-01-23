
import os, sys
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from pfcon.app import create_app

os.environ.setdefault("APPLICATION_MODE", "production")

application = create_app()
