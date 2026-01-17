import sys
import termios
import tty


__all__ = ['read_one_char', 'prompt_yes_no']


def read_one_char() -> str:
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setcbreak(fd)
        return sys.stdin.read(1)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


def prompt_yes_no(prompt: str, default: bool = True) -> bool:
    default_str = 'Y/n' if default else 'y/N'

    while True:
        print(f'{prompt} [{default_str}] ', end='')
        sys.stdout.flush()

        y_or_n = read_one_char()
        if y_or_n.upper() not in 'YN\r\n':
            print('')
            print('Please enter Y or N.')
        else:
            break

    print(y_or_n)

    if y_or_n.upper() in 'Y':
        return True
    elif y_or_n.upper() in 'N':
        return False
    else:
        return default
