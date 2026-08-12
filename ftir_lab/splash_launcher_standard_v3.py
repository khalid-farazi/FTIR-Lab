"""Standard FTIR Lab v3.1 launcher."""
import os

os.environ["FTIR_SOUDA_BRANDING"] = "0"

from ftir_lab.splash_launcher_v3 import main


if __name__ == "__main__":
    main()
