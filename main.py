import logging

from src.inat_download import run as inat_run

# log_level = logging.INFO
log_level = logging.DEBUG


def main():
    logging.basicConfig(
        level=log_level, format="%(asctime)s - %(levelname)s - %(message)s"
    )
    inat_run()


if __name__ == "__main__":
    main()
