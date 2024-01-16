from symbols import Variable, Array
from procedure_symbols import ProcedureVariable, ProcedureArgsVariable, ProcedureArray, ProcedureArgsArray

from globals import modify_global_consts_address, program_lines, get_global_command_lineno, modify_global_command_lineno


# Class responsible for translating the commands into assembly code
class Encoder:
    """
    Encoder's attributes are:
    - commands: list of received commands
    - symbols: list of local variables (arguments)
    - earlier_symbols: list of all procedures (along with their attributes) that are visible
    - code_offset: information about how long the already generated assembly code is and where currently are we
    - code: generated assembly code
    """
    def __init__(self, commands, symbols, earlier_encoders, is_procedure, lineno_offset):
        self.is_procedure = is_procedure
        self.lineno_offset = lineno_offset
        self.commands = commands
        self.symbols = symbols
        self.earlier_encoders = earlier_encoders.copy()
        self.code_offset = 0
        self.code = []
        self.is_in_loop = False

    def create_assembly_code(self):
        if self.is_procedure:
            self.create_assembly_code_from_commands(self.commands)
            self.symbols.end_address = len(self.code)
        else:
            modify_global_consts_address(self.symbols.memory_offset + 1)
            self.create_assembly_code_from_commands(self.commands)
            self.code.append("HALT")

    def create_assembly_code_from_commands(self, commands):
        for command in commands:
            # command[1] - ('load', 'n') || ('const', 2)
            if command[0] == "write":
                self.find_command_lineno('WRITE')
                value = command[1]
                register = 'b'
                register1 = 'c'
                if value[0] == "load":
                    if type(value[1]) == tuple:
                        if value[1][0] == "undeclared":
                            var = value[1][1]
                            self.load_variable_address(var, register1, declared=False)
                        elif value[1][0] == "array":
                            self.load_array_address_at(value[1][1], value[1][2], register, register1)
                    else:
                        if type(self.symbols[value[1]]) == Array or type(self.symbols[value[1]]) == ProcedureArray or type(
                                self.symbols[value[1]]) == ProcedureArgsArray:
                            raise Exception(f"Used WRITE {value[1]} but it is an array! Use READ {value[1]}[index] instead (line {get_global_command_lineno()})!")
                        if self.symbols[value[1]].initialized or self.is_in_loop:
                            if self.is_in_loop:
                                print(f"WARNING: Variable {value[1]} may not have been initialized (line {get_global_command_lineno()})!")
                            self.load_variable_address(value[1], register)
                        else:
                            raise Exception(f"Use of uninitialized variable {value[1]} (line {get_global_command_lineno()})!")

                elif value[0] == "const":
                    address = self.symbols.get_const(value[1])
                    if address is None:
                        address = self.symbols.add_const(value[1])

                        self.create_const(address, register)
                        self.create_const(value[1], register1)

                        # STORE b a = p(r_b) <- r_a
                        #self.code.append(f"STORE {register1} {register}")
                        # register1 == x
                        # register == y
                        self.code.append(f"GET {register1}")
                        self.code.append(f"STORE {register}")
                    else:
                        self.create_const(address, register)
                self.code.append(f"LOAD {register}")
                self.code.append(f"WRITE")

            elif command[0] == "read":
                self.find_command_lineno('READ')

                target = command[1]
                register = 'b'
                register1 = 'c'
                if type(target) == tuple:
                    self.load_array_address_at(target[1], target[2], register, register1)
                else:
                    if type(self.symbols[target]) == Array or type(self.symbols[target]) == ProcedureArray or type(self.symbols[target]) == ProcedureArgsArray:
                        raise Exception(f"Used READ {target} but it is an array! Use READ {target}[index] instead (line {get_global_command_lineno()})!")
                    self.load_variable_address(target, register)
                    self.symbols[target].initialized = True
                self.code.append(f"READ")
                self.code.append(f"STORE {register}")

            elif command[0] == "assign":
                self.find_command_lineno('PID')

                target = command[1]
                expression = command[2]
                target_reg = 'b'
                second_reg = 'c'
                third_reg = 'd'
                self.calculate_expression(expression)
                if type(target) == tuple:
                    self.load_array_address_at(target[1], target[2], second_reg, third_reg)
                else:
                    if type(self.symbols[target]) == Variable or type(self.symbols[target]) == ProcedureVariable or type(self.symbols[target]) == ProcedureArgsVariable:
                        self.load_variable_address(target, second_reg)
                        self.symbols[target].initialized = True
                    else:
                        raise Exception(f"Assigning to array {target} with no index provided (line {get_global_command_lineno()})!")
                self.code.append(f"GET {target_reg}")
                self.code.append(f"STORE {second_reg}")

            elif command[0] == "if":
                """
                command[0] - keyword
                command[1] - condition
                command[2] - commands in if
                command[3] - constants
                """
                self.find_command_lineno('IF')
                self.is_in_loop = True
                condition = self.simplify_condition(command[1])
                # If condition is easy to deduce (like 'if 4>3')
                if isinstance(condition, bool):
                    # If the condition is true do the commands inside
                    if condition:
                        self.create_assembly_code_from_commands(command[2])
                else:
                    self.prepare_consts_before_block(command[-1])
                    condition_start = len(self.code) + self.code_offset
                    self.check_condition(condition)
                    command_start = len(self.code) + self.code_offset
                    self.create_assembly_code_from_commands(command[2])
                    command_end = len(self.code) + self.code_offset
                    # If the condition is not met, jump outside of 'if' statement
                    for i in range(condition_start - self.code_offset, command_start - self.code_offset):
                        self.code[i] = self.code[i].replace('finish', str(command_end))
                self.is_in_loop = False

            elif command[0] == "ifelse":
                """
                command[0] - keyword
                command[1] - condition
                command[2] - commands in 'if'
                command[3] - commands in 'else'
                command[4] - constants
                """
                self.find_command_lineno('IF')
                self.is_in_loop = True
                condition = self.simplify_condition(command[1])
                modify_global_command_lineno(get_global_command_lineno() + 1)

                if isinstance(condition, bool):
                    # If condition is true go to the first part (before 'else')
                    if condition:
                        self.create_assembly_code_from_commands(command[2])
                    # If condition is false go to the second part (after 'else')
                    else:
                        self.create_assembly_code_from_commands(command[3])
                else:
                    self.prepare_consts_before_block(command[-1])
                    condition_start = len(self.code) + self.code_offset
                    self.check_condition(command[1])
                    if_start = len(self.code) + self.code_offset
                    self.create_assembly_code_from_commands(command[2])
                    self.code.append(f"JUMP finish")
                    else_start = len(self.code) + self.code_offset
                    self.create_assembly_code_from_commands(command[3])
                    command_end = len(self.code) + self.code_offset
                    self.code[else_start - self.code_offset - 1] = self.code[else_start - self.code_offset - 1].replace('finish',
                                                                                  str(command_end))
                    for i in range(condition_start - self.code_offset, if_start - self.code_offset):
                        self.code[i] = self.code[i].replace('finish', str(else_start))

                self.is_in_loop = False

            elif command[0] == "while":
                """
                command[0] - keyword
                command[1] - condition
                command[2] - commands inside 'while'
                command[3] - constants
                """
                lines_scope = self.find_lines_scope('WHILE')
                self.is_in_loop = True
                modify_global_command_lineno(lines_scope[0])
                condition = self.simplify_condition(command[1])
                if isinstance(condition, bool):
                    # If condition is met, do commands inside while and come back
                    if condition:
                        self.prepare_consts_before_block(command[-1])
                        loop_start = len(self.code) + self.code_offset
                        self.create_assembly_code_from_commands(command[2])
                        self.code.append(f"JUMP {loop_start}")
                else:
                    self.prepare_consts_before_block(command[-1])
                    condition_start = len(self.code) + self.code_offset
                    self.check_condition(command[1])
                    loop_start = len(self.code) + self.code_offset
                    self.create_assembly_code_from_commands(command[2])
                    self.code.append(f"JUMP {condition_start}")
                    loop_end = len(self.code) + self.code_offset
                    for i in range(condition_start - self.code_offset, loop_start - self.code_offset):
                        self.code[i] = self.code[i].replace('finish', str(loop_end))

                self.is_in_loop = False

            elif command[0] == "until":
                """
                command[0] - keyword
                command[1] - condition
                command[2] - commands inside 'repeat'
                """
                lines_scope = self.find_lines_scope('REPEAT')
                self.is_in_loop = True
                modify_global_command_lineno(lines_scope[0])
                loop_start = len(self.code) + self.code_offset
                self.create_assembly_code_from_commands(command[2])
                condition_start = len(self.code) + self.code_offset
                self.check_condition(command[1])
                condition_end = len(self.code) + self.code_offset
                for i in range(condition_start - self.code_offset, condition_end - self.code_offset):
                    self.code[i] = self.code[i].replace('finish', str(loop_start))

                self.is_in_loop = False

            elif command[0] == "proc_call":
                """
                command[0] - keyword
                command[1][0] - procedure's name
                command[1][1] - list of procedure's arguments           
                """
                self.find_command_lineno('PID')

                args = command[1][1]

                # Find which procedure's encoder is called
                received_encoder = None
                for encoder in self.earlier_encoders:
                    if encoder.symbols.name == command[1][0]:
                        received_encoder = encoder
                        break

                if received_encoder is None:
                    raise Exception(f"Procedure {command[1]} not found (line {get_global_command_lineno()})!")

                # Passing arguments to the procedure
                for i in range(0, len(command[1][1])):
                    # Getting argument from the caller
                    received_var = self.symbols.get_variable(command[1][1][i])
                    # Getting argument from the called procedure
                    proc_var = type(received_encoder.symbols.get_variable(received_encoder.symbols.args[i]))
                    # Checking if the types are okay (passing an array)
                    if type(received_var) == Array or type(received_var) == ProcedureArray or type(received_var) == ProcedureArgsArray:
                        if proc_var == Variable or proc_var == ProcedureVariable or proc_var == ProcedureArgsVariable:
                            raise Exception(
                                f"Array {args[i]} (used as the '{i + 1}' argument) in call of the procedure '{command[1][0]}' instead of a variable line({get_global_command_lineno()})!")
                        # If the types are compatible, get the address of the array and its size
                        caller_arg_address = received_var.memory_offset
                        caller_arg_size = received_var.size
                        # Properly adjust the argument in the procedure
                        received_encoder.symbols.set_args_array_address_and_size(i, caller_arg_address, caller_arg_size)
                    # Checking if the types are okay (passing a non-array variable)
                    if type(received_var) == Variable or type(received_var) == ProcedureVariable or type(received_var) == ProcedureArgsVariable:
                        if proc_var == Array or proc_var == ProcedureArray or proc_var == ProcedureArgsArray:
                            raise Exception(f"Variable '{args[i]}' (used as the {i + 1} argument) in call of the procedure '{command[1][0]}' instead of an array line({get_global_command_lineno()})!")
                        # Getting the address of the variable and passing it to the procedure's argument
                        caller_arg_address = received_var.memory_offset
                        received_encoder.symbols.set_args_variable_address(i, caller_arg_address)

                current_line = get_global_command_lineno()
                modify_global_command_lineno(received_encoder.lineno_offset)
                self.find_command_lineno('IN')
                # Getting current code length, so the procedure knows where to jump back
                received_encoder.code_offset = len(self.code) + self.code_offset
                received_encoder.create_assembly_code()
                modify_global_command_lineno(current_line)

                # Initializing any symbols that had been uninitialized but were initialized elsewhere
                for s in self.symbols:
                    var = self.symbols.get_variable(s)
                    if (type(var) == Variable or type(var) == ProcedureVariable or type(var) == ProcedureArgsVariable) and not var.initialized and s in args:
                        if received_encoder.symbols.get_variable(received_encoder.symbols.args[args.index(s)]).initialized:
                            var.initialized = True

                # Procedure's generated code is appended to the current code
                for line in received_encoder.code:
                    self.code.append(line)

                # Procedure's generated code is erased
                if received_encoder.is_procedure:
                    received_encoder.code = []

    """
    Function responsible for creating a number in the given register
    """
    def create_const(self, const, reg='a'):
        self.code.append(f"RST {reg}")
        if const > 0:
            # Removing '0b' part
            bits = bin(const)[2:]
            # Iterating over the bits except the last one
            for bit in bits[:-1]:
                # Increment by one
                if bit == '1':
                    self.code.append(f"INC {reg}")
                # Multiply by two using left shift
                self.code.append(f"SHL {reg}")
            # Checking the last bit
            if bits[-1] == '1':
                self.code.append(f"INC {reg}")

    """
    Function responsible for calculating expression's value
    """
    def calculate_expression(self, expression, target_reg='b', second_reg='c', third_reg='d', fourth_reg='e',
                             fifth_reg='f'):
        # The expression is a number, create it in a register
        if expression[0] == "const":
            self.create_const(expression[1], target_reg)

        # The expression is to get the variable's value
        elif expression[0] == "load":
            # Getting value from an array
            if type(expression[1]) == tuple:
                # If the variable is undeclared, throw an exception
                if expression[1][0] == "undeclared":
                    self.load_variable(expression[1][1], target_reg, declared=False)
                # If everything is alright, get the wanted value from the array
                elif expression[1][0] == "array":
                    self.load_array_at(expression[1][1], expression[1][2], target_reg, second_reg)
            # Getting value from a non-array
            else:
                # If array is used as a variable
                if type(self.symbols[expression[1]]) == ProcedureArgsArray or type(self.symbols[expression[1]]) == ProcedureArray or type(self.symbols[expression[1]]) == Array:
                    raise Exception(
                        f"Use of array {expression[1]} as a variable (line {get_global_command_lineno()})!")

                # Variable is initialized or is used as the procedure's argument
                if self.symbols[expression[1]].initialized or type(self.symbols[expression[1]]) == ProcedureArgsVariable:
                    self.load_variable(expression[1], target_reg)
                else:
                    if self.is_in_loop:
                        print(f"WARNING: Variable {expression[1]} may not have been initialized (line {get_global_command_lineno()})! ")
                        self.load_variable(expression[1], target_reg)
                    else:
                        raise Exception(f"Use of uninitialized variable {expression[1]} (line {get_global_command_lineno()})!")

        else:
            if expression[1][0] == 'const':
                const, var = 1, 2
            elif expression[2][0] == 'const':
                const, var = 2, 1
            else:
                const = None

            # Adding numbers
            if expression[0] == "add":
                # Adding two constants
                if expression[1][0] == expression[2][0] == "const":
                    self.create_const(expression[1][1] + expression[2][1], target_reg)

                # Adding the same thing
                elif expression[1] == expression[2]:
                    self.calculate_expression(expression[1], target_reg, second_reg)
                    # Doubling it
                    self.code.append(f"SHL {target_reg}")

                # If the constant is less than fourteen
                elif const and expression[const][1] < 14:
                    self.calculate_expression(expression[var], target_reg, second_reg)
                    change = f"INC {target_reg}"
                    self.code += expression[const][1] * [change]

                else:
                    # Calculating both parts of the expression and adding them together
                    self.calculate_expression(expression[1], target_reg, second_reg)
                    self.calculate_expression(expression[2], second_reg, third_reg)
                    self.code.append(f"GET {target_reg}")
                    self.code.append(f"ADD {second_reg}")
                    self.code.append(f"PUT {target_reg}")

            # Subtracting numbers
            elif expression[0] == "sub":
                # If both parts are constants
                if expression[1][0] == expression[2][0] == "const":
                    # If val > 0, create a constant in the register
                    val = max(0, expression[1][1] - expression[2][1])
                    if val:
                        self.create_const(val, target_reg)
                    else:
                        self.code.append(f"RST {target_reg}")

                # Both parts are equal to each other (reset register)
                elif expression[1] == expression[2]:
                    self.code.append(f"RST {target_reg}")

                elif const and const == 2 and expression[const][1] < 14:
                    self.calculate_expression(expression[var], target_reg, second_reg)
                    # cost = const < 14
                    change = f"DEC {target_reg}"
                    self.code += expression[const][1] * [change]

                # If the first part is already 0
                elif const and const == 1 and expression[const][1] == 0:
                    self.code.append(f"RST {target_reg}")

                else:
                    # Calculate both expressions and return their result
                    self.calculate_expression(expression[1], target_reg, second_reg)
                    # If the const >= 14 then the cost of creating a const is >= 7
                    self.calculate_expression(expression[2], second_reg, third_reg)
                    self.code.append(f"GET {target_reg}")  # cost = 1
                    self.code.append(f"SUB {second_reg}")  # cost = 5
                    self.code.append(f"PUT {target_reg}")  # cost = 1

            # Multiplying numbers
            elif expression[0] == "mul":
                # If both parts are constants, just multiply them
                if expression[1][0] == expression[2][0] == "const":
                    self.create_const(expression[1][1] * expression[2][1], target_reg)
                    return

                # If one part is a constant
                if const:
                    val = expression[const][1]
                    # Multiplying by zero
                    if val == 0:
                        self.code.append(f"RST {target_reg}")
                        return
                    # Multiplying by one
                    elif val == 1:
                        self.calculate_expression(expression[var], target_reg, second_reg)
                        return
                    # Checking whether val is a power of two
                    elif val & (val - 1) == 0:
                        # If it is, multiply it using left shifts
                        self.calculate_expression(expression[var], target_reg, second_reg)
                        while val > 1:
                            self.code.append(f"SHL {target_reg}")
                            val /= 2
                        return

                # If both parts are equal to each other, calculate just one of them
                if expression[1] == expression[2]:
                    self.calculate_expression(expression[1], second_reg, target_reg)
                    self.code.append(f"GET {second_reg}")
                    self.code.append(f"PUT {third_reg}")
                else:
                    self.calculate_expression(expression[1], second_reg, target_reg)
                    self.calculate_expression(expression[2], third_reg, target_reg)

                # Check if there is multiplication by zero
                self.code.append(f"GET {second_reg}")
                k = len(self.code) + self.code_offset
                self.code.append(f"JZERO {k + 42}")
                self.code.append(f"GET {third_reg}")
                k = len(self.code) + self.code_offset
                self.code.append(f"JZERO {k + 40}")

                # Check which number is bigger
                self.code.append(f"GET {second_reg}")
                self.code.append(f"SUB {third_reg}")
                k = len(self.code) + self.code_offset
                self.code.append(f"JZERO {k + 19}")

                # Second is bigger than third
                # Check if the third is already zero
                self.code.append(f"RST {target_reg}")
                self.code.append(f"GET {third_reg}")
                k = len(self.code) + self.code_offset
                self.code.append(f"JZERO {k + 34}")

                # Check if third is odd (using shifts)
                self.code.append(f"PUT {fifth_reg}")
                self.code.append(f"SHR {third_reg}")
                self.code.append(f"SHL {third_reg}")
                self.code.append(f"SUB {third_reg}")
                k = len(self.code) + self.code_offset
                self.code.append(f"JPOS {k + 2} ")
                k = len(self.code) + self.code_offset
                self.code.append(f"JUMP {k + 4}")
                # If it is odd (shifts cannot be used)
                self.code.append(f"GET {target_reg}")
                self.code.append(f"ADD {second_reg}")
                self.code.append(f"PUT {target_reg}")
                # If it is even (shifts can be used)
                self.code.append(f"GET {fifth_reg}")  # Retrieve previously shifted third
                self.code.append(f"PUT {third_reg}")  # Put it back in the right register
                self.code.append(f"SHR {third_reg}")  # Divide the third by two
                self.code.append(f"SHL {second_reg}")  # Multiply the second by two
                self.code.append(f"RST a")
                k = len(self.code) + self.code_offset
                self.code.append(f"JUMP {k - 16}")

                # Third is bigger than second
                # Check if the second is already zero
                self.code.append(f"RST {target_reg}")
                self.code.append(f"GET {second_reg}")
                k = len(self.code) + self.code_offset
                self.code.append(f"JZERO {k + 16}")

                # Check if second is odd (using shifts)
                self.code.append(f"PUT {fifth_reg}")
                self.code.append(f"SHR {second_reg}")
                self.code.append(f"SHL {second_reg}")
                self.code.append(f"SUB {second_reg}")
                k = len(self.code) + self.code_offset
                self.code.append(f"JPOS {k + 2}")
                k = len(self.code) + self.code_offset
                self.code.append(f"JUMP {k + 4}")
                # If it is odd (shifts cannot be used)
                self.code.append(f"GET {target_reg}")
                self.code.append(f"ADD {third_reg}")
                self.code.append(f"PUT {target_reg}")
                # If it is even (shifts can be used)
                self.code.append(f"GET {fifth_reg}")  # Retrieve previously shifted second
                self.code.append(f"PUT {second_reg}")  # Put it back in the right register
                self.code.append(f"SHR {second_reg}")  # Divide the second by two
                self.code.append(f"SHL {third_reg}")  # Multiply the third by two
                self.code.append(f"RST a")
                k = len(self.code) + self.code_offset
                self.code.append(f"JUMP {k - 16}")

            # Dividing two numbers
            elif expression[0] == "div":
                # Division of constants
                if expression[1][0] == expression[2][0] == "const":
                    # Do the integer division
                    if expression[2][1] > 0:
                        self.create_const(expression[1][1] // expression[2][1], target_reg)
                    # If the second expression is equal to zero
                    else:
                        self.code.append(f"RST {target_reg}")
                    return

                # Division of equal parts
                elif expression[1] == expression[2]:
                    # If expression == 0, return 0
                    # Else, return 1
                    self.calculate_expression(expression[1], third_reg, second_reg)
                    self.code.append(f"RST {target_reg}")
                    self.code.append(f"GET {third_reg}")
                    k = len(self.code) + self.code_offset
                    self.code.append(f"JZERO {k + 2}")
                    self.code.append(f"INC {target_reg}")
                    return

                # Division of 0 / x
                elif const and const == 1 and expression[const][1] == 0:
                    self.code.append(f"RST {target_reg}")
                    return

                # Division of x / const
                elif const and const == 2:
                    val = expression[const][1]
                    # const == 0
                    if val == 0:
                        self.code.append(f"RST {target_reg}")
                        return
                    # const == 1
                    elif val == 1:
                        self.calculate_expression(expression[var], target_reg, second_reg)
                        return
                    # const % 2 == 0
                    elif val & (val - 1) == 0:
                        self.calculate_expression(expression[var], target_reg, second_reg)
                        while val > 1:
                            self.code.append(f"SHR {target_reg}")
                            val /= 2
                        return

                # Calculating x and y from x / y
                self.calculate_expression(expression[1], third_reg, second_reg)
                self.calculate_expression(expression[2], fourth_reg, second_reg)
                # Performing division
                self.perform_division(target_reg, second_reg, third_reg, fourth_reg)

            elif expression[0] == "mod":
                if expression[1][0] == expression[2][0] == "const":
                    if expression[2][1] > 0:
                        self.create_const(expression[1][1] % expression[2][1], target_reg)
                    else:
                        self.code.append(f"RST {target_reg}")
                    return

                elif expression[1] == expression[2]:
                    self.code.append(f"RST {target_reg}")
                    return

                elif const and const == 1 and expression[const][1] == 0:
                    self.code.append(f"RST {target_reg}")
                    return

                elif const and const == 2:
                    val = expression[const][1]
                    if val < 2:
                        self.code.append(f"RST {target_reg}")
                        return
                    elif val == 2:
                        self.calculate_expression(expression[var], second_reg, target_reg)
                        self.code.append(f"RST {target_reg}")
                        self.code.append(f"GET {second_reg}")
                        self.code.append(f"SHR {second_reg}")
                        self.code.append(f"SHL {second_reg}")
                        self.code.append(f"SUB {second_reg}")
                        k = len(self.code) + self.code_offset
                        self.code.append(f"JPOS {k + 2}")
                        k = len(self.code) + self.code_offset
                        self.code.append(f"JUMP {k + 2}")
                        self.code.append(f"INC {target_reg}")
                        return

                self.calculate_expression(expression[1], third_reg, second_reg)
                self.calculate_expression(expression[2], fourth_reg, second_reg)
                self.perform_division(second_reg, target_reg, third_reg, fourth_reg)

    def perform_division(self, quotient_register='b', remainder_register='c', dividend_register='d',
                         divisor_register='e'):

        # Reset quotient's and remainder's registers
        start = len(self.code) + self.code_offset
        self.code.append(f"RST {quotient_register}")
        self.code.append(f"RST {remainder_register}")
        self.code.append(f"GET {divisor_register}")
        # Check if the divisor is equal to zero, if yes, end the division
        self.code.append(f"JZERO finish")
        # Add the dividend to the remainder
        self.code.append(f"GET {remainder_register}")
        self.code.append(f"ADD {dividend_register}")
        self.code.append(f"PUT {remainder_register}")

        # Store the divisor in the dividend
        self.code.append(f"RST a")
        self.code.append(f"ADD {divisor_register}")
        self.code.append(f"PUT {dividend_register}")

        # Check if the divisor is already bigger than the dividend
        self.code.append(f"RST a")
        self.code.append(f"ADD {remainder_register}")
        self.code.append(f"SUB {dividend_register}")
        self.code.append(f"JZERO block_start")

        # Determine how many times the divisor can be multiplied by two (while it is still smaller than the dividend)
        self.code.append(f"RST a")
        self.code.append(f"ADD {dividend_register}")
        self.code.append(f"SUB {remainder_register}")
        k = len(self.code) + self.code_offset
        self.code.append(f"JZERO {k + 3}")
        # If it became bigger, divide it by two and go further
        self.code.append(f"SHR {dividend_register}")
        k = len(self.code) + self.code_offset
        self.code.append(f"JUMP {k + 3}")
        # If it is still smaller, multiply it by two and come back
        self.code.append(f"SHL {dividend_register}")
        k = len(self.code) + self.code_offset
        self.code.append(f"JUMP {k - 7}")

        block_start = len(self.code) + self.code_offset
        # Check if the divisor is bigger than the dividend
        self.code.append(f"RST a")
        self.code.append(f"ADD {dividend_register}")
        self.code.append(f"SUB {remainder_register}")
        k = len(self.code) + self.code_offset
        # If it is, finish
        self.code.append(f"JZERO {k + 2}")
        self.code.append(f"JUMP finish")
        # Or else, decrease the dividend by the divisor and increment the result by one
        self.code.append(f"GET {remainder_register}")
        self.code.append(f"SUB {dividend_register}")
        self.code.append(f"PUT {remainder_register}")
        self.code.append(f"INC {quotient_register}")

        midblock_start = len(self.code) + self.code_offset
        # If the maximum available divisor was subtracted from dividend already,
        # go back to subtracting smaller values
        self.code.append(f"RST a")
        self.code.append(f"ADD {dividend_register}")
        self.code.append(f"SUB {remainder_register}")
        self.code.append(f"JZERO block_start")
        self.code.append(f"SHR {dividend_register}")
        # Check if the dividend is already smaller than the divisor
        self.code.append(f"RST a")
        self.code.append(f"ADD {divisor_register}")
        self.code.append(f"SUB {dividend_register}")
        k = len(self.code) + self.code_offset
        self.code.append(f"JZERO {k + 2}")  # If no, multiply the result by two and go back
        self.code.append(f"JUMP finish")  # If yes, end the division
        self.code.append(f"SHL {quotient_register}")
        self.code.append(f"JUMP midblock_start")
        end = len(self.code) + self.code_offset

        for i in range(start- self.code_offset, end- self.code_offset):
            self.code[i] = self.code[i].replace('midblock_start', str(midblock_start))
            self.code[i] = self.code[i].replace('block_start', str(block_start))
            self.code[i] = self.code[i].replace('finish', str(end))

    def simplify_condition(self, condition):
        # If the condition is based on two constants, return the results as a boolean
        if condition[1][0] == "const" and condition[2][0] == "const":
            if condition[0] == "le":
                return condition[1][1] <= condition[2][1]
            elif condition[0] == "ge":
                return condition[1][1] >= condition[2][1]
            elif condition[0] == "lt":
                return condition[1][1] < condition[2][1]
            elif condition[0] == "gt":
                return condition[1][1] > condition[2][1]
            elif condition[0] == "eq":
                return condition[1][1] == condition[2][1]
            elif condition[0] == "ne":
                return condition[1][1] != condition[2][1]

        # 0 <= ... or 0 > ...
        elif condition[1][0] == "const" and condition[1][1] == 0:
            if condition[0] == "le":
                return True
            elif condition[0] == "gt":
                return False
            else:
                return condition

        # ... >= 0 or ... < 0
        elif condition[2][0] == "const" and condition[2][1] == 0:
            if condition[0] == "ge":
                return True
            elif condition[0] == "lt":
                return False
            else:
                return condition

        # Both sides are the same
        elif condition[1] == condition[2]:
            # >=, <=, ==
            if condition[0] in ["ge", "le", "eq"]:
                return True
            # >, <, !=
            else:
                return False

        else:
            return condition

    def check_condition(self, condition, first_reg='b', second_reg='c', third_reg='d'):
        # If in the condition 0 is the first argument
        if condition[1][0] == "const" and condition[1][1] == 0:
            # 0 >= ... or 0 == ...
            if condition[0] == "ge" or condition[0] == "eq":
                # If the expression is equal to zero, don't skip
                self.calculate_expression(condition[2], first_reg, second_reg)
                self.code.append(f"GET {first_reg}")
                k = len(self.code) + self.code_offset
                self.code.append(f"JZERO {k + 2}")
                self.code.append("JUMP finish")

            # 0 < ... or 0 != ...
            elif condition[0] == "lt" or condition[0] == "ne":
                # If the expression is equal to zero, skip the part
                self.calculate_expression(condition[2], first_reg, second_reg)
                self.code.append(f"GET {first_reg}")
                self.code.append(f"JZERO finish")

        # If in the condition 0 is the second argument
        elif condition[2][0] == "const" and condition[2][1] == 0:
            if condition[0] == "le" or condition[0] == "eq":
                self.calculate_expression(condition[1], first_reg, second_reg)
                self.code.append(f"GET {first_reg}")
                k = len(self.code) + self.code_offset
                self.code.append(f"JZERO {k + 2}")
                self.code.append("JUMP finish")

            elif condition[0] == "gt" or condition[0] == "ne":
                self.calculate_expression(condition[1], first_reg, second_reg)
                self.code.append(f"GET {first_reg}")
                self.code.append(f"JZERO finish")

        else:
            # Calculate both parts of the condition
            self.calculate_expression(condition[1], first_reg, third_reg)
            self.calculate_expression(condition[2], second_reg, third_reg)

            if condition[0] == "le":
                self.code.append(f"GET {first_reg}")
                self.code.append(f"SUB {second_reg}")
                self.code.append(f"PUT {first_reg}")
                k = len(self.code) + self.code_offset
                self.code.append(f"JZERO {k + 2}")
                self.code.append(f"JUMP finish")

            elif condition[0] == "ge":
                self.code.append(f"GET {second_reg}")
                self.code.append(f"SUB {first_reg}")
                k = len(self.code) + self.code_offset
                self.code.append(f"JZERO {k + 2}")
                self.code.append(f"JUMP finish")

            elif condition[0] == "lt":
                self.code.append(f"GET {second_reg}")
                self.code.append(f"SUB {first_reg}")
                self.code.append(f"JZERO finish")

            elif condition[0] == "gt":
                self.code.append(f"GET {first_reg}")
                self.code.append(f"SUB {second_reg}")
                self.code.append(f"JZERO finish")

            elif condition[0] == "eq":
                # Checking x - y and y - x
                self.code.append(f"GET {first_reg}")
                self.code.append(f"SUB {second_reg}")
                k = len(self.code) + self.code_offset
                self.code.append(f"JZERO {k + 2}")
                self.code.append(f"JUMP finish")
                self.code.append(f"GET {second_reg}")
                self.code.append(f"SUB {first_reg}")
                k = len(self.code) + self.code_offset
                self.code.append(f"JZERO {k + 2}")
                self.code.append(f"JUMP finish")

            elif condition[0] == "ne":
                # Checking x - y and y - x
                self.code.append(f"GET {first_reg}")
                self.code.append(f"SUB {second_reg}")
                k = len(self.code) + self.code_offset
                self.code.append(f"JZERO {k + 2}")
                k = len(self.code) + self.code_offset
                self.code.append(f"JUMP {k + 4}")
                self.code.append(f"GET {second_reg}")
                self.code.append(f"SUB {first_reg}")
                self.code.append(f"JZERO finish")

    def load_array_at(self, array, index, reg1, reg2):
        self.load_array_address_at(array, index, reg1, reg2)
        self.code.append(f"LOAD {reg1}")
        self.code.append(f"PUT {reg1}")

    def load_array_address_at(self, array, index, reg1, reg2):
        # If the call is in the form of f[const]
        if type(index) == int:
            address = self.symbols.get_address((array, index))
            self.create_const(address, reg1)
        # If the call is in the form of f[x] (where x is a variable)
        elif type(index) == tuple:
            # If in the f[x] the x is undeclared
            if type(index[1]) == tuple:
                self.load_variable(index[1][1], reg1, declared=False)
            else:
                # If in the f[x] the x is not initialized
                if not self.symbols[index[1]].initialized:
                    # Give just a warning if the variable is inside any kind of loop or if (it may be initialized elsewhere)
                    if self.is_in_loop:
                        print(f"WARNING: Variable {array} may not have been initialized (line {get_global_command_lineno()})!")
                    else:
                        raise Exception(f"Trying to use {array}({index[1]}) where variable {index[1]} is uninitialized (line {get_global_command_lineno()})!")
                # If everything is fine - load the variable's address
                self.load_variable(index[1], reg1)
            # Get the address of the first element of the array and then add the variable's address
            var = self.symbols.get_variable(array)
            self.create_const(var.memory_offset, reg2)
            self.code.append(f"GET {reg1}")
            self.code.append(f"ADD {reg2}")
            self.code.append(f"PUT {reg1}")

    def load_variable(self, name, reg, declared=True):
        self.load_variable_address(name, reg, declared)
        self.code.append(f"LOAD {reg}")
        self.code.append(f"PUT {reg}")

    def load_variable_address(self, name, reg, declared=True):
        if declared:
            address = self.symbols.get_address(name)
            self.create_const(address, reg)
        else:
            raise Exception(f"Undeclared variable {name} (line {get_global_command_lineno()})!")

    # Add the constants inside the block to the symbols
    def prepare_consts_before_block(self, consts, reg1='b', reg2='c'):
        for c in consts:
            address = self.symbols.get_const(c)
            if address is None:
                address = self.symbols.add_const(c)
                self.create_const(address, reg1)
                self.create_const(c, reg2)
                self.code.append(f"GET {reg2}")
                self.code.append(f"STORE {reg1}")

    # For if, if-else, while and repeat find its scope
    def find_lines_scope(self, command):
        end_statement = ""
        if command == 'WHILE':
            end_statement = "ENDWHILE"
        elif command == 'REPEAT':
            end_statement = "UNTIL"

        for token in program_lines:
            if token[0] == command and token[1] > get_global_command_lineno():
                loop_start_lineno = token[1]
                command_counter = 0
                for tok in program_lines:
                    if tok[1] > loop_start_lineno:
                        if tok[0] == f"{end_statement}" and command_counter == 0:
                            return [loop_start_lineno, tok[1]]
                        if tok[0] == f"{end_statement}":
                            command_counter -= 1
                        if tok[0] == command:
                            command_counter += 1
                break

    # Finding where the command is regarding current program line
    def find_command_lineno(self, command):
        for token in program_lines:
            if token[0] == command and token[1] > get_global_command_lineno():
                modify_global_command_lineno(token[1])
                break
