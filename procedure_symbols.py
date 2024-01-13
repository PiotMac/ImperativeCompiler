from globals import get_global_consts_address, modify_global_consts_address, get_global_command_lineno


class ProcedureArray:
    def __init__(self, name, memory_offset, size):
        self.name = name
        self.memory_offset = memory_offset
        self.size = size

    def __repr__(self):
        return f"[{self.memory_offset}, {self.size}]"

    def change_address(self, address):
        self.memory_offset = address

    def get_at(self, index):
        if 0 <= index < self.size:
            return self.memory_offset + index
        else:
            raise Exception(f"Index {index} out of range for array {self.name} of size {self.size} (line {get_global_command_lineno})!")


class ProcedureArgsArray:
    def __init__(self, name):
        self.name = name
        self.memory_offset = None
        self.size = None

    def __repr__(self):
        return f"[{self.memory_offset}, {self.size}]"

    def get_at(self, index):
        if 0 <= index < self.size:
            return self.memory_offset + index
        else:
            raise Exception(f"Index {index} out of range for array {self.name} of size {self.size} (line {get_global_command_lineno})!")

    def set_array_address_and_size(self, address, size):
        self.memory_offset = address
        self.size = size


class ProcedureVariable:
    def __init__(self, memory_offset):
        self.memory_offset = memory_offset
        self.initialized = False

    def __repr__(self):
        return f"{'Uni' if not self.initialized else 'I'}nitialized procedure variable at {self.memory_offset} (line {get_global_command_lineno()})!"

    def change_address(self, address):
        self.memory_offset = address


class ProcedureArgsVariable:
    def __init__(self):
        self.memory_offset = None
        self.initialized = False

    def __repr__(self):
        return f"{'Uni' if not self.initialized else 'I'}nitialized procedure argument variable at {self.memory_offset} (line {get_global_command_lineno()})!"

    def set_var_address(self, address):
        self.memory_offset = address


class ProcedureSymbols(dict):
    def __init__(self):
        super().__init__()
        self.name = ""
        self.memory_offset = 0
        self.start_address = 0
        self.end_address = 0
        self.args = []
        self.consts = {}

    #def set_memory_offset(self, memory_offset):
    #    self.memory_offset = memory_offset

    def get_memory_offset(self):
        return self.memory_offset

    def set_procedure_name(self, name):
        self.name = name

    def get_procedure_name(self):
        return self.name

    def add_variable(self, name, offset=0):
        if name in self:
            raise Exception(f"Redeclaration of {name} (line {get_global_command_lineno()})!")
        self.setdefault(name, ProcedureVariable(self.memory_offset + offset))
        self.memory_offset += 1

    def add_args_variable(self, name):
        self.setdefault(name, ProcedureArgsVariable())
        self.args += name

    def set_args_variable_address(self, index, address):
        self.get_variable(self.args[index]).set_var_address(address)
        self.get_variable(self.args[index]).initialized = True

    def add_args_array(self, name):
        self.setdefault(name, ProcedureArgsArray(name))
        self.args += name

    def set_args_array_address_and_size(self, index, address, size):
        x = self.args[index]
        self.get_variable(self.args[index]).set_array_address_and_size(address, size)

    def add_array(self, name, size, offset=0):
        if name in self:
            raise Exception(f"Redeclaration of {name} (line {get_global_command_lineno()})!")
        elif size == 0:
            raise Exception(f"Array of size 0 in declaration of {name} (line {get_global_command_lineno()})!")
        self.setdefault(name, ProcedureArray(name, self.memory_offset + offset, size))
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
            raise Exception(f"Undeclared variable {name} (line {get_global_command_lineno()})!")

    def get_array_at(self, name, index):
        if name in self:
            try:
                return self[name].get_at(index)
            except AttributeError:
                raise Exception(f"Non-array {name} used as an array (line {get_global_command_lineno()})!")
        else:
            raise Exception(f"Undeclared array {name} (line {get_global_command_lineno()})!")

    def get_address(self, target):
        if type(target) == str:
            return self.get_variable(target).memory_offset
        else:
            return self.get_array_at(target[0], target[1])

    def get_const(self, val):
        if val in self.consts:
            return self.consts[val]