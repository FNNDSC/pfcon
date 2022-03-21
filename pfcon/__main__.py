import os
from pfcon.app import create_app


def main():
    """
    Run pfcon in development mode.
    """
    if 'APPLICATION_MODE' not in os.environ:
        os.environ['APPLICATION_MODE'] = 'dev'
    app = create_app()
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 5005)))


if __name__ == '__main__':
    main()
