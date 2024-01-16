from symbols import ProgramSymbols, Array, Variable
from procedure_symbols import (ProcedureSymbols, ProcedureArray, ProcedureArgsArray,
                               ProcedureVariable, ProcedureArgsVariable)
from encoder import Encoder

from sly import Lexer
from sly import Parser
import sys

from globals import modify_global_consts_address, program_lines, modify_global_command_lineno


# Lexer class for tokenizing the input
class ImperativeLexer(Lexer):
    # Set of token names
    tokens = {PROCEDURE, IS, IN, END, PROGRAM, IF, THEN, ELSE, ENDIF,
              WHILE, DO, ENDWHILE, REPEAT, UNTIL, READ, WRITE, PID, TAB,
              ASSIGN, EQ, NE, GT, LT, GE, LE, NUM}

    # Set of literals
    literals = {'+', '-', '*', '/', '%', ',', ';', '(', ')', '[', ']'}

    # Ignore whitespaces
    ignore = ' \t'

    # Ignore one-line comments
    @_(r'\#.*')
    def ignore_comment(self, t):
        self.lineno += t.value.count('\n')

    # Ignore new lines
    @_(r'\n+')
    def ignore_newline(self, t):
        self.lineno += len(t.value)

    # Regular expressions for the tokens
    PROCEDURE = r'PROCEDURE'
    ENDWHILE = r'ENDWHILE'
    ENDIF = r'ENDIF'
    END = r'END'
    PROGRAM = r'PROGRAM'
    THEN = r'THEN'
    ELSE = r'ELSE'
    WHILE = r'WHILE'
    REPEAT = r'REPEAT'
    UNTIL = r'UNTIL'
    READ = r'READ'
    WRITE = r'WRITE'
    IF = r'IF'
    IS = r'IS'
    IN = r'IN'
    DO = r'DO'
    PID = r'[_a-z]+'

    TAB = r'T'

    ASSIGN = r':='
    GE = r'>='
    LE = r'<='
    NE = r'!='
    EQ = r'='
    GT = r'>'
    LT = r'<'

    # Convert the given number into integer
    @_(r'\d+')
    def NUM(self, t):
        t.value = int(t.value)
        return t

    # Throw error
    def error(self, t):
        raise Exception(f"ERROR: Invalid symbol encountered - '{t.value[0]}' (line {self.lineno}")


