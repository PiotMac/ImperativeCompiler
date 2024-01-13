from globals import get_global_consts_address, modify_global_consts_address, get_global_command_lineno


class Array:
    def __init__(self, name, memory_offset, size):
        self.name = name
        self.memory_offset = memory_offset
        self.size = size

    def __repr__(self):
        return f"[{self.memory_offset}, {self.size}]"

    def get_at(self, index):
        if 0 <= index < self.size:
            return self.memory_offset + index
        else:
            raise Exception(f"Index {index} out of range for array {self.name} of size {self.size} (line {get_global_command_lineno()})!")


class Variable:
    def __init__(self, memory_offset):
        self.memory_offset = memory_offset
        self.initialized = False

    def __repr__(self):
        return f"{'Uni' if not self.initialized else 'I'}nitialized variable at {self.memory_offset} (line {get_global_command_lineno()})!"


class ProgramSymbols(dict):
    def __init__(self):
        super().__init__()
        self.memory_offset = 0
        self.consts = {}

    def add_variable(self, name, offset=0):
        if name in self:
            raise Exception(f"Redeclaration of {name} (line {get_global_command_lineno()})!")
        self.setdefault(name, Variable(self.memory_offset + offset))
        self.memory_offset += 1

    def add_array(self, name, size, offset=0):
        if name in self:
            raise Exception(f"Redeclaration of {name}! (line {get_global_command_lineno()})")
        elif size == 0:
            raise Exception(f"Array of size 0 in declaration of {name}! (line {get_global_command_lineno()})")
        self.setdefault(name, Array(name, self.memory_offset + offset, size))
        self.memory_offset += size

    def add_const(self, value):
        available_address = get_global_consts_address()
        self.consts.setdefault(value, available_address)
        modify_global_consts_address(available_address + 1)

        return available_address

    def get_variable(self, name):
        if name in self:
            return self[name]
        else:
            raise Exception(f"Undeclared variable {name}! (line {get_global_command_lineno()})")

    def get_array_at(self, name, index):
        if name in self:
            try:
                return self[name].get_at(index)
            except AttributeError:
                raise Exception(f"Non-array {name} used as an array! (line {get_global_command_lineno()})")
        else:
            raise Exception(f"Undeclared array {name}! (line {get_global_command_lineno()})")

    def get_address(self, target):
        if type(target) == str:
            return self.get_variable(target).memory_offset
        else:
            return self.get_array_at(target[0], target[1])

    def get_const(self, val):
        if val in self.consts:
            return self.consts[val]