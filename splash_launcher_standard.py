"""Unbranded entry point retaining the bilingual Qur'an verse splash."""
import os

os.environ["FTIR_SOUDA_BRANDING"] = "0"

from splash_launcher import main


if __name__ == "__main__":
    main()
