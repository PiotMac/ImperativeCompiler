# All variables and arrays are initialized from top to bottom
# and the rest of the memory is for creating constants

global_consts_address = 0  # First free memory cell address
program_lines = []  # List of all program lines
global_command_lineno = 0  # Current line of code


def get_global_consts_address():
    return global_consts_address


def modify_global_consts_address(address):
    global global_consts_address
    global_consts_address = address


def get_global_command_lineno():
    return global_command_lineno


def modify_global_command_lineno(value):
    global global_command_lineno
    global_command_lineno = value
