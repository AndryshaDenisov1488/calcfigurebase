<<<<<<< HEAD
#!/usr/bin/env python3
"""
WSGI файл для развертывания на Beget
"""

import sys
import os

# Добавляем путь к проекту
sys.path.insert(0, os.path.dirname(__file__))

from app import app

if __name__ == "__main__":
    app.run()
=======
#!/usr/bin/env python3
"""
WSGI файл для развертывания на Beget
"""

import sys
import os

# Добавляем путь к проекту
sys.path.insert(0, os.path.dirname(__file__))

from app import app

if __name__ == "__main__":
    app.run()
>>>>>>> 0ad5c8fdbf27d11e9354e3c0f7d3e79ec45ba482
