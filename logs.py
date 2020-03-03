import logging
import sys

class Applogger:

    def __init__(self,name):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.DEBUG)

        # create Filehandler and set level to debug
        ch = logging.StreamHandler(sys.stdout)
        ch.setLevel(logging.DEBUG)

        # create formatter
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

        # add formatter to ch
        ch.setFormatter(formatter)

        # add ch to logger
        self.logger.addHandler(ch)
