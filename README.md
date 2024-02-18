# An imperative compiler
This is a project of a simple imperative compiler developed during my Formal Languages and Translation Techniques course at Wrocław University of Science and Technology.

## Technologies
- Python 3.10.12
- SLY 0.5

## Usage and installation
First, you need to install SLY library in Python using `pip install sly`.
Then, you can run the program by writing `python3 main.py <input_file> <output_file>` in the terminal.

## Files
- `maszyna_wirtualna` - Folder with an implementation of a virtual machine, created by [Maciej Gębala](http://ki.pwr.edu.pl/gebala/).
- `tests` - Folder that consists of many tests written by [Maciej Gębala](http://ki.pwr.edu.pl/gebala/) and [Marcin Słowik](https://cs.pwr.edu.pl/slowik/).
- `specifications.pdf` - PDF file with specifications for the compiler (in Polish)
- `main.py` - The file contains the implementation of the lexer and parser, and is also used to run the entire program.
- `encoder.py` - A file that compiles the received data into machine code consistent with the specifications of the virtual machine.
- `symbols.py` - The file responsible for storing symbols of the main function of the compiled program and for managing their memory.
- `procedure_symbols.py` - It does the same as the file above, but it is responsible for procedures.
- `globals.py` - A file containing global variables that the rest of the files use.
