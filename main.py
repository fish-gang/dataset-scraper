import logging
import os

from src.inat_download import run as inat_run


def main():
    logging.basicConfig(
        level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s"
    )
    inat_run()


if __name__ == "__main__":
    main()
