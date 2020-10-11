#!/bin/python3

import os
import sys
import re
from io import BytesIO
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s: %(message)s",
    handlers=[logging.StreamHandler(stream=sys.stdout)],
)

LOGGER = logging.getLogger("processor")

TOOL_PATTERN = re.compile(rb"^T(?P<tool>\d+)")
FAN_PATTERN = re.compile(rb"^M106( P(?P<index>\d+))? S(?P<speed>\d+(?:\.\d+)?)")
INPUT_FILE_PATH = sys.argv[1]

# configuration
FAN_INDEXES_TO_EXCLUDE = [3, ]


class Processor:
    tool = None

    def __init__(self):
        self.processors = [
            getattr(self, func_name)
            for func_name in dir(self)
            if func_name.startswith("process_")
        ]

    def process_tool(self, line):
        """
        Saves the tool number based on the last sawn tool change command.
        """
        match = TOOL_PATTERN.match(line)
        if match:
            self.tool = int(match.group("tool"))
            LOGGER.debug("Switched tool to %s", self.tool)
        return line

    def process_fan(self, line):
        """
        Looks for M106 commands based on the FAN_PATTERN and adds a `P`
        argument with a value of the last tool.
        """
        match = FAN_PATTERN.match(line)
        if match:
            index = match.group("index")
            if index is not None:
                index = int(index)
                if index in FAN_INDEXES_TO_EXCLUDE:
                    LOGGER.debug("Fan excluded")
                    return line
            line = f"M106 P{self.tool} S{match.group('speed').decode()}\n".encode()
            LOGGER.debug("Set fan for P%s", self.tool)
        return line

    def run_on_line(self, line):
        """
        Runs all the `process_` commands of this class on the provided line.
        """
        for processor in self.processors:
            line = processor(line)
        return line


def run():
    processor = Processor()
    output = BytesIO()

    total_size = os.path.getsize(INPUT_FILE_PATH)
    LOGGER.info("Total file size: %s bytes", total_size)
    reported = 0
    with open(INPUT_FILE_PATH, "rb") as gcode_file:
        for line_no, line in enumerate(gcode_file):
            if line_no == 0 and line.startswith(b"; Post-processed with idex_fan.py"):
                continue
            line = processor.run_on_line(line)
            if line:
                output.write(line)
            processed = 100 * gcode_file.tell() / total_size
            if processed > reported + 10:
                LOGGER.info("%s%%", int(processed))
                reported = reported + 10

    LOGGER.info("All processed, now saving...")

    output.seek(0)

    with open(INPUT_FILE_PATH, "wb") as gcode_file:
        gcode_file.write(b"; Post-processed with idex_fan.py\n")
        gcode_file.write(output.read())

    LOGGER.info("Done")


if __name__ == "__main__":
    run()