# Parser class
class ImperativeParser(Parser):
    # Tokens received from the lexer
    tokens = ImperativeLexer.tokens
    # Creating symbol classes for main and procedures
    procedure_symbols = ProcedureSymbols()
    symbols = ProgramSymbols()
    # List of all encountered procedure variables/arrays
    all_procedures_symbols = []
    consts = set()
    # List of all encoders (each for every procedure/main)
    whole_code = []
    code = None
    # List of arguments for a procedure call
    arguments_to_call = []

    @_('procedures main')
    def program_all(self, p):
        return self.whole_code

    @_('procedures PROCEDURE proc_head IS declarations IN commands END', 'procedures PROCEDURE proc_head IS IN commands END')
    def procedures(self, p):
        self.procedure_symbols.set_procedure_name(p[2][0])

        if self.all_procedures_symbols:
            last_symbol = self.all_procedures_symbols[-1]
            last_memory_offset = last_symbol.memory_offset
            self.procedure_symbols.memory_offset += last_memory_offset

            last_procedure_address = last_symbol.start_address
            self.procedure_symbols.start_address = last_procedure_address
        else:
            self.procedure_symbols.start_address = 1

        self.code = Encoder(p.commands, self.procedure_symbols, self.whole_code, True, p.lineno)
        self.whole_code.append(self.code)

        self.procedure_symbols.end_address = len(self.whole_code)
        self.all_procedures_symbols.append(self.procedure_symbols)
        self.procedure_symbols = ProcedureSymbols()

    @_('')
    def procedures(self, p):
        pass

    @_('PROGRAM IS declarations IN commands END', 'PROGRAM IS IN commands END')
    def main(self, p):
        modify_global_command_lineno(p.lineno)
        self.code = Encoder(p.commands, self.symbols, self.whole_code, False, p.lineno)
        modify_global_consts_address(self.symbols.memory_offset + 1)
        self.whole_code.append(self.code)

        return self.code

    @_('commands command')
    def commands(self, p):
        return p[0] + [p[1]]

    @_('command')
    def commands(self, p):
        return [p[0]]

    @_('identifier ASSIGN expression ";"')
    def command(self, p):
        return "assign", p[0], p[2]

    @_('IF condition THEN commands ELSE commands ENDIF')
    def command(self, p):
        resp = "ifelse", p[1], p[3], p[5], self.consts.copy()
        self.consts.clear()
        return resp

    @_('IF condition THEN commands ENDIF')
    def command(self, p):
        resp = "if", p[1], p[3], self.consts.copy()
        self.consts.clear()
        return resp

    @_('WHILE condition DO commands ENDWHILE')
    def command(self, p):
        resp = "while", p[1], p[3], self.consts.copy()
        self.consts.clear()
        return resp

    @_('REPEAT commands UNTIL condition ";"')
    def command(self, p):
        return "until", p[3], p[1]

    @_('proc_call ";"')
    def command(self, p):
        return "proc_call", p[0]

    @_('READ identifier ";"')
    def command(self, p):
        return "read", p[1]

    @_('WRITE value ";"')
    def command(self, p):
        if p[1][0] == "const":
            self.consts.add(int(p[1][1]))
        return "write", p[1]

    @_('PID "(" args_decl ")"')
    def proc_head(self, p):
        return p[0], p[2]

    @_('PID "(" args ")"')
    def proc_call(self, p):
        # Only procedures can be called, so I check if there are any
        if len(self.all_procedures_symbols) == 0:
            raise Exception(f"No procedure named '{p[0]}' found or a procedure used recursively (line {p.lineno})!")
        else:
            # Checking if a procedure with the given identifier exists
            for procedure in self.all_procedures_symbols:
                if p[0] == procedure.name:
                    # Procedure was found but the number of arguments does not match
                    if len(p[2]) != len(procedure.args):
                        raise Exception(f"Wrong number of arguments for procedure '{p[0]}' (line {p.lineno})!")
                    # Clearing received arguments list
                    self.arguments_to_call = []
                    return p[0], p[2]

            raise Exception(f"No procedure named '{p[0]}' found or a procedure used recursively! (line {p.lineno})!")

    @_('declarations "," PID', 'PID')
    def declarations(self, p):
        # Checking first if parsing the main program or a procedure
        # Parsing a procedure
        modify_global_command_lineno(p.lineno)
        if len(self.symbols) < len(self.procedure_symbols):
            # It is not the first procedure so the memory offset has to be added
            if len(self.all_procedures_symbols) != 0:
                current_memory_offset = self.all_procedures_symbols[-1].memory_offset
                self.procedure_symbols.add_variable(p[-1], current_memory_offset)
            # It is the first procedure (memory offset is equal to 0)
            else:
                self.procedure_symbols.add_variable(p[-1])
        # Parsing main program
        else:
            if len(self.all_procedures_symbols) != 0:
                current_memory_offset = self.all_procedures_symbols[-1].memory_offset
                self.symbols.add_variable(p[-1], current_memory_offset)
                self.procedure_symbols.add_variable(p[-1], current_memory_offset)
            else:
                self.symbols.add_variable(p[-1])
                self.procedure_symbols.add_variable(p[-1])

    @_('declarations "," PID "[" NUM "]"')
    def declarations(self, p):
        modify_global_command_lineno(p.lineno)
        if len(self.symbols) < len(self.procedure_symbols):
            if len(self.all_procedures_symbols) != 0:
                current_memory_offset = self.all_procedures_symbols[-1].memory_offset
                self.procedure_symbols.add_array(p[2], p[4], current_memory_offset)
            else:
                self.procedure_symbols.add_array(p[2], p[4])
        else:
            if len(self.all_procedures_symbols) != 0:
                current_memory_offset = self.all_procedures_symbols[-1].memory_offset
                self.symbols.add_array(p[2], p[4], current_memory_offset)
                self.procedure_symbols.add_array(p[2], p[4], current_memory_offset)
            else:
                self.symbols.add_array(p[2], p[4])
                self.procedure_symbols.add_array(p[2], p[4])

    @_('PID "[" NUM "]"')
    def declarations(self, p):
        modify_global_command_lineno(p.lineno)
        if len(self.symbols) < len(self.procedure_symbols):
            if len(self.all_procedures_symbols) != 0:
                current_memory_offset = self.all_procedures_symbols[-1].memory_offset
                self.procedure_symbols.add_array(p[0], p[2], current_memory_offset)
            else:
                self.procedure_symbols.add_array(p[0], p[2])
        else:
            if len(self.all_procedures_symbols) != 0:
                current_memory_offset = self.all_procedures_symbols[-1].memory_offset
                self.symbols.add_array(p[0], p[2], current_memory_offset)
                self.procedure_symbols.add_array(p[0], p[2], current_memory_offset)
            else:
                self.symbols.add_array(p[0], p[2])
                self.procedure_symbols.add_array(p[0], p[2])

    @_('args_decl "," PID', 'PID')
    def args_decl(self, p):
        self.procedure_symbols.add_args_variable(p[-1])

    @_('args_decl "," TAB PID', 'TAB PID')
    def args_decl(self, p):
        self.procedure_symbols.add_args_array(p[-1])

    @_('args "," PID', 'PID')
    def args(self, p):
        # Collecting all the received arguments
        self.arguments_to_call.append(p[-1])
        return self.arguments_to_call

    @_('value')
    def expression(self, p):
        return p[0]

    @_('value "+" value')
    def expression(self, p):
        return "add", p[0], p[2]

    @_('value "-" value')
    def expression(self, p):
        return "sub", p[0], p[2]

    @_('value "*" value')
    def expression(self, p):
        return "mul", p[0], p[2]

    @_('value "/" value')
    def expression(self, p):
        return "div", p[0], p[2]

    @_('value "%" value')
    def expression(self, p):
        return "mod", p[0], p[2]

    @_('value EQ value')
    def condition(self, p):
        return "eq", p[0], p[2]

    @_('value NE value')
    def condition(self, p):
        return "ne", p[0], p[2]

    @_('value LT value')
    def condition(self, p):
        return "lt", p[0], p[2]

    @_('value GT value')
    def condition(self, p):
        # print(p[0], p[2])
        return "gt", p[0], p[2]

    @_('value LE value')
    def condition(self, p):
        return "le", p[0], p[2]

    @_('value GE value')
    def condition(self, p):
        return "ge", p[0], p[2]

    @_('NUM')
    def value(self, p):
        return "const", p[0]

    @_('identifier')
    def value(self, p):
        return "load", p[0]

    @_('PID')
    def identifier(self, p):
        if p[0] in self.symbols or p[0] in self.procedure_symbols:
            return p[0]
        else:
            return "undeclared", p[0]

    @_('PID "[" NUM "]"')
    def identifier(self, p):
        if p[0] in self.procedure_symbols and type(self.procedure_symbols[p[0]]) == ProcedureArgsArray:
            return "array", p[0], p[2]
        elif p[0] in self.symbols and type(self.symbols[p[0]]) == Array:
            return "array", p[0], p[2]
        elif p[0] in self.procedure_symbols and type(self.procedure_symbols[p[0]]) == ProcedureArray:
            return "array", p[0], p[2]
        else:
            raise Exception(f"Undeclared array {p[0]} (line {p.lineno})!")

    @_('PID "[" PID "]"')
    def identifier(self, p):
        if p[0] in self.symbols and type(self.symbols[p[0]]) == Array:
            if p[2] in self.symbols and type(self.symbols[p[2]]) == Variable:
                return "array", p[0], ("load", p[2])
            else:
                return "array", p[0], ("load", ("undeclared", p[2]))
        elif p[0] in self.procedure_symbols and type(self.procedure_symbols[p[0]]) == ProcedureArray:
            if p[2] in self.procedure_symbols and (type(self.procedure_symbols[p[2]]) == ProcedureVariable or type(self.procedure_symbols[p[2]]) == ProcedureArgsVariable):
                return "array", p[0], ("load", p[2])
            else:
                return "array", p[0], ("load", ("undeclared", p[2]))
        elif p[0] in self.procedure_symbols and type(self.procedure_symbols[p[0]]) == ProcedureArgsArray:
            if p[2] in self.procedure_symbols and (type(self.procedure_symbols[p[2]]) == ProcedureVariable or type(self.procedure_symbols[p[2]]) == ProcedureArgsVariable):
                return "array", p[0], ("load", p[2])
            else:
                return "array", p[0], ("load", ("undeclared", p[2]))
        else:
            raise Exception(f"Undeclared array {p[0]} (line {p.lineno})!")


if __name__ == '__main__':
    with open(sys.argv[1]) as in_f:
        text = in_f.read()

    lexer = ImperativeLexer()
    current_line = None
    for tok in lexer.tokenize(text):
        if current_line != tok.lineno:
            current_line = tok.lineno
            program_lines.append((tok.type, tok.lineno))  # Append a tuple with token type and line number

    parser = ImperativeParser()

    parser.parse(lexer.tokenize(text))

    # Receiving the last encoder (it is the main program)
    code_gen = parser.whole_code[-1]

    code_gen.create_assembly_code()
    with open(sys.argv[2], 'w') as out_f:
        for line in code_gen.code:
            print(line, file=out_f)