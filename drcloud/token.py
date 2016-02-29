import random
import string

from . import time


consonants = ''.join(_ for _ in string.ascii_uppercase if _ not in 'AEIOU')
base31 = string.digits + consonants


def booking_code(extend=0):
    """Air travel booking code style token: caps and digits.

    1 letter, 1 digit, 4 consonants or decimal numbers, 1 consonant. All
    letters are allowed in the first digit but the remaining digits can
    only be consonants. This makes accidentally generating real words with
    any unfortunate associations impossible.

    log(26, 2) + log(10, 2) + (4 * log(31, 2)) + log(21, 2) > 32.23147

    There is just a little over 32 bits of information stored in this 7
    digit token. Syntactically, these tokens are seven upper case letters
    or digits that start and end with a letter.
    """
    assert extend >= 0
    first = random.choice(string.ascii_uppercase)
    second = random.choice(string.digits)
    middle = ''.join(random.choice(base31) for _ in range(4 + extend))
    last = random.choice(consonants)
    return first + second + middle + last


def seconds(t=None, full=False):
    t = t or time.utc()
    s = t.isoformat()
    return (s if full else s.replace('-', '').replace(':', '')).split('.')[0]
